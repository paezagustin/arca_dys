"""Casos de uso fiscales sin HTTP/HTML, serializados y recuperables con PostgreSQL."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4
from zoneinfo import ZoneInfo
import logging
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.core import config
from app.core.database import engine as default_engine
from app.models.billing import BillingRequest, BillingReservation
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice
from app.services.arca.billing import validate_amount
from app.services.fiscal_gateway import gateway_for, voucher_payload, authorization, FiscalRejected

logger = logging.getLogger(__name__)


class BillingConflict(ValueError):
    pass


@dataclass(frozen=True)
class BillingResult:
    request_id: str
    state: str
    invoice_id: int | None
    message: str | None


def result(row):
    return BillingResult(row.id, row.state, row.invoice_id, row.error)


class BillingService:
    def __init__(self, engine=default_engine, gateway_factory=gateway_for):
        self.engine = engine
        self.gateway_factory = gateway_factory

    @contextmanager
    def _locked(self, point):
        # Bloqueo de SESIÓN: sobrevive a los commits que preceden al envío.
        # No se libera al pool una conexión con el bloqueo todavía adquirido.
        with self.engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(72421, :key)"), {"key": point * 100 + 11})
            connection.commit()
            try:
                with Session(bind=connection, expire_on_commit=False) as db:
                    yield db
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(72421, :key)"), {"key": point * 100 + 11})
                connection.commit()

    def issue(self, payment_ids=(), *, manual_amount=None, idempotency_key=None):
        ids = sorted(set(payment_ids))
        if manual_amount is None and not ids:
            raise ValueError("Seleccioná al menos un pago")
        if manual_amount is not None and ids:
            raise ValueError("Una factura independiente no puede incluir pagos MP")
        if manual_amount is not None and not idempotency_key:
            raise ValueError("La factura independiente requiere un identificador de operación")
        key = ("payments:" + sha256(",".join(map(str, ids)).encode()).hexdigest()) if ids else ("manual:" + str(idempotency_key or uuid4()))
        if len(key) > 100:
            raise ValueError("Identificador de operación inválido")
        point = config.ARCA_PTO_VTA
        with self._locked(point) as db:
            prior = db.scalar(select(BillingRequest).where(BillingRequest.idempotency_key == key))
            if prior:
                if manual_amount is not None and prior.total != Decimal(str(manual_amount)):
                    raise BillingConflict("La operación ya existe con otro importe")
                return result(prior)
            unresolved = db.scalar(select(BillingRequest.id).where(BillingRequest.point == point,
                BillingRequest.voucher_type == 11, BillingRequest.state.in_(["sending", "uncertain"])))
            if unresolved:
                raise BillingConflict("Hay una emisión por verificar. Resolvela antes de emitir otra: " + unresolved)
            payments = list(db.scalars(select(Payment).where(Payment.id.in_(ids)).order_by(Payment.id).with_for_update())) if ids else []
            if len(payments) != len(ids) or any(p.status != "approved" or p.registered_arca is not False or p.date_approved is None or p.mont is None or p.mont <= 0 for p in payments):
                raise BillingConflict("Algún pago ya fue facturado o dejó de estar disponible. Actualizá el listado.")
            if ids and (db.scalar(select(BillingReservation.payment_id).where(BillingReservation.payment_id.in_(ids))) is not None
                        or db.scalar(select(PaymentInvoice.id).where(PaymentInvoice.payment_id.in_(ids))) is not None):
                raise BillingConflict("Algún pago ya está vinculado a una factura o a un intento previo")
            total = sum((Decimal(str(p.mont)) for p in payments), Decimal("0")) if ids else Decimal(str(manual_amount))
            validate_amount(total)
            today = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
            snapshot = {"cuit": config.ARCA_CUIT, "point": point, "voucher_type": 11,
                        "simulation": config.INTEGRATIONS_MODE == "mock"}
            row = BillingRequest(id=str(uuid4()), idempotency_key=key, state="prepared", total=total,
                invoice_date=today, point=point, voucher_type=11, payment_ids=ids,
                payment_snapshot=[{"id": p.id, "external_id": p.id_payment_mp, "amount": str(p.mont)} for p in payments],
                fiscal_snapshot=snapshot)
            db.add(row)
            db.flush()
            for payment in payments:
                db.add(BillingReservation(payment_id=payment.id, request_id=row.id))
            db.commit()  # La identidad, el importe y las reservas existen ANTES del proveedor.
            return self._send(db, row)

    def _send(self, db, row, gateway=None):
        try:
            gateway = gateway or self.gateway_factory(self.engine)
            if row.payload is None:
                row.voucher_number = gateway.last_number(row.point, row.voucher_type) + 1
                row.payload = voucher_payload(row.total, row.invoice_date, row.point, row.voucher_number)
            row.state, row.error = "sending", None
            db.commit()  # Incluye el número exacto: un reinicio obliga a consultar ESTE comprobante.
        except Exception:
            db.rollback()
            row = db.get(BillingRequest, row.id)
            row.error = "No se pudo iniciar la emisión. No se envió un comprobante; podés reintentar esta solicitud."
            db.commit()
            return result(row)
        try:
            response = gateway.emit(row.payload)
            authorization(response, row.payload)
            return self._finalize(db, row, response)
        except FiscalRejected:
            db.rollback()
            row = db.get(BillingRequest, row.id)
            row.state, row.error = "rejected", "El proveedor rechazó la factura. Revisá la solicitud antes de reintentar."
            if "response" in locals():
                row.response = response
            db.commit()
            return result(row)
        except Exception:
            # No es seguro inferir que no se emitió. No incluir respuestas/tokens en logs.
            db.rollback()
            row = db.get(BillingRequest, row.id)
            row.state, row.error = "uncertain", "La emisión necesita verificación. No vuelvas a facturar estos pagos desde otro intento."
            db.commit()
            logger.warning("Emisión por verificar | request_id=%s", row.id)
            return result(row)

    def _finalize(self, db, row, response):
        cae, due = authorization(response, row.payload)
        number = f"{row.point:05d}-{row.voucher_number:08d}"
        if row.fiscal_snapshot.get("simulation"):
            number = "SIM-" + number
        invoice = Invoice(invoice_number=number, total_amount=row.total, invoice_date=row.invoice_date,
            cae=cae, cae_due_date=due, raw_afip_response=response, fiscal_snapshot=row.fiscal_snapshot,
            status="completed")
        db.add(invoice)
        db.flush()
        invoice.pdf_url = f"/ARCA/invoice/{invoice.id}/pdf"
        for payment_id in row.payment_ids:
            payment = db.get(Payment, payment_id)
            payment.registered_arca = True
            db.add(PaymentInvoice(payment_id=payment_id, invoice_id=invoice.id))
        row.invoice_id, row.response, row.state, row.error = invoice.id, response, "authorized", None
        db.commit()  # Factura + todos los vínculos + todas las marcas + resultado, juntos.
        return result(row)

    def recover(self, request_id, *, retry=False):
        with Session(self.engine) as read:
            found = read.get(BillingRequest, request_id)
            if found is None:
                raise ValueError("Solicitud no encontrada")
            point = found.point
        with self._locked(point) as db:
            row = db.get(BillingRequest, request_id)
            if row.state == "authorized":
                return result(row)
            try:
                gateway = self.gateway_factory(self.engine)
                if row.payload is not None:
                    response = gateway.lookup(row.payload)
                    if response is not None:
                        return self._finalize(db, row, response)
                if not retry:
                    row.error = "No se confirmó una autorización. Podés consultar otra vez o reintentar la MISMA solicitud."
                    db.commit()
                    return result(row)
                other = db.scalar(select(BillingRequest.id).where(BillingRequest.point == row.point,
                    BillingRequest.voucher_type == row.voucher_type, BillingRequest.id != row.id,
                    BillingRequest.state.in_(["sending", "uncertain"])))
                if other:
                    raise BillingConflict("Hay otra emisión por verificar")
                # Reenvío explícito con el MISMO número/payload, jamás otro número.
                return self._send(db, row, gateway)
            except Exception:
                db.rollback()
                row = db.get(BillingRequest, request_id)
                if row.payload is not None:
                    row.state = "uncertain"
                row.error = "No se pudo verificar el comprobante; la solicitud se conserva sin reemitir."
                db.commit()
                return result(row)


def get_billing_service():
    return BillingService()

"""Casos de uso fiscales sin HTTP/HTML, serializados y recuperables con PostgreSQL."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4
from zoneinfo import ZoneInfo
import logging
from sqlalchemy import select, text, case
from sqlalchemy.orm import Session
from app.core import config
from app.core.database import engine as default_engine
from app.models.billing import BillingRequest, BillingReservation
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice
from app.services.arca.billing import validate_amount
from app.services.fiscal_gateway import gateway_for, voucher_payload, authorization, FiscalRejected
from app.services.settings import fiscal_configuration
from app.services.mp_identity import operational_payment

logger = logging.getLogger(__name__)
UNCERTAIN_STATES = ["sending", "uncertain", "check_queued", "retry_queued"]
QUEUED_STATES = ["queued", "check_queued", "retry_queued"]


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
    def _locked(self, point, wait=True):
        # Bloqueo de SESIÓN: sobrevive a los commits que preceden al envío.
        # No se libera al pool una conexión con el bloqueo todavía adquirido.
        with self.engine.connect() as connection:
            if wait:
                connection.execute(text("SELECT pg_advisory_lock(72421, :key)"), {"key": point * 100 + 11})
            elif not connection.scalar(text("SELECT pg_try_advisory_lock(72421, :key)"), {"key": point * 100 + 11}):
                connection.rollback()
                yield None
                return
            connection.commit()
            try:
                with Session(bind=connection, expire_on_commit=False) as db:
                    yield db
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(72421, :key)"), {"key": point * 100 + 11})
                connection.commit()

    def issue(self, payment_ids=(), *, manual_amount=None, idempotency_key=None, expected_total=None, settings_version=None, enqueue=False):
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
        with Session(self.engine) as read:
            snapshot, version = fiscal_configuration(read)
        point = snapshot["point"]
        with self._locked(point) as db:
            prior = db.scalar(select(BillingRequest).where(BillingRequest.idempotency_key == key))
            if prior:
                if manual_amount is not None and prior.total != Decimal(str(manual_amount)):
                    raise BillingConflict("La operación ya existe con otro importe")
                return result(prior)
            db.execute(text("SELECT pg_advisory_xact_lock_shared(72422,1)"))
            snapshot, version = fiscal_configuration(db)
            if snapshot["point"] != point:
                raise BillingConflict("El punto de venta cambió. Actualizá y volvé a confirmar.")
            if settings_version is not None and version != settings_version:
                raise BillingConflict("La configuración cambió. Volvé a revisar y confirmar la factura.")
            unresolved = db.scalar(select(BillingRequest.id).where(BillingRequest.point == point,
                BillingRequest.voucher_type == 11, BillingRequest.state.in_(UNCERTAIN_STATES)))
            if unresolved:
                raise BillingConflict("Hay una emisión por verificar. Resolvela antes de emitir otra: " + unresolved)
            payments = list(db.scalars(select(Payment).where(Payment.id.in_(ids), operational_payment()).order_by(Payment.id).with_for_update())) if ids else []
            if len(payments) != len(ids) or any(p.status != "approved" or p.registered_arca is not False or p.date_approved is None or p.mont is None or p.mont <= 0 for p in payments):
                raise BillingConflict("Algún pago ya fue facturado o dejó de estar disponible. Actualizá el listado.")
            if ids and (db.scalar(select(BillingReservation.payment_id).where(BillingReservation.payment_id.in_(ids))) is not None
                        or db.scalar(select(PaymentInvoice.id).where(PaymentInvoice.payment_id.in_(ids))) is not None):
                raise BillingConflict("Algún pago ya está vinculado a una factura o a un intento previo")
            total = sum((Decimal(str(p.mont)) for p in payments), Decimal("0")) if ids else Decimal(str(manual_amount))
            validate_amount(total, Decimal(snapshot["minimum"]), Decimal(snapshot["maximum"]))
            if expected_total is not None and total != expected_total:
                raise BillingConflict("Los importes cambiaron. Volvé a revisar la selección.")
            today = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
            row = BillingRequest(id=str(uuid4()), idempotency_key=key, state="queued" if enqueue else "prepared", total=total,
                invoice_date=today, point=point, voucher_type=11, payment_ids=ids,
                payment_snapshot=[{"id": p.id, "external_id": p.id_payment_mp, "amount": str(p.mont)} for p in payments],
                fiscal_snapshot=snapshot)
            db.add(row)
            db.flush()
            for payment in payments:
                db.add(BillingReservation(payment_id=payment.id, request_id=row.id))
            db.commit()  # La identidad, el importe y las reservas existen ANTES del proveedor.
            return result(row) if enqueue else self._send(db, row)

    def _send(self, db, row, gateway=None):
        payments = list(db.scalars(select(Payment).where(Payment.id.in_(row.payment_ids), operational_payment()).with_for_update())) if row.payment_ids else []
        if (len(payments) != len(row.payment_ids) or any(p.status != "approved" or p.registered_arca is not False for p in payments)
                or (row.payment_ids and sum((Decimal(str(p.mont)) for p in payments), Decimal(0)) != row.total)):
            row.state = "uncertain" if row.payload is not None else "rejected"
            row.error = "Algún pago cambió o ya fue facturado. La solicitud se conserva para revisar; no se envió otro comprobante."
            db.commit()
            return result(row)
        db.commit()
        try:
            gateway = gateway or self._gateway(row)
            if row.payload is None:
                row.voucher_number = gateway.last_number(row.point, row.voucher_type) + 1
                row.payload = voucher_payload(row.total, row.invoice_date, row.point, row.voucher_number)
                row.fiscal_snapshot = dict(row.fiscal_snapshot, number=row.voucher_number)
            row.state, row.error = "sending", None
            db.commit()  # Incluye el número exacto: un reinicio obliga a consultar ESTE comprobante.
        except Exception:
            db.rollback()
            row = db.get(BillingRequest, row.id)
            row.state = "prepared"
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
            if row.invoice_id is not None:
                # Puede perderse el ACK de COMMIT aunque PostgreSQL lo confirmara.
                return result(row)
            row.state, row.error = "uncertain", "La emisión necesita verificación. No vuelvas a facturar estos pagos desde otro intento."
            db.commit()
            logger.warning("Emisión por verificar | request_id=%s", row.id)
            return result(row)

    def _finalize(self, db, row, response):
        if row.invoice_id is not None:
            row.state, row.error = "authorized", None
            db.commit()
            return result(row)
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
            if row.invoice_id is not None:
                if row.state != "authorized":
                    row.state, row.error = "authorized", None
                    db.commit()
                return result(row)
            try:
                gateway = self._gateway(row)
                if row.payload is not None:
                    response = gateway.lookup(row.payload)
                    if response is not None:
                        return self._finalize(db, row, response)
                if not retry:
                    row.state = "uncertain" if row.payload is not None else "prepared"
                    row.error = "No se confirmó una autorización. Podés consultar otra vez o reintentar la MISMA solicitud."
                    db.commit()
                    return result(row)
                other = db.scalar(select(BillingRequest.id).where(BillingRequest.point == row.point,
                    BillingRequest.voucher_type == row.voucher_type, BillingRequest.id != row.id,
                    BillingRequest.state.in_(UNCERTAIN_STATES)))
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

    def _gateway(self, row):
        if config.INTEGRATIONS_MODE == "production" and row.fiscal_snapshot.get("cuit") != config.ARCA_CUIT:
            raise ValueError("El emisor del intento no coincide con los certificados configurados")
        return self.gateway_factory(self.engine)

    def schedule(self, request_id, *, retry=False):
        with Session(self.engine, expire_on_commit=False) as db:
            row = db.scalar(select(BillingRequest).where(BillingRequest.id == request_id).with_for_update())
            if row is None:
                raise ValueError("Solicitud no encontrada")
            if row.state in {"authorized", "sending", *QUEUED_STATES}:
                return result(row)
            row.state = "retry_queued" if retry else "check_queued"
            row.error = None
            db.commit()
            return result(row)

    def process_one_queued(self):
        # Detectar un proceso interrumpido sin confundirlo con una emisión activa.
        # Solo una consulta se agenda automáticamente; jamás una nueva emisión.
        with Session(self.engine) as read:
            interrupted = list(read.execute(select(BillingRequest.id, BillingRequest.point).where(BillingRequest.state == "sending").limit(10)))
        for request_id, point in interrupted:
            with self._locked(point, wait=False) as db:
                if db is not None:
                    row = db.get(BillingRequest, request_id)
                    if row.state == "sending":
                        row.state = "check_queued"
                        db.commit()
        with Session(self.engine) as read:
            candidates = list(read.execute(select(BillingRequest.id, BillingRequest.point, BillingRequest.state)
                .where(BillingRequest.state.in_(QUEUED_STATES))
                .order_by(case((BillingRequest.state == "queued", 1), else_=0), BillingRequest.created_at, BillingRequest.id).limit(10)))
        for request_id, point, state in candidates:
            if state != "queued":
                self.recover(request_id, retry=state == "retry_queued")
                return True
            with self._locked(point, wait=False) as db:
                if db is None:
                    continue
                row = db.get(BillingRequest, request_id)
                if row.state != "queued":
                    continue
                blocked = db.scalar(select(BillingRequest.id).where(BillingRequest.point == point,
                    BillingRequest.state.in_(UNCERTAIN_STATES), BillingRequest.id != request_id))
                if not blocked:
                    self._send(db, row)
                    return True
        return False


def get_billing_service():
    return BillingService()

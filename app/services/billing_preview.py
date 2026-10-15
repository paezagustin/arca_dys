from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select
from app.models.billing import utcnow
from app.models.settings import BillingPreview
from app.models.payment import Payment
from app.services.settings import fiscal_configuration
from app.services.arca.billing import validate_amount
from app.services.billing import BillingService, BillingConflict


def preview_invoice(db, user_id, payment_ids=(), manual_amount=None):
    ids = sorted(set(payment_ids))
    if bool(ids) == (manual_amount is not None):
        raise ValueError("Elegí pagos o ingresá un importe independiente")
    settings, version = fiscal_configuration(db)
    if ids:
        payments = list(db.scalars(select(Payment).where(Payment.id.in_(ids))))
        if len(payments) != len(ids) or any(p.status != "approved" or p.registered_arca is not False or p.date_approved is None or p.mont is None or p.mont <= 0 for p in payments):
            raise BillingConflict("Algún pago no está disponible. Actualizá el listado.")
        amount = sum((Decimal(str(p.mont)) for p in payments), Decimal(0))
    else:
        amount = Decimal(str(manual_amount))
    validate_amount(amount, Decimal(settings["minimum"]), Decimal(settings["maximum"]))
    preview = BillingPreview(id=str(uuid4()), user_id=user_id, kind="payments" if ids else "manual",
        payment_ids=ids, total=amount, settings_version=version, expires_at=utcnow() + timedelta(minutes=15))
    db.add(preview)
    db.commit()
    return preview


def confirm_preview(db, preview_id, user_id, service=None):
    preview = db.get(BillingPreview, preview_id)
    if preview is None or preview.user_id != user_id:
        raise ValueError("Confirmación no encontrada")
    if preview.request_id:
        return preview.request_id
    if preview.expires_at <= utcnow():
        raise BillingConflict("La confirmación venció. Volvé a preparar la factura.")
    # Cerrar la transacción de lectura antes de adquirir la conexión fiscal.
    ids, amount, version, kind = preview.payment_ids, preview.total, preview.settings_version, preview.kind
    db.commit()
    result = (service or BillingService()).issue(ids, manual_amount=amount if kind == "manual" else None,
        idempotency_key=preview_id, expected_total=amount, settings_version=version)
    preview = db.get(BillingPreview, preview_id)
    preview.request_id = result.request_id
    db.commit()
    return result.request_id

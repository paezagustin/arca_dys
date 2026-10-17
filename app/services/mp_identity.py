"""Los grupos históricos ambiguos nunca son candidatos de facturación."""
from sqlalchemy import select
from app.models.payment import Payment
from app.models.mp_identity import MPPaymentIdentity


def operational_payment():
    return select(MPPaymentIdentity.id_payment_mp).where(
        MPPaymentIdentity.id_payment_mp == Payment.id_payment_mp,
        MPPaymentIdentity.payment_id == Payment.id,
        MPPaymentIdentity.legacy_duplicate.is_(False)).exists()

"""Sugerencias de cierre desde cobros ya recibidos, sin consultar la API de MP."""
from datetime import datetime, time
from decimal import Decimal
from sqlalchemy import select, func
from app.models.payment import Payment


def unbilled_mp_total(db, day):
    return db.scalar(select(func.coalesce(func.sum(Payment.mont), 0)).where(
        Payment.status == "approved", Payment.registered_arca.is_(False), Payment.mont > 0,
        Payment.date_approved.between(datetime.combine(day, time.min), datetime.combine(day, time.max)))) or Decimal("0.00")

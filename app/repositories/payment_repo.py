from datetime import date, datetime, time
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.payment import Payment
from typing import Iterable


def create_payment(db: Session, data: dict) -> Payment:
    payment = Payment(**data)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def get_payments_to_bill(db: Session) -> None:
    return db.query(Payment).filter(
        Payment.bill == True,
        Payment.registered_arca == False,
        Payment.date_approved.isnot(None)
    ).all()


def payment_exists(db: Session, id_payment_mp: str) -> bool:
    return db.query(Payment).filter(
        Payment.id_payment_mp == id_payment_mp
    ).first() is not None


def get_today_payments(db: Session)-> list:
    """
    Devuelve todos los pagos que esten para facturar
    """

    return (
        db.query(Payment)
        .filter(Payment.status == "approved")
        .filter(Payment.mont > 0.0)
        .filter(Payment.mont != None)
        .filter(Payment.registered_arca == False)
        .all()
    )


def get_invoice_report_payments(
    db: Session,
    facturado: str = "no",
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> list:
    """
    Devuelve pagos para el reporte de facturacion con filtros por estado
    de facturacion y rango de fecha sobre date_approved.
    """
    query = (
        db.query(Payment)
        .filter(Payment.status == "approved")
        .filter(Payment.mont > 0.0)
        .filter(Payment.mont != None)
        .filter(Payment.date_approved.isnot(None))
    )

    if facturado == "si":
        query = query.filter(Payment.registered_arca == True)
    elif facturado == "no":
        query = query.filter(Payment.registered_arca == False)

    if fecha_desde:
        query = query.filter(
            Payment.date_approved >= datetime.combine(fecha_desde, time.min)
        )
    if fecha_hasta:
        query = query.filter(
            Payment.date_approved <= datetime.combine(fecha_hasta, time.max)
        )

    return query.order_by(Payment.date_approved.desc()).all()


def get_payments_by_ids_to_bill(db: Session, payment_ids: Iterable[int]) -> list:
    """
    Devuelve pagos facturables filtrados por IDs.
    """
    ids = list(payment_ids or [])
    if not ids:
        return []

    return (
        db.query(Payment)
        .filter(Payment.id.in_(ids))
        .filter(Payment.status == "approved")
        .filter(Payment.mont > 0.0)
        .filter(Payment.mont != None)
        .filter(Payment.registered_arca == False)
        .all()
    )

def mark_payment_as_registered(db: Session, payment_id: int):
    """
    Update en registered_arca para marcar como facturado el pago
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment:
        payment.registered_arca = True
        db.commit()
        db.refresh(payment)
    return payment

def get_duplicated_mp_ids(db: Session) -> list:
    """
    Devuelve solo los pagos cuyo id_payment_mp aparece más de una vez.
    """

    subquery = (
        db.query(Payment.id_payment_mp)
        .group_by(Payment.id_payment_mp)
        .having(func.count(Payment.id_payment_mp) > 1)
        .subquery()
    )

    return (
        db.query(Payment)
        .filter(Payment.id_payment_mp.in_(subquery))
        .order_by(Payment.id_payment_mp.asc(), Payment.created_at.asc())
        .all()
    )

def get_duplicated_amounts(db: Session) -> list:
    """
    Devuelve solo los pagos cuyo monto (mont) aparece más de una vez.
    Útil para detectar posibles pagos repetidos por importe.
    """

    subquery = (
        db.query(Payment.mont)
        .filter(Payment.mont != None)
        .group_by(Payment.mont)
        .having(func.count(Payment.mont) > 1)
        .subquery()
    )

    return (
        db.query(Payment)
        .filter(Payment.mont.in_(subquery))
        .order_by(Payment.mont.asc(), Payment.created_at.asc())
        .all()
    )

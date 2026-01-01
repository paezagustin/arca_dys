from sqlalchemy.orm import Session
from datetime import date, time, datetime
from app.models.payment import Payment


def create_payment(db: Session, data: dict) -> Payment:
    payment = Payment(**data)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def get_payments_to_bill(db: Session, fecha: date):
    return db.query(Payment).filter(
        Payment.bill == True,
        Payment.registered_arca == False,
        Payment.date_approved.isnot(None)
    ).all()


def payment_exists(db: Session, id_payment_mp: str) -> bool:
    return db.query(Payment).filter(
        Payment.id_payment_mp == id_payment_mp
    ).first() is not None


# Provisorio


def get_today_payments(db: Session):
    """
    Devuelve todos los pagos del día actual (00:00 a 23:59)
    """

    today = datetime.now().date()

    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)

    return (
        db.query(Payment)
        .filter(Payment.created_at >= start)
        .filter(Payment.created_at <= end)
        .filter(Payment.status == "approved")
        .all()
    )
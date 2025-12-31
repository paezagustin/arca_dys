from sqlalchemy.orm import Session
from datetime import date
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

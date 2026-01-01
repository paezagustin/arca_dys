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


# Provisorio

from datetime import datetime

class MockPayment:
    def __init__(self, amount, created_at):
        self.amount = amount
        self.created_at = created_at


def get_today_payments(db=None):
    """
    Mock de pagos del día para testeo de Jinja2.
    Ignora la DB y devuelve datos hardcodeados.
    """

    return [
        MockPayment(
            amount=3000,
            created_at=datetime(2025, 1, 1, 16, 0)
        ),
        MockPayment(
            amount=4500,
            created_at=datetime(2025, 1, 1, 18, 30)
        ),
        MockPayment(
            amount=1200,
            created_at=datetime(2025, 1, 1, 20, 15)
        ),
    ]

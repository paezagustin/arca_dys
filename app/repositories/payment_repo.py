from sqlalchemy.orm import Session
from app.models.payment import Payment


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
from sqlalchemy.orm import Session
from app.models.payment_invoice import PaymentInvoice


def link_payment_to_invoice(
    db: Session,
    payment_id: int,
    invoice_id: int
) -> PaymentInvoice:

    relation = PaymentInvoice(
        payment_id=payment_id,
        invoice_id=invoice_id
    )

    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation

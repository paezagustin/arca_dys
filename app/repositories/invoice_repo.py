from sqlalchemy.orm import Session
from datetime import date
from app.models.invoice import Invoice


def create_invoice(
    db: Session,
    invoice_number: str,
    total_amount: float,
    invoice_date: date,
    cae: str | None = None,
    cae_due_date: date | None = None,
    pdf_url: str | None = None
) -> Invoice:

    invoice = Invoice(
        invoice_number=invoice_number,
        total_amount=total_amount,
        invoice_date=invoice_date,
        cae=cae,
        cae_due_date=cae_due_date,
        pdf_url=pdf_url
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def get_invoice_by_id(db: Session, invoice_id: int) -> Invoice | None:
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()


def update_status_invoice(
    db: Session,
    invoice_id: int,
    new_status: str = "completed"
) -> bool:
    try:
        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == invoice_id)
            .first()
        )

        if not invoice:
            return False

        invoice.status = new_status
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False


def get_invoices_by_date_range(db: Session, fecha_desde: date, fecha_hasta: date):
    '''
    Devuelve las facturas cuyo invoice_date esté entre fecha_desde y fecha_hasta.
    '''
    return db.query(Invoice).filter(
        Invoice.invoice_date >= fecha_desde,
        Invoice.invoice_date <= fecha_hasta
    ).order_by(Invoice.invoice_date.desc()).all()
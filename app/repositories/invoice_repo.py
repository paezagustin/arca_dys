"""Consultas de facturas. Las escrituras pertenecen al caso de uso BillingService."""
from sqlalchemy.orm import Session
from app.models.invoice import Invoice


def get_invoices_by_date_range(db: Session, fecha_desde=None, fecha_hasta=None):
    query = db.query(Invoice)
    if fecha_desde:
        query = query.filter(Invoice.invoice_date >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Invoice.invoice_date <= fecha_hasta)
    return query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).all()


def get_all_invoices(db: Session):
    return get_invoices_by_date_range(db)

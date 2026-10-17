from fastapi import APIRouter, Request, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.billing import BillingRequest
from app.models.mp_identity import MPPaymentIdentity
from app.services.billing import UNCERTAIN_STATES
from app.services.settings import read_settings
from app.services.listings import parse_filters, payment_statement, paginate, payment_totals
from app.services.payments import STATUSES
from app.web import templates

router = APIRouter(prefix="/page", tags=["Páginas"])


def filters_or_error(facturado="no", start=None, end=None, default_today=True):
    try:
        return parse_filters(facturado, start, end, default_today=default_today)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def date_range(statement, field, filters):
    if filters.start:
        statement = statement.where(field >= filters.start)
    if filters.end:
        statement = statement.where(field <= filters.end)
    return statement


@router.get("/invoice/manual")
def manual_invoice(request: Request, db: Session = Depends(get_db)):
    values, _ = read_settings(db)
    return templates.TemplateResponse(request=request, name="manual_invoice.html", context={"values": values})


@router.get("/invoice")
def invoice_page(request: Request, facturado: str = "no", fecha_desde: str | None = None, fecha_hasta: str | None = None,
                 payments_page: int = Query(1, ge=1), invoices_page: int = Query(1, ge=1), requests_page: int = Query(1, ge=1),
                 page_size: int = Query(25, ge=10, le=100), db: Session = Depends(get_db)):
    filters = filters_or_error(facturado, fecha_desde, fecha_hasta)
    payments = payment_statement(filters)
    eligible = payment_statement(filters, eligible=True)
    count, total = payment_totals(db, payments)
    eligible_count, eligible_total = payment_totals(db, eligible)
    invoices = date_range(select(Invoice), Invoice.invoice_date, filters).order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    attempts = date_range(select(BillingRequest), BillingRequest.invoice_date, filters).order_by(BillingRequest.created_at.desc(), BillingRequest.id.desc())
    review = db.scalar(select(func.count()).select_from(BillingRequest).where(BillingRequest.state.in_(UNCERTAIN_STATES + ["prepared", "rejected"])))
    payments_result = paginate(db, payments, payments_page, page_size)
    legacy_groups = db.scalar(select(func.count()).select_from(MPPaymentIdentity).where(MPPaymentIdentity.legacy_duplicate.is_(True)))
    legacy_page_ids = set(db.scalars(select(Payment.id).join(MPPaymentIdentity,
        MPPaymentIdentity.id_payment_mp == Payment.id_payment_mp).where(MPPaymentIdentity.legacy_duplicate.is_(True),
            Payment.id.in_([p.id for p in payments_result.items]))))
    eligible_page_ids = set(db.scalars(eligible.with_only_columns(Payment.id).where(Payment.id.in_([p.id for p in payments_result.items]))))
    return templates.TemplateResponse(request=request, name="pagina_facturacion.html", context={"filters": filters,
        "payments": payments_result, "eligible_page_ids": eligible_page_ids, "invoices": paginate(db, invoices, invoices_page, page_size),
        "attempts": paginate(db, attempts, requests_page, page_size), "count": count, "total": total,
        "eligible_count": eligible_count, "eligible_total": eligible_total, "page_size": page_size, "review": review,
        "legacy_page_ids": legacy_page_ids, "legacy_groups": legacy_groups})


@router.get("/billing-requests")
def billing_history(request: Request, state: str = "all", page: int = Query(1, ge=1),
                    page_size: int = Query(25, ge=10, le=100), db: Session = Depends(get_db)):
    statement = select(BillingRequest).order_by(BillingRequest.created_at.desc(), BillingRequest.id.desc())
    if state == "review":
        statement = statement.where(BillingRequest.state != "authorized")
    elif state != "all":
        raise HTTPException(422, "Elegí un estado válido")
    return templates.TemplateResponse(request=request, name="billing_history.html", context={
        "attempts": paginate(db, statement, page, page_size), "state": state})


@router.get("/payments")
def payment_history(request: Request, status: str = "all", fecha_desde: str | None = None, fecha_hasta: str | None = None,
                    page: int = Query(1, ge=1), page_size: int = Query(25, ge=10, le=100), db: Session = Depends(get_db)):
    if status != "all" and status not in STATUSES:
        raise HTTPException(422, "Elegí un estado de cobro válido")
    filters = filters_or_error("todo", fecha_desde, fecha_hasta, default_today=False)
    from datetime import datetime, time
    timestamp = func.coalesce(Payment.date_approved, Payment.created_at)
    statement = select(Payment)
    if status != "all":
        statement = statement.where(Payment.status == status)
    if filters.start:
        statement = statement.where(timestamp >= datetime.combine(filters.start, time.min))
    if filters.end:
        statement = statement.where(timestamp <= datetime.combine(filters.end, time.max))
    statement = statement.order_by(timestamp.desc(), Payment.id.desc())
    return templates.TemplateResponse(request=request, name="payments.html", context={"payments": paginate(db, statement, page, page_size),
        "status": status, "statuses": sorted(STATUSES), "filters": filters, "page_size": page_size})

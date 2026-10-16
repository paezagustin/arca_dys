"""Filtros compartidos y paginación SQL; ningún listado carga todos los registros."""
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from app.models.payment import Payment
from app.models.billing import BillingReservation
from app.models.payment_invoice import PaymentInvoice


def business_today():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()


@dataclass(frozen=True)
class PaymentFilters:
    facturado: str
    start: date | None
    end: date | None


def parse_filters(facturado="no", start=None, end=None, *, default_today=True):
    if facturado not in {"no", "si", "todo"}:
        raise ValueError("Elegí un estado de facturación válido")
    try:
        start = date.fromisoformat(start) if isinstance(start, str) and start else (start or None)
        end = date.fromisoformat(end) if isinstance(end, str) and end else (end or None)
    except ValueError as error:
        raise ValueError("Revisá las fechas ingresadas") from error
    if default_today and not start and not end:
        start = end = business_today()
    if start and end and start > end:
        raise ValueError("La fecha desde no puede ser posterior a la fecha hasta")
    return PaymentFilters(facturado, start, end)


def payment_statement(filters, *, eligible=False):
    query = select(Payment).where(Payment.status == "approved", Payment.mont > 0, Payment.date_approved.isnot(None))
    if eligible or filters.facturado == "no":
        query = query.where(Payment.registered_arca.is_(False))
    elif filters.facturado == "si":
        query = query.where(Payment.registered_arca.is_(True))
    if filters.start:
        query = query.where(Payment.date_approved >= datetime.combine(filters.start, time.min))
    if filters.end:
        query = query.where(Payment.date_approved <= datetime.combine(filters.end, time.max))
    if eligible and filters.facturado == "si":
        query = query.where(False)
    if eligible:
        query = query.where(~select(BillingReservation.payment_id).where(BillingReservation.payment_id == Payment.id).exists(),
                            ~select(PaymentInvoice.id).where(PaymentInvoice.payment_id == Payment.id).exists())
    return query.order_by(Payment.date_approved.desc(), Payment.id.desc())


@dataclass
class Page:
    items: list
    total: int
    number: int
    pages: int
    size: int


def paginate(db, statement, number=1, size=25, *, scalars=True):
    if number < 1 or size < 1 or size > 100:
        raise ValueError("Página o cantidad de filas inválida")
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    pages = max(1, (total + size - 1) // size)
    number = min(number, pages)
    selected = statement.offset((number - 1) * size).limit(size)
    return Page(list(db.scalars(selected) if scalars else db.execute(selected)), total, number, pages, size)


def payment_totals(db, statement):
    subquery = statement.order_by(None).subquery()
    count, amount = db.execute(select(func.count(), func.coalesce(func.sum(subquery.c.mont), 0)).select_from(subquery)).one()
    return count, Decimal(str(amount)).quantize(Decimal("0.01"))

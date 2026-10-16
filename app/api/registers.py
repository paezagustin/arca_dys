from calendar import monthrange
from uuid import uuid4
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.registers import SalaryPayment, CustomerCredit, EMPLOYEES, SALARY_MEDIA
from app.services.business import check_version
from app.services.registers import save_register
from app.services.listings import business_today, parse_filters, paginate
from app.web import templates

router = APIRouter(tags=["Sueldos y Fiados"])


def render_registers(request, db, model, *, identifier=None, values=None, error=None):
    salary = model is SalaryPayment
    query_params = request.query_params
    today = business_today()
    start = query_params.get("fecha_desde")
    end = query_params.get("fecha_hasta")
    if salary and start is None and end is None:
        start, end = today.replace(day=1).isoformat(), today.replace(day=monthrange(today.year, today.month)[1]).isoformat()
    try:
        filters = parse_filters("todo", start or "", end or "", default_today=False)
        employee = query_params.get("employee", "")
        paid = query_params.get("paid", "no")
        if salary and employee and employee not in EMPLOYEES:
            raise ValueError("Elegí un empleado válido")
        if not salary and paid not in {"all", "no", "yes"}:
            raise ValueError("Elegí un filtro de pago válido")
        page = int(query_params.get("page", "1"))
        if page < 1:
            raise ValueError("Página inválida")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    query = select(model)
    if filters.start:
        query = query.where(model.entry_date >= filters.start)
    if filters.end:
        query = query.where(model.entry_date <= filters.end)
    if salary and employee:
        query = query.where(model.employee == employee)
    if not salary and paid != "all":
        query = query.where(model.paid.is_(paid == "yes"))
    name = str(query_params.get("customer", "")).strip()
    if len(name) > 150:
        raise HTTPException(422, "El nombre admite hasta 150 caracteres")
    if not salary and name:
        query = query.where(model.customer.ilike("%" + name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"))
    total = db.scalar(select(func.coalesce(func.sum(query.subquery().c.amount), 0)))
    row = db.get(model, identifier) if identifier else None
    if identifier and row is None:
        raise HTTPException(404, "Registro no encontrado")
    fields = ("entry_key", "entry_date", "amount", "employee", "medium", "version") if salary else (
        "entry_key", "entry_date", "amount", "customer", "observation", "paid", "version")
    data = values if values is not None else ({key: getattr(row, key) for key in fields} if row else {
        "entry_key": str(uuid4()), "entry_date": today, "medium": "mercado pago", "paid": False})
    return templates.TemplateResponse(request=request, name="registers.html", context={"salary": salary,
        "row": row, "values": data, "error": error, "employees": EMPLOYEES, "media": SALARY_MEDIA,
        "records": paginate(db, query.order_by(model.entry_date.desc(), model.id.desc()), page),
        "filters": filters, "employee": employee, "paid": paid, "customer": name, "total": total}, status_code=422 if error else 200)


@router.get("/salaries")
def salaries(request: Request, edit: int | None = Query(None, ge=1), db: Session = Depends(get_db)):
    return render_registers(request, db, SalaryPayment, identifier=edit)


@router.get("/fiados")
def credits(request: Request, edit: int | None = Query(None, ge=1), db: Session = Depends(get_db)):
    return render_registers(request, db, CustomerCredit, identifier=edit)


async def store(request, db, model):
    values = dict(await request.form())
    try:
        identifier = int(values["id"]) if values.get("id") else None
    except ValueError:
        raise HTTPException(422, "Registro inválido") from None
    try:
        save_register(db, model, values, identifier)
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        return render_registers(request, db, model, identifier=identifier, values=values,
            error=str(exc) if isinstance(exc, ValueError) else "El formulario ya fue guardado. Revisá el listado.")
    return RedirectResponse(("/salaries" if model is SalaryPayment else "/fiados") + "?stored=1", status_code=303)


@router.post("/salaries")
async def save_salary(request: Request, db: Session = Depends(get_db)):
    return await store(request, db, SalaryPayment)


@router.post("/fiados")
async def save_credit(request: Request, db: Session = Depends(get_db)):
    return await store(request, db, CustomerCredit)


@router.post("/fiados/{identifier}/paid")
async def mark_paid(identifier: int, request: Request, db: Session = Depends(get_db)):
    values = dict(await request.form())
    row = db.scalar(select(CustomerCredit).where(CustomerCredit.id == identifier).with_for_update())
    if row is None:
        raise HTTPException(404, "Fiado no encontrado")
    # Repetir el mismo marcado de pago ya confirmado no revierte ni duplica nada.
    if not row.paid:
        try:
            check_version(row, values.get("version"))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        row.paid_date = business_today()
        row.paid, row.version = True, row.version + 1
        db.commit()
    return RedirectResponse("/fiados?paid=all&stored=1", status_code=303)

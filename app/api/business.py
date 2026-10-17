from uuid import uuid4
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.models.business import BusinessEntry, Supplier
from app.services.business import KINDS, EXPENSE_TYPES, snapshot, save_entry, save_supplier, record_date
from app.services.day_closing import unbilled_mp_total
from app.services.listings import paginate, parse_filters, business_today
from app.web import templates

router = APIRouter(prefix="/business", tags=["Gestión"])


@router.get("")
def entries(request: Request, kind: str = "all", fecha_desde: str = "", fecha_hasta: str = "",
            page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    try:
        filters = parse_filters("todo", fecha_desde, fecha_hasta, default_today=False)
        if kind not in {"all", *KINDS}:
            raise ValueError("Elegí filtros válidos")
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    query = select(BusinessEntry).where(BusinessEntry.active.is_(True))
    if kind != "all":
        query = query.where(BusinessEntry.kind == kind)
    if filters.start:
        query = query.where(BusinessEntry.entry_date >= filters.start)
    if filters.end:
        query = query.where(BusinessEntry.entry_date <= filters.end)
    grouped = query.order_by(None).subquery()
    totals = dict(db.execute(select(grouped.c.kind, func.sum(grouped.c.amount)).group_by(grouped.c.kind)).all())
    result = paginate(db, query.order_by(BusinessEntry.entry_date.desc(), BusinessEntry.id.desc()), page)
    ids = {row.supplier_id for row in result.items if row.supplier_id}
    suppliers = {s.id: s.name for s in db.scalars(select(Supplier).where(Supplier.id.in_(ids)))} if ids else {}
    return templates.TemplateResponse(request=request, name="business.html", context={"entries": result, "filters": filters,
        "kind": kind, "kinds": KINDS, "expense_types": EXPENSE_TYPES, "suppliers": suppliers, "totals": totals})


def entry_form(request, db, row=None, values=None, error=None):
    kind = row.kind if row else (values or {}).get("kind", request.query_params.get("kind", "sale"))
    if kind not in KINDS:
        raise HTTPException(422, "Elegí ventas del día o egresos")
    data = values if values is not None else (dict(snapshot(row), entry_key=row.entry_key) if row else {
        "kind": kind, "entry_date": business_today().isoformat(), "entry_key": str(uuid4())})
    data["kind"] = kind
    if kind == "sale" and values is not None:
        # Un total enviado por el navegador no participa ni del guardado ni del error.
        data.pop("amount", None)
    if not row and values is None and kind == "sale":
        suggested_mp = unbilled_mp_total(db, record_date(data["entry_date"]))
        data.update(cash_amount="", mp_amount=str(suggested_mp) if suggested_mp else "")
    selected = db.get(Supplier, int(data["supplier_id"])) if str(data.get("supplier_id", "")).isdigit() else None
    return templates.TemplateResponse(request=request, name="business_entry.html", context={"row": row,
        "values": data, "selected_supplier": selected, "expense_types": EXPENSE_TYPES,
        "error": error}, status_code=422 if error else 200)

@router.get("/sales/mp-total")
def mp_total(date: str, db: Session = Depends(get_db)):
    try:
        total = unbilled_mp_total(db, record_date(date))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"total": str(total)}


@router.get("/entries/new")
def new_entry(request: Request, db: Session = Depends(get_db)):
    return entry_form(request, db)


@router.get("/entries/{entry_id}")
def edit_entry(entry_id: int, request: Request, db: Session = Depends(get_db)):
    row = db.get(BusinessEntry, entry_id)
    if row is None or not row.active:
        raise HTTPException(404, "Registro no encontrado")
    return entry_form(request, db, row)


async def store_entry(request, db, entry_id=None):
    values = dict(await request.form())
    try:
        row = save_entry(db, values, request.state.user.username, entry_id)
    except (ValueError, IntegrityError) as error:
        db.rollback()
        message = str(error) if isinstance(error, ValueError) else "Ya existe una venta para esa fecha o este formulario fue guardado. Revisá el listado antes de repetirlo."
        return entry_form(request, db, db.get(BusinessEntry, entry_id) if entry_id else None, values, message)
    return RedirectResponse(f"/business?stored={row.id}", status_code=303)


@router.post("/entries/new")
async def create_entry(request: Request, db: Session = Depends(get_db)):
    return await store_entry(request, db)


@router.post("/entries/{entry_id}")
async def update_entry(entry_id: int, request: Request, db: Session = Depends(get_db)):
    return await store_entry(request, db, entry_id)


@router.get("/suppliers/search")
def search_suppliers(q: str = Query("", max_length=150), db: Session = Depends(get_db)):
    query = select(Supplier.id, Supplier.name).where(Supplier.active.is_(True))
    if q.strip():
        query = query.where(Supplier.name_key.contains(" ".join(q.casefold().split()), autoescape=True))
    return [{"id": row.id, "name": row.name} for row in db.execute(query.order_by(Supplier.name_key, Supplier.id).limit(20))]


@router.get("/suppliers")
def suppliers(request: Request, q: str = Query("", max_length=150), page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    query = select(Supplier)
    if q.strip():
        query = query.where(Supplier.name_key.contains(" ".join(q.casefold().split()), autoescape=True))
    rows = paginate(db, query.order_by(Supplier.active.desc(), Supplier.name_key, Supplier.id), page)
    return templates.TemplateResponse(request=request, name="suppliers.html", context={"suppliers": rows, "q": q})


def supplier_form(request, db, row=None, values=None, error=None):
    return templates.TemplateResponse(request=request, name="supplier.html", context={"row": row,
        "values": values if values is not None else (snapshot(row) if row else {"active": "1"}),
        "error": error}, status_code=422 if error else 200)



@router.get("/suppliers/new")
def new_supplier(request: Request, db: Session = Depends(get_db)):
    return supplier_form(request, db)


@router.get("/suppliers/{supplier_id}")
def edit_supplier(supplier_id: int, request: Request, db: Session = Depends(get_db)):
    row = db.get(Supplier, supplier_id)
    if row is None:
        raise HTTPException(404, "Proveedor no encontrado")
    return supplier_form(request, db, row)


async def store_supplier(request, db, supplier_id=None):
    values = dict(await request.form())
    try:
        row = save_supplier(db, values, request.state.user.username, supplier_id)
    except (ValueError, IntegrityError) as error:
        db.rollback()
        return supplier_form(request, db, db.get(Supplier, supplier_id) if supplier_id else None, values,
            str(error) if isinstance(error, ValueError) else "Ya existe ese nombre de proveedor. Seleccionalo desde el listado.")
    return RedirectResponse(f"/business/suppliers?stored={row.id}", status_code=303)


@router.post("/suppliers/new")
async def create_supplier(request: Request, db: Session = Depends(get_db)):
    return await store_supplier(request, db)


@router.post("/suppliers/{supplier_id}")
async def update_supplier(supplier_id: int, request: Request, db: Session = Depends(get_db)):
    return await store_supplier(request, db, supplier_id)


@router.post("/suppliers/{supplier_id}/delete")
async def delete_supplier(supplier_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.business import check_version
    from app.models.imports import ImportSupplierMap
    values = dict(await request.form())
    row = db.scalar(select(Supplier).where(Supplier.id == supplier_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Proveedor no encontrado")
    try:
        check_version(row, values.get("version"))
        linked = db.scalar(select(BusinessEntry.id).where(BusinessEntry.supplier_id == supplier_id).limit(1))
        mapped = db.scalar(select(ImportSupplierMap.batch_id).where(ImportSupplierMap.supplier_id == supplier_id).limit(1))
        if linked or mapped:
            raise ValueError("Este proveedor tiene egresos o una importación vinculada. Podés editarlo o archivarlo.")
        db.delete(row)
        db.commit()
    except (ValueError, IntegrityError) as error:
        db.rollback()
        return supplier_form(request, db, db.get(Supplier, supplier_id), error=str(error) if isinstance(error, ValueError)
            else "El proveedor tiene registros vinculados y no se puede eliminar.")
    return RedirectResponse("/business/suppliers?deleted=1", status_code=303)

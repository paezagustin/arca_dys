from uuid import uuid4
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.models.business import BusinessEntry, Supplier, BusinessChange
from app.services.business import KINDS, MEDIA, snapshot, save_entry, save_supplier
from app.services.listings import paginate, parse_filters, business_today
from app.web import templates

router = APIRouter(prefix="/business", tags=["Gestión"])


@router.get("")
def entries(request: Request, kind: str = "all", state: str = "active", fecha_desde: str = "", fecha_hasta: str = "",
            page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    try:
        filters = parse_filters("todo", fecha_desde, fecha_hasta, default_today=False)
        if kind not in {"all", *KINDS} or state not in {"active", "archived", "all"}:
            raise ValueError("Elegí filtros válidos")
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    query = select(BusinessEntry)
    if kind != "all":
        query = query.where(BusinessEntry.kind == kind)
    if state != "all":
        query = query.where(BusinessEntry.active.is_(state == "active"))
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
        "kind": kind, "state": state, "kinds": KINDS, "media": MEDIA, "suppliers": suppliers, "totals": totals})


def entry_form(request, db, row=None, values=None, error=None):
    data = values or (dict(snapshot(row), entry_key=row.entry_key) if row else {"kind": request.query_params.get("kind", "sale"),
        "entry_date": business_today().isoformat(), "entry_key": str(uuid4()), "active": "1", "medium": "mixed" if request.query_params.get("kind", "sale") == "sale" else "unspecified"})
    options = list(db.scalars(select(Supplier).where(or_(Supplier.active.is_(True), Supplier.id == (row.supplier_id if row else None))).order_by(Supplier.name_key)))
    categories = list(db.scalars(select(BusinessEntry.category).distinct().order_by(BusinessEntry.category).limit(100)))
    changes = paginate(db, select(BusinessChange).where(BusinessChange.entity == "entry", BusinessChange.entity_id == row.id).order_by(BusinessChange.id.desc()), int(request.query_params.get("history_page", 1))) if row else None
    return templates.TemplateResponse(request=request, name="business_entry.html", context={"row": row, "values": data,
        "suppliers": options, "categories": categories, "kinds": KINDS, "media": MEDIA, "error": error, "changes": changes}, status_code=422 if error else 200)


@router.get("/entries/new")
def new_entry(request: Request, db: Session = Depends(get_db)):
    return entry_form(request, db)


@router.get("/entries/{entry_id}")
def edit_entry(entry_id: int, request: Request, history_page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    row = db.get(BusinessEntry, entry_id)
    if row is None:
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


@router.get("/suppliers")
def suppliers(request: Request, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    rows = paginate(db, select(Supplier).order_by(Supplier.active.desc(), Supplier.name_key, Supplier.id), page)
    return templates.TemplateResponse(request=request, name="suppliers.html", context={"suppliers": rows})


def supplier_form(request, db, row=None, values=None, error=None):
    changes = paginate(db, select(BusinessChange).where(BusinessChange.entity == "supplier", BusinessChange.entity_id == row.id).order_by(BusinessChange.id.desc()), int(request.query_params.get("history_page", 1))) if row else None
    return templates.TemplateResponse(request=request, name="supplier.html", context={"row": row, "values": values or (snapshot(row) if row else {"active": "1"}),
        "changes": changes, "error": error}, status_code=422 if error else 200)


@router.get("/suppliers/new")
def new_supplier(request: Request, db: Session = Depends(get_db)):
    return supplier_form(request, db)


@router.get("/suppliers/{supplier_id}")
def edit_supplier(supplier_id: int, request: Request, history_page: int = Query(1, ge=1), db: Session = Depends(get_db)):
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

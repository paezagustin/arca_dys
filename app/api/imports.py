from difflib import get_close_matches
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.core.database import get_db
from app.models.imports import ImportBatch, ImportRow, ImportSupplierMap
from app.models.business import Supplier
from app.services.excel_reader import read_excel, MAX_UPLOAD
from app.services.excel_import import prepare_import, confirm_import, resolve_row, assign_supplier, prepared_totals
from app.services.business import clean_text
from app.services.listings import paginate
from app.web import templates

router = APIRouter(prefix="/business/imports", tags=["Importación"])


@router.get("")
def imports(request: Request, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    return templates.TemplateResponse(request=request, name="imports.html", context={
        "batches": paginate(db, select(ImportBatch).order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc()), page), "error": None})


@router.post("")
async def upload(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    workbook = form.get("workbook")
    try:
        dataset = clean_text(form.get("dataset"), "el identificador del libro", 80, True)
        if workbook is None or not hasattr(workbook, "read") or not workbook.filename.lower().endswith(".xlsx"):
            raise ValueError("Elegí un archivo XLSX")
        content = await workbook.read(MAX_UPLOAD + 1)
        parsed = await run_in_threadpool(read_excel, content, dataset)
        batch = prepare_import(db, content, dataset, workbook.filename, request.state.user.username, parsed)
    except ValueError as error:
        db.rollback()
        return templates.TemplateResponse(request=request, name="imports.html", context={
            "batches": paginate(db, select(ImportBatch).order_by(ImportBatch.created_at.desc()), 1), "error": str(error)}, status_code=422)
    return RedirectResponse(f"/business/imports/{batch.id}", status_code=303)


def get_batch(db, identifier):
    batch = db.get(ImportBatch, identifier)
    if batch is None:
        raise HTTPException(404, "Lote no encontrado")
    return batch


@router.get("/{identifier}")
def preview(identifier: str, request: Request, state: str = "candidates", page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    batch = get_batch(db, identifier)
    query = select(ImportRow).where(ImportRow.batch_id == identifier)
    if state == "candidates":
        query = query.where(ImportRow.kind.in_(["sale", "expense"]))
    elif state == "source":
        query = query.where(ImportRow.kind.in_(["source", "historical"]))
    elif state in {"review", "ready", "skipped", "imported", "already"}:
        query = query.where(ImportRow.state == state)
    else:
        raise HTTPException(422, "Elegí una vista válida")
    rows = paginate(db, query.order_by(ImportRow.sheet, ImportRow.row_number, ImportRow.slot), page)
    counts = dict(db.execute(select(ImportRow.state, func.count()).where(ImportRow.batch_id == identifier,
        ImportRow.kind.in_(["sale", "expense"])).group_by(ImportRow.state)).all())
    return templates.TemplateResponse(request=request, name="import_preview.html", context={"batch": batch,
        "rows": rows, "counts": counts, "state": state, "totals": prepared_totals(db, identifier)})


@router.post("/{identifier}/confirm")
def confirm(identifier: str, request: Request, db: Session = Depends(get_db)):
    get_batch(db, identifier)
    confirm_import(db, identifier, request.state.user.username)
    return RedirectResponse(f"/business/imports/{identifier}?confirmed=1", status_code=303)


@router.get("/{identifier}/rows/{row_id}")
def review(identifier: str, row_id: int, request: Request, db: Session = Depends(get_db)):
    row = db.get(ImportRow, row_id)
    if row is None or row.batch_id != identifier:
        raise HTTPException(404, "Fila no encontrada")
    return templates.TemplateResponse(request=request, name="import_row.html", context={"row": row, "error": None, "values": row.proposed})


@router.post("/{identifier}/rows/{row_id}")
async def save_review(identifier: str, row_id: int, request: Request, db: Session = Depends(get_db)):
    values = dict(await request.form())
    try:
        resolve_row(db, identifier, row_id, values, request.state.user.username)
    except ValueError as error:
        db.rollback()
        row = db.get(ImportRow, row_id)
        if row is None or row.batch_id != identifier:
            raise HTTPException(404, "Fila no encontrada")
        return templates.TemplateResponse(request=request, name="import_row.html", context={"row": row, "error": str(error), "values": values}, status_code=422)
    return RedirectResponse(f"/business/imports/{identifier}?state=review&reviewed=1", status_code=303)


@router.get("/{identifier}/suppliers")
def suppliers(identifier: str, request: Request, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    batch = get_batch(db, identifier)
    label = ImportRow.proposed["label"].as_string()
    labels = paginate(db, select(label).where(ImportRow.batch_id == identifier, ImportRow.kind == "expense", label != "").distinct().order_by(label), page)
    options = list(db.scalars(select(Supplier).where(Supplier.active.is_(True)).order_by(Supplier.name_key)))
    keys = {s.name_key: s.name for s in options}
    suggestions = {value: [keys[key] for key in get_close_matches(" ".join(value.casefold().split()), list(keys), n=3, cutoff=.55)] for value in labels.items}
    maps = dict(db.execute(select(ImportSupplierMap.label, ImportSupplierMap.supplier_id).where(ImportSupplierMap.batch_id == identifier)).all())
    return templates.TemplateResponse(request=request, name="import_suppliers.html", context={"batch": batch, "labels": labels,
        "suppliers": options, "maps": maps, "suggestions": suggestions})


@router.post("/{identifier}/suppliers")
async def map_supplier(identifier: str, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        assign_supplier(db, identifier, form.get("label"), form.get("supplier_id"), request.state.user.username)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return RedirectResponse(f"/business/imports/{identifier}/suppliers?saved=1", status_code=303)

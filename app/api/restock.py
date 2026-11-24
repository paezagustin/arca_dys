from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from starlette.datastructures import FormData

from app.core.database import get_db
from app.models.business import Supplier
from app.models.restock import RestockCatalogSync, RestockNeed, RestockProduct, SupplierOrder, SupplierOrderLine
from app.services import restock, restock_catalog
from app.services.listings import paginate
from app.web import templates

router = APIRouter(prefix="/faltantes", tags=["Faltantes"])

NOTICES = {"added": "Faltante registrado.", "edited": "Cambios guardados.", "cancelled": "Faltante cancelado.",
           "product": "Producto guardado.", "linked": "Asociaciones guardadas.", "ordered": "Pedido registrado.",
           "received": "Recepción guardada.", "synced": "Catálogo actualizado."}


async def form_data(request: Request):
    return await request.form()


def amount_display(value):
    return format(value.normalize(), "f").replace(".", ",") if value is not None else ""


templates.env.filters["restock_quantity"] = amount_display


def show(request, name, *, status_code=200, **context):
    return templates.TemplateResponse(request=request, name=f"restock/{name}.html", status_code=status_code,
                                      context={"need_states": restock.NEED_STATES, "order_states": restock.ORDER_STATES,
                                               "line_states": restock.LINE_STATES,
                                               "notice": NOTICES.get(request.query_params.get("aviso")), **context})


def wants_json(request):
    return "application/json" in request.headers.get("accept", "")


def write(request, db, action, notice, location, *, invalid=None, navigate=False):
    try:
        result = action()
        db.commit()
    except (ValueError, LookupError, IntegrityError) as error:
        db.rollback()
        status, message = 422, str(error)
        if isinstance(error, LookupError):
            status = 404
        if isinstance(error, (restock.Conflict, IntegrityError, restock.SimilarProducts)):
            status = 409
        if isinstance(error, IntegrityError):
            message = "Los datos cambiaron mientras guardabas. Actualizá la página y volvé a intentar."
        if wants_json(request):
            details = {"detail": message}
            if isinstance(error, restock.SimilarProducts):
                details["duplicates"] = [{"name": row.name, "presentation": row.presentation} for row in error.candidates]
            return JSONResponse(details, status_code=status)
        if invalid:
            return invalid(status, message, getattr(error, "candidates", ()))
        raise HTTPException(status, message) from None
    target = location(result) if callable(location) else location
    if wants_json(request):
        return {"message": NOTICES[notice], "url": f"{target}?aviso={notice}" if navigate else None}
    return RedirectResponse(f"{target}?aviso={notice}", status_code=303)


def search_context(db, query):
    rows, needs, orders = restock.product_search(db, query)
    return {"query": query, "matches": rows, "matched_needs": needs, "matched_orders": orders,
            "keys": {row.id: str(uuid4()) for row in rows}, "quick_key": str(uuid4())}


@router.get("")
def needs_index(request: Request, q: str = Query("", max_length=180), proveedor: str = "", estado: str = "pending",
                desde: str = Query("", max_length=10), hasta: str = Query("", max_length=10), orden: str = "oldest",
                buscar: str = Query("", max_length=180), page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    try:
        statement = restock.need_statement(q, proveedor, estado, desde, hasta, orden)
        search = search_context(db, buscar)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    rows = paginate(db, statement, page)
    pending = db.scalar(select(func.count(RestockNeed.id)).where(RestockNeed.status == "pending"))
    return show(request, "needs", section="needs", rows=rows, pending=pending, orders=restock.need_orders(db, rows.items),
                suppliers=restock.suppliers_list(db), q=q, supplier_filter=proveedor, status=estado,
                starts=desde, ends=hasta, sort=orden, **search)


@router.get("/buscar")
def search_products(q: str = Query("", max_length=180), *, request: Request, db: Session = Depends(get_db)):
    try:
        return show(request, "search_results", **search_context(db, q))
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.post("/registrar/{product_id}")
def add_need(product_id: int, request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    return write(request, db, lambda: restock.register_need(db, product_id, form), "added", "/faltantes")


@router.post("/editar/{need_id}")
def edit_need(need_id: int, request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    return write(request, db, lambda: restock.change_need(db, need_id, form), "edited", "/faltantes")


@router.post("/cancelar/{need_id}")
def cancel_need(need_id: int, request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    return write(request, db, lambda: restock.change_need(db, need_id, form, cancel=True), "cancelled", "/faltantes")


@router.get("/productos")
def products_index(request: Request, q: str = Query("", max_length=180), vinculo: str = "", estado: str = "",
                   proveedor: int | None = Query(None, ge=1, le=2147483647), page: int = Query(1, ge=1),
                   db: Session = Depends(get_db)):
    if proveedor:
        return RedirectResponse(f"/faltantes/productos/proveedores/{proveedor}", status_code=303)
    try:
        rows = paginate(db, restock.product_statement(q, vinculo, estado), page)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return show(request, "products", section="products", rows=rows, q=q, link_filter=vinculo, status=estado,
                suppliers=restock.suppliers_list(db), sync=db.get(RestockCatalogSync, restock_catalog.SOURCE),
                catalog_ready=callable(getattr(request.app.state, "restock_catalog_fetch", None)))


@router.post("/productos/sincronizar")
def sync_products(request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    fetch = getattr(request.app.state, "restock_catalog_fetch", None)
    if not callable(fetch):
        raise HTTPException(503, "La conexión con Dulce y Salado está pendiente. Podés seguir trabajando con los productos locales.")
    mode = form.get("mode", "auto")
    if mode not in {"auto", "full"}:
        raise HTTPException(422, "Elegí un tipo de sincronización válido.")
    try:
        changed = restock_catalog.synchronize(db, fetch, force_full=mode == "full")
    except restock_catalog.SyncFailed as error:
        if wants_json(request):
            raise HTTPException(502, str(error)) from None
        return RedirectResponse("/faltantes/productos", status_code=303)
    except restock.Conflict as error:
        raise HTTPException(409, str(error)) from None
    if wants_json(request):
        return {"message": NOTICES["synced"], "changed": changed}
    return RedirectResponse("/faltantes/productos?aviso=synced", status_code=303)


def product_form(request, db, row=None, form=None, *, quick=False, name="", **context):
    options = restock.suppliers_list(db)
    pending = False
    if row:
        pending = db.scalar(select(RestockNeed.id).where(RestockNeed.product_id == row.id,
                                                        RestockNeed.status.in_(restock.ACTIVE_NEEDS)).limit(1)) is not None
    relations = {link.supplier_id: link for link in row.suppliers} if row else {}
    if form is None:
        form = {"name": row.name if row else name, "description": row.description if row else "",
                "presentation": row.presentation if row else "", "barcode": row.barcode if row else "",
                "active": "1" if not row or row.active else "0", "version": row.version if row else 1,
                "request_key": str(uuid4()), "preferred": next((key for key, link in relations.items() if link.preferred), "")}
        selected = set(relations)
    else:
        selected = {option.id for option in options if str(option.id) in form.getlist("supplier_id")}
    return show(request, "product_form", section="products", row=row, values=form, quick=quick, pending=pending,
                suppliers=[option for option in options if option.active or option.id in relations], selected=selected, **context)


@router.get("/productos/nuevo")
def new_product(request: Request, faltante: bool = False, nombre: str = Query("", max_length=180), db: Session = Depends(get_db)):
    return product_form(request, db, quick=faltante, name=nombre)


def store_product(request, db, form, *, product_id=None, quick=False):
    return write(request, db, lambda: restock.save_product(db, form, form.getlist("supplier_id"),
                                                          product_id=product_id, add_need=quick),
                 "added" if quick else "product", "/faltantes" if quick else "/faltantes/productos",
                 invalid=lambda status, message, candidates: product_form(request, db, db.get(RestockProduct, product_id)
                     if product_id else None, form, quick=quick, error=message, duplicates=candidates, status_code=status))


@router.post("/productos/nuevo")
def create_product(request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    return store_product(request, db, form)


@router.post("/productos/rapido")
def quick_product(request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    return store_product(request, db, form, quick=True)


@router.get("/productos/proveedores/{supplier_id}")
def supplier_products(supplier_id: int, request: Request, q: str = Query("", max_length=180), todos: bool = False,
                      page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(404, "Proveedor no encontrado")
    try:
        rows = paginate(db, restock.product_statement(q, supplier_id=None if todos else supplier_id), page)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    linked = {row.id for row in rows.items if any(link.supplier_id == supplier_id for link in row.suppliers)}
    return show(request, "supplier_products", section="products", supplier=supplier, rows=rows, linked=linked, q=q, all_products=todos)


@router.post("/productos/proveedores/{supplier_id}")
def link_products(supplier_id: int, request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    return write(request, db, lambda: restock.add_supplier_products(db, supplier_id, form.getlist("product_id")),
                 "linked", f"/faltantes/productos/proveedores/{supplier_id}")


@router.get("/productos/{product_id}")
def product_detail(product_id: int, request: Request, db: Session = Depends(get_db)):
    row = db.get(RestockProduct, product_id)
    if row is None:
        raise HTTPException(404, "Producto no encontrado")
    return product_form(request, db, row)


@router.post("/productos/{product_id}")
def update_product(product_id: int, request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    return store_product(request, db, form, product_id=product_id)


@router.get("/pedidos")
def orders_index(request: Request, proveedor: int | None = Query(None, ge=1, le=2147483647), db: Session = Depends(get_db)):
    suppliers = restock.suppliers_list(db, active_only=True)
    supplier = next((row for row in suppliers if row.id == proveedor), None)
    return show(request, "orders", section="orders", suppliers=suppliers, supplier=supplier, requested_supplier=proveedor,
                rows=restock.eligible_needs(db, supplier.id) if supplier else (), request_key=str(uuid4()),
                whatsapp=restock.whatsapp_destination(supplier.contact) if supplier else "")


@router.post("/pedidos/{supplier_id}")
def create_order(supplier_id: int, request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    def register():
        if form.get("confirmed") != "1":
            raise ValueError("Confirmá que ya realizaste el pedido al proveedor")
        selections = []
        for value in form.getlist("need_id"):
            identifier = restock.positive_id(value)
            suffix = f"_{identifier}"
            selections.append(restock.Selection(identifier, restock.positive_id(form.get("version" + suffix)),
                restock.positive_id(form.get("product_version" + suffix)), restock.purchase_fields(form, suffix)))
        return restock.register_order(db, supplier_id, form, selections)
    return write(request, db, register, "ordered", lambda order: f"/faltantes/historial/{order.id}", navigate=True)


@router.get("/historial")
def history_index(request: Request, q: str = Query("", max_length=180), proveedor: str = "", estado: str = "",
                  desde: str = Query("", max_length=10), hasta: str = Query("", max_length=10),
                  page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    try:
        rows = paginate(db, restock.order_history(q, proveedor, estado, desde, hasta), page, scalars=False)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return show(request, "history", section="history", rows=rows, suppliers=restock.suppliers_list(db), q=q,
                supplier_filter=proveedor, status=estado, starts=desde, ends=hasta)


@router.get("/historial/{order_id}")
def order_detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    status = select(restock.order_counts()[1]).where(SupplierOrderLine.order_id == SupplierOrder.id).scalar_subquery()
    result = db.execute(select(SupplierOrder, status).options(joinedload(SupplierOrder.lines))
                        .where(SupplierOrder.id == order_id)).unique().one_or_none()
    if result is None:
        raise HTTPException(404, "Pedido no encontrado")
    row, status = result
    return show(request, "order", section="history", row=row, status=status)


@router.post("/historial/{order_id}/recepcion")
def save_receipt(order_id: int, request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db)):
    return write(request, db, lambda: restock.receive_order(db, order_id, form), "received",
                 f"/faltantes/historial/{order_id}", navigate=True)

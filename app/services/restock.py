"""Operaciones y consultas de reposición, independientes de stock y facturación."""
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.billing import utcnow
from app.models.business import Supplier
from app.models.restock import RestockNeed, RestockProduct, RestockProductSupplier, SupplierOrder, SupplierOrderLine
from app.services.business import check_version, clean_text, record_date
from app.utils.text import normalized

NEED_STATES = {"pending": "Pendiente", "ordered": "Pedido", "received": "Recibido", "cancelled": "Cancelado"}
ORDER_STATES = {"waiting": "Pendiente de recepción", "partial": "Recibido parcialmente",
                "received": "Recibido completamente", "short": "Cerrado con faltantes", "cancelled": "Cancelado"}
LINE_STATES = {"waiting": "Pendiente de entrega", "received": "Recibido",
               "undelivered": "No entregado", "cancelled": "Cancelado"}
ACTIVE_NEEDS = ("pending", "ordered")
FINAL_OUTCOMES = ("received", "undelivered", "cancelled")
LOCAL_ZONE = ZoneInfo("America/Argentina/Buenos_Aires")


class Conflict(ValueError):
    pass


class SimilarProducts(ValueError):
    def __init__(self, candidates):
        self.candidates = candidates
        super().__init__("Hay productos con el mismo nombre o código de barras. Revisá las presentaciones antes de guardar.")


def checked_text(value, label, limit, required=False):
    value = clean_text(value, label, limit, required)
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value):
        raise ValueError(f"Revisá {label}: contiene caracteres no válidos")
    return value


def positive_id(value):
    value = str(value)
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) > 2147483647:
        raise ValueError("Revisá la selección y volvé a abrir el formulario")
    return int(value)


def request_key(db, value):
    try:
        key = str(UUID(str(value)))
    except (ValueError, TypeError):
        raise ValueError("Reabrí el formulario antes de guardar") from None
    db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended("restock:" + key, 0))))
    return key


def require_version(row, version):
    try:
        check_version(row, version)
    except ValueError as error:
        raise Conflict(str(error)) from error


def product_fields(values, *, from_catalog=False, previous=None):
    name = checked_text(values.get("name"), "el nombre", 180, required=True)
    description = checked_text(values.get("description", previous.description if previous else ""),
                               "la descripción", 65536 if from_catalog else 4000)
    presentation = checked_text(values.get("presentation", previous.presentation if previous else ""), "la presentación", 160)
    barcode = checked_text(values.get("barcode"), "el código de barras", 100)
    searchable = f"{name} {presentation} {barcode}"
    if from_catalog and description:
        searchable = f"{searchable} {description}"
    return dict(name=name, name_key=normalized(name), description=description, presentation=presentation,
                barcode=barcode, search_text=normalized(searchable))


def purchase_fields(values, suffix=""):
    raw = str(values.get("quantity" + suffix, "")).strip().replace(",", ".")
    quantity = None
    if raw:
        try:
            if not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,3})?", raw):
                raise ValueError()
            quantity = Decimal(raw).quantize(Decimal("0.001"))
            if quantity <= 0:
                raise ValueError()
        except (ValueError, InvalidOperation):
            raise ValueError("Ingresá una cantidad positiva de hasta 9 enteros y 3 decimales, o dejala vacía") from None
    fields = dict(quantity=quantity, notes=checked_text(values.get("notes" + suffix), "las observaciones", 1000))
    if "unit" + suffix in values:
        fields["unit"] = checked_text(values["unit" + suffix], "la unidad", 160)
    return fields


def matching(column, query):
    query = checked_text(query, "la búsqueda", 180)
    return [column.contains(term, autoescape=True) for term in normalized(query).split()]


def date_conditions(column, starts, ends):
    start = record_date(starts) if starts else None
    end = record_date(ends) if ends else None
    if (start and start.year < 1900) or (end and end.year < 1900):
        raise ValueError("Ingresá fechas a partir de 1900")
    if start and end and start > end:
        raise ValueError("La fecha desde no puede ser posterior a la fecha hasta")
    conditions = []
    if start:
        conditions.append(column >= datetime.combine(start, time.min, LOCAL_ZONE))
    if end:
        conditions.append(column <= datetime.combine(end, time.max, LOCAL_ZONE))
    return conditions


def suppliers_list(db, *, active_only=False):
    query = select(Supplier).order_by(Supplier.name_key, Supplier.id)
    if active_only:
        query = query.where(Supplier.active.is_(True))
    return list(db.scalars(query))


def supplier_search(db, q, *, active_only, excluded=()):
    words = normalized(checked_text(q, "el proveedor", 150)).split()
    query = select(Supplier.id, Supplier.name, Supplier.active).order_by(Supplier.name_key, Supplier.id)
    if active_only:
        query = query.where(Supplier.active.is_(True))
    if excluded:
        query = query.where(Supplier.id.not_in([positive_id(value) for value in excluded]))
    if not words:
        return db.execute(query.limit(20)).all()
    matches = []
    for row in db.execute(query.execution_options(yield_per=100)):
        name = normalized(row.name)
        if all(word in name for word in words):
            matches.append(row)
            if len(matches) == 20:
                break
    return matches


def supplier_link(supplier_id):
    return select(RestockProductSupplier.product_id).where(
        RestockProductSupplier.product_id == RestockProduct.id,
        RestockProductSupplier.supplier_id == supplier_id,
    ).exists()


def has_active_supplier():
    return select(RestockProductSupplier.product_id).join(Supplier).where(
        RestockProductSupplier.product_id == RestockProduct.id, Supplier.active.is_(True),
    ).exists()


def association_options():
    return selectinload(RestockProduct.suppliers).joinedload(RestockProductSupplier.supplier)


def available_product():
    return RestockProduct.active.is_(True) & or_(RestockProduct.catalog_status.is_(None),
                                                RestockProduct.catalog_status == "active")


def product_conditions(q, product_id):
    if product_id is not None:
        return [RestockProduct.id == product_id]
    return matching(RestockProduct.search_text, q)


def product_statement(q="", links="", status="", supplier_id=None, *, product_id=None):
    query = select(RestockProduct).options(association_options()).where(*product_conditions(q, product_id))
    if links not in {"", "with", "without"} or status not in {"", "active", "archived"}:
        raise ValueError("Elegí un filtro de productos válido")
    if links:
        query = query.where(has_active_supplier() if links == "with" else ~has_active_supplier())
    if status:
        available = available_product()
        query = query.where(available if status == "active" else ~available)
    if supplier_id:
        query = query.where(supplier_link(supplier_id))
    return query.order_by(RestockProduct.name_key, RestockProduct.presentation, RestockProduct.id)


def product_search(db, q, *, include_archived=False):
    if not normalized(q):
        return []
    query = select(RestockProduct.id, RestockProduct.name, RestockNeed.status).outerjoin(
        RestockNeed, (RestockNeed.product_id == RestockProduct.id) & RestockNeed.status.in_(ACTIVE_NEEDS)
    ).where(*matching(RestockProduct.search_text, q)).order_by(RestockProduct.name_key, RestockProduct.id).limit(20)
    if not include_archived:
        query = query.where(available_product())
    return list(db.execute(query))


def save_product(db, values, supplier_ids=(), *, product_id=None, add_need=False):
    ids = sorted({positive_id(value) for value in supplier_ids})
    preferred = positive_id(values["preferred"]) if values.get("preferred") else None
    if preferred is not None and preferred not in ids:
        raise ValueError("Asociá primero el proveedor que querés marcar como preferido")
    key = request_key(db, values.get("request_key")) if product_id is None else None
    if key:
        previous = db.scalar(select(RestockProduct).where(RestockProduct.request_key == key))
        if previous:
            if add_need and db.scalar(select(RestockNeed.id).where(RestockNeed.request_key == key,
                                                                   RestockNeed.product_id == previous.id)) is None:
                raise Conflict("Este formulario ya se usó. Buscá el producto para registrar el faltante")
            return previous

    suppliers = {row.id: row for row in db.scalars(select(Supplier).where(Supplier.id.in_(ids))
                                                  .order_by(Supplier.id).with_for_update(read=True))} if ids else {}
    if len(suppliers) != len(ids):
        raise Conflict("Algún proveedor ya no está disponible. Volvé a abrir la ficha")
    row = db.get(RestockProduct, product_id, with_for_update=True) if product_id else None
    if product_id and row is None:
        raise LookupError("Producto no encontrado")
    if row:
        require_version(row, values.get("version"))
    fields = product_fields(values, previous=row) if not row or not row.source else {}
    if fields and (not row or row.name_key != fields["name_key"] or row.barcode != fields["barcode"]):
        criteria = RestockProduct.name_key == fields["name_key"]
        if fields["barcode"]:
            criteria = or_(criteria, RestockProduct.barcode == fields["barcode"])
        candidates = select(RestockProduct).where(criteria).order_by(RestockProduct.name_key, RestockProduct.id)
        if row:
            candidates = candidates.where(RestockProduct.id != row.id)
        if values.get("allow_duplicate") != "1" and (matches := list(db.scalars(candidates.limit(8)))):
            raise SimilarProducts(matches)

    existing = {link.supplier_id: link for link in row.suppliers} if row else {}
    if "preferred" not in values:
        preferred = next((identifier for identifier, link in existing.items() if link.preferred and identifier in suppliers), None)
    if any(not supplier.active and identifier not in existing for identifier, supplier in suppliers.items()):
        raise Conflict("Solo podés sumar proveedores activos")
    if row is None:
        row = RestockProduct(request_key=key, **fields)
        db.add(row)
    else:
        if "active" in values:
            row.active = product_active(values["active"])
        for field, value in fields.items():
            setattr(row, field, value)
        row.version += 1

    # Liberar el índice parcial antes de asignar otro proveedor preferido.
    for identifier, link in existing.items():
        if identifier not in suppliers:
            db.delete(link)
        elif identifier != preferred and link.preferred:
            link.preferred = False
    db.flush()
    for identifier in ids:
        if identifier not in existing:
            db.add(RestockProductSupplier(product_id=row.id, supplier_id=identifier, preferred=identifier == preferred))
        elif identifier == preferred:
            existing[identifier].preferred = True
    if add_need:
        db.add(RestockNeed(product_id=row.id, request_key=key, **purchase_fields(values)))
    return row


def product_active(value):
    if value not in {"0", "1"}:
        raise ValueError("Elegí un estado válido para el producto")
    return value == "1"


def set_product_active(db, product_id, values):
    row = db.get(RestockProduct, product_id, with_for_update=True)
    if row is None:
        raise LookupError("Producto no encontrado")
    require_version(row, values.get("version"))
    active = product_active(values.get("active"))
    if row.active != active:
        row.active = active
        row.version += 1


def add_supplier_products(db, supplier_id, selections):
    supplier = db.get(Supplier, supplier_id, with_for_update={"read": True})
    if supplier is None:
        raise LookupError("Proveedor no encontrado")
    if not supplier.active:
        raise Conflict("Este proveedor está archivado")
    ids = {positive_id(value) for value in selections}
    if not ids:
        raise ValueError("Seleccioná al menos un producto")
    products = list(db.scalars(select(RestockProduct).where(RestockProduct.id.in_(ids))
                              .order_by(RestockProduct.id).with_for_update()))
    if len(products) != len(ids):
        raise Conflict("Algún producto ya no existe. Volvé a abrir el listado")
    linked = set(db.scalars(select(RestockProductSupplier.product_id).where(
        RestockProductSupplier.supplier_id == supplier_id, RestockProductSupplier.product_id.in_(ids))))
    for product in products:
        if product.id not in linked:
            db.add(RestockProductSupplier(product_id=product.id, supplier_id=supplier_id))
            product.version += 1
    return len(ids - linked)


def set_supplier_preference(db, supplier_id, product_id, values):
    desired = values.get("preferred")
    if desired not in {"0", "1"}:
        raise ValueError("Elegí una preferencia válida")
    supplier = db.get(Supplier, supplier_id, with_for_update={"read": True})
    product = db.get(RestockProduct, product_id, with_for_update=True)
    if supplier is None or product is None:
        raise LookupError("Producto o proveedor no encontrado")
    require_version(product, values.get("version"))
    link = db.get(RestockProductSupplier, (product_id, supplier_id))
    if link is None or (desired == "1" and not supplier.active):
        raise Conflict("Revisá los proveedores asociados antes de cambiar la preferencia")
    if link.preferred != (desired == "1"):
        if desired == "1":
            for previous in product.suppliers:
                if previous.preferred:
                    previous.preferred = False
            db.flush()
        link.preferred = desired == "1"
        product.version += 1


def need_orders(db, needs):
    ids = [row.id for row in needs if row.status in {"ordered", "received"}]
    if not ids:
        return {}
    return {identifier: order for identifier, order in db.execute(
        select(SupplierOrderLine.need_id, SupplierOrder).join(SupplierOrder).where(
            SupplierOrderLine.need_id.in_(ids), SupplierOrderLine.outcome.in_(("waiting", "received"))))}


def register_need(db, product_id, values):
    key = request_key(db, values.get("request_key"))
    details = purchase_fields(values)
    product = db.get(RestockProduct, product_id, with_for_update=True)
    if product is None:
        raise LookupError("Producto no encontrado")
    previous = db.scalar(select(RestockNeed).where(RestockNeed.request_key == key))
    if previous and (previous.product_id != product_id or previous.status not in ACTIVE_NEEDS):
        raise Conflict("Este formulario ya se usó. Actualizá la lista para registrar un nuevo faltante")
    existing = previous or db.scalar(select(RestockNeed).where(RestockNeed.product_id == product_id,
                                                                RestockNeed.status.in_(ACTIVE_NEEDS)))
    if existing:
        order = need_orders(db, [existing]).get(existing.id)
        if order:
            raise Conflict(f"{product.name} ya fue pedido a {order.supplier_name} (pedido #{order.id}).")
        day = existing.created_at.astimezone(LOCAL_ZONE).strftime("%d/%m/%Y")
        raise Conflict(f"{product.name} ya está pendiente desde el {day}.")
    if not product.available:
        raise Conflict("El producto está archivado o fuera del catálogo. Revisá su ficha")
    row = RestockNeed(product_id=product_id, request_key=key, **details)
    db.add(row)
    return row


def change_need(db, need_id, values, *, cancel=False):
    row = db.get(RestockNeed, need_id, with_for_update=True)
    if row is None:
        raise LookupError("Faltante no encontrado")
    if row.status != "pending":
        raise Conflict("El faltante ya cambió de estado. Revisá la lista actualizada")
    require_version(row, values.get("version"))
    if cancel:
        row.status = "cancelled"
    else:
        for field, value in purchase_fields(values).items():
            setattr(row, field, value)
    row.version += 1


def need_statement(q="", supplier="", status="pending", starts="", ends="", sort="oldest", *, product_id=None):
    if status not in {"all", *NEED_STATES} or sort not in {"oldest", "newest", "name"}:
        raise ValueError("Elegí filtros y orden válidos")
    query = select(RestockNeed).join(RestockProduct).options(joinedload(RestockNeed.product).options(association_options())).where(
        *product_conditions(q, product_id), *date_conditions(RestockNeed.created_at, starts, ends))
    if status != "all":
        query = query.where(RestockNeed.status == status)
    if supplier == "none":
        query = query.where(~has_active_supplier())
    elif supplier:
        identifier = positive_id(supplier)
        associated = supplier_link(identifier)
        ordered_by_supplier = select(SupplierOrderLine.id).join(SupplierOrder).where(
            SupplierOrderLine.need_id == RestockNeed.id, SupplierOrderLine.outcome.in_(("waiting", "received")),
            SupplierOrder.supplier_id == identifier).exists()
        query = query.where(or_(RestockNeed.status.in_(("pending", "cancelled")) & associated,
                                RestockNeed.status.in_(("ordered", "received")) & ordered_by_supplier))
    if sort == "name":
        return query.order_by(RestockProduct.name_key, RestockNeed.id)
    if sort == "newest":
        return query.order_by(RestockNeed.created_at.desc(), RestockNeed.id.desc())
    return query.order_by(RestockNeed.created_at, RestockNeed.id)


def eligible_needs(db, supplier_id):
    query = (select(RestockNeed).join(RestockProduct)
             .options(joinedload(RestockNeed.product).options(association_options()))
             .where(RestockNeed.status == "pending", supplier_link(supplier_id))
             .order_by(RestockProduct.name_key, RestockProduct.presentation, RestockNeed.id))
    return list(db.scalars(query))


@dataclass(frozen=True)
class Selection:
    need_id: int
    version: int
    product_version: int
    purchase: dict


def register_order(db, supplier_id, values, selections):
    if not selections:
        raise ValueError("Seleccioná al menos un faltante para registrar el pedido")
    selections = sorted(selections, key=lambda row: row.need_id)
    if len({row.need_id for row in selections}) != len(selections):
        raise ValueError("Seleccioná cada faltante una sola vez")
    key = request_key(db, values.get("request_key"))
    notes = checked_text(values.get("order_notes"), "las observaciones del pedido", 1000)
    supplier_version = positive_id(values.get("supplier_version"))
    digest = sha256(json.dumps([supplier_id, supplier_version, notes, [vars(row) for row in selections]],
                               sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
    previous = db.scalar(select(SupplierOrder).where(SupplierOrder.request_key == key))
    if previous:
        if previous.request_hash != digest:
            raise Conflict("Este formulario ya registró otro pedido. Revisá el historial")
        return previous

    supplier = db.get(Supplier, supplier_id, with_for_update={"read": True})
    if not supplier or not supplier.active:
        raise Conflict("El proveedor ya no está activo. Elegí otro proveedor")
    require_version(supplier, supplier_version)
    ids = [row.need_id for row in selections]
    products = {row.id: row for row in db.scalars(select(RestockProduct).where(RestockProduct.id.in_(
        select(RestockNeed.product_id).where(RestockNeed.id.in_(ids)))).order_by(RestockProduct.id).with_for_update())}
    needs = {row.id: row for row in db.scalars(select(RestockNeed).where(RestockNeed.id.in_(ids))
                                              .order_by(RestockNeed.id).with_for_update())}
    linked = set(db.scalars(select(RestockProductSupplier.product_id).where(
        RestockProductSupplier.supplier_id == supplier_id, RestockProductSupplier.product_id.in_(products))))
    for selection in selections:
        need = needs.get(selection.need_id)
        if not need or need.status != "pending" or need.product_id not in linked:
            raise Conflict("Uno o más faltantes ya fueron pedidos, cancelados o desvinculados. Revisá la lista actualizada antes de registrar")
        if need.version != selection.version or products[need.product_id].version != selection.product_version:
            raise Conflict("Uno o más productos cambiaron mientras preparabas el pedido. Revisá la lista actualizada")

    order = SupplierOrder(request_key=key, request_hash=digest, supplier_id=supplier.id,
                          supplier_name=supplier.name, notes=notes)
    db.add(order)
    for selection in selections:
        need = needs[selection.need_id]
        product = products[need.product_id]
        purchase = {"unit": need.unit, **selection.purchase}
        order.lines.append(SupplierOrderLine(need_id=need.id, product_name=product.name,
                                             product_description=product.description if product.source and product.description else None,
                                             presentation=product.presentation, barcode=product.barcode,
                                             search_text=product.search_text, **purchase))
        need.status = "ordered"
        need.version += 1
    return order


def receive_order(db, order_id, values):
    order = db.get(SupplierOrder, order_id, with_for_update=True)
    if order is None:
        raise LookupError("Pedido no encontrado")
    if order.closed_at:
        raise Conflict("El pedido ya está cerrado. Consultá el historial")
    require_version(order, values.get("version"))
    waiting = {row.id: row for row in order.lines if row.outcome == "waiting"}
    actions = {}
    for key, action in values.items():
        if not key.startswith("outcome_"):
            continue
        line_id = positive_id(key.removeprefix("outcome_"))
        if line_id not in waiting or action not in {"waiting", *FINAL_OUTCOMES}:
            raise ValueError("Revisá los resultados de recepción")
        notes = checked_text(values.get(f"receipt_{line_id}"), "las observaciones de recepción", 1000)
        if action != "waiting" or notes != waiting[line_id].receipt_notes:
            actions[line_id] = action, notes
    if not actions:
        raise ValueError("Elegí un resultado o agregá una observación para guardar la recepción")
    ids = [waiting[identifier].need_id for identifier, (action, _) in actions.items() if action != "waiting"]
    needs = {row.id: row for row in db.scalars(select(RestockNeed).where(RestockNeed.id.in_(ids))
                                              .order_by(RestockNeed.id).with_for_update())}
    if len(needs) != len(ids) or any(need.status != "ordered" for need in needs.values()):
        raise Conflict("Algún faltante cambió de estado. Volvé a abrir el pedido")
    now = utcnow()
    for identifier, (action, notes) in actions.items():
        line = waiting[identifier]
        line.receipt_notes = notes
        if action != "waiting":
            line.outcome = action
            line.resolved_at = now
            need = needs[line.need_id]
            need.status = "received" if action == "received" else "pending"
            need.version += 1
    if all(line.outcome != "waiting" for line in order.lines):
        order.closed_at = now
    order.version += 1
    return order


def order_status(waiting, received, cancelled, total):
    return case((waiting > 0, case((received > 0, "partial"), else_="waiting")),
                (received == total, "received"), (cancelled == total, "cancelled"), else_="short")


def order_counts():
    line = SupplierOrderLine
    total = func.count(line.id)
    status = order_status(func.count().filter(line.outcome == "waiting"),
                          func.count().filter(line.outcome == "received"),
                          func.count().filter(line.outcome == "cancelled"), total)
    return total.label("line_count"), status.label("status")


def order_history(q, supplier, status, starts, ends, *, product_id=None):
    if status and status not in ORDER_STATES:
        raise ValueError("Elegí un estado de pedido válido")
    query = select(SupplierOrder).where(*date_conditions(SupplierOrder.created_at, starts, ends))
    if supplier:
        query = query.where(SupplierOrder.supplier_id == positive_id(supplier))
    line = SupplierOrderLine
    if product_id is not None:
        query = query.where(select(line.id).join(RestockNeed, RestockNeed.id == line.need_id).where(
            line.order_id == SupplierOrder.id, RestockNeed.product_id == product_id).exists())
    elif terms := matching(line.search_text, q):
        query = query.where(select(line.id).where(line.order_id == SupplierOrder.id, *terms).exists())
    stats = select(line.order_id, *order_counts()).group_by(line.order_id).subquery()
    query = query.add_columns(stats.c.line_count, stats.c.status).join(stats, stats.c.order_id == SupplierOrder.id)
    if status:
        query = query.where(stats.c.status == status)
    return query.order_by(SupplierOrder.created_at.desc(), SupplierOrder.id.desc())


def whatsapp_destination(contact):
    # El contacto existente es libre. Aceptar un número único con formato reconocible.
    raw = re.sub(r"^(?:whatsapp|celular|tel[eé]fono)\s*:?\s*", "", contact.strip(), flags=re.IGNORECASE)
    if not re.fullmatch(r"\+?[0-9() .-]+", raw):
        return ""
    digits = re.sub(r"[^0-9]", "", raw)
    if raw.startswith("+") and re.fullmatch(r"[1-9][0-9]{7,14}", digits):
        return digits
    if re.fullmatch(r"549[1-9][0-9]{9}", digits):
        return digits
    if re.fullmatch(r"[1-9][0-9]{9}", digits):
        return "549" + digits
    return ""

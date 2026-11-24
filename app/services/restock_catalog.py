"""Proyección local del catálogo y control del alcance de cada sincronización."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from sqlalchemy import func, select

from app.models.billing import utcnow
from app.models.restock import RestockCatalogSync, RestockProduct
from app.services.restock import Conflict, checked_text, product_fields

SOURCE = "dulce-salado"
FULL_INTERVAL = timedelta(days=7)
OVERLAP = timedelta(minutes=5)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogCategory:
    id: int
    name: str
    active: bool


@dataclass(frozen=True)
class CatalogProduct:
    external_id: str
    name: str
    presentation: str = ""
    description: str = ""
    barcode: str = ""
    active: bool = True
    category: CatalogCategory | None = None


@dataclass(frozen=True)
class CatalogQuery:
    # Sin límite temporal implica enumerar y reconciliar todo el catálogo.
    updated_since: datetime | None
    known_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CatalogSnapshot:
    products: tuple[CatalogProduct, ...]
    # True solo para una enumeración íntegra y verificada del catálogo.
    complete: bool = False


class SyncFailed(ValueError):
    pass


class CatalogReadError(ValueError):
    """Un error de transporte con un mensaje que puede ver el operador."""


def apply_snapshot(db, snapshot):
    incoming = {}
    if not isinstance(snapshot, CatalogSnapshot) or type(snapshot.complete) is not bool:
        raise ValueError("La copia del catálogo no es válida")
    for item in snapshot.products:
        if not isinstance(item, CatalogProduct) or not isinstance(item.external_id, str) or type(item.active) is not bool:
            raise ValueError("Hay fichas con identidad o estado inválidos")
        identifier = checked_text(item.external_id, "el ID externo", 160, required=True)
        if identifier != item.external_id or identifier in incoming:
            raise ValueError("Hay IDs externos repetidos o inválidos")
        category = item.category
        incoming[identifier] = {
            **product_fields(vars(item), from_catalog=True),
            "catalog_status": "active" if item.active and (category is None or category.active) else "inactive",
            "catalog_product_active": item.active,
            "catalog_category_id": category.id if category else None,
            "catalog_category_name": category.name if category else None,
            "catalog_category_active": category.active if category else None,
        }

    query = select(RestockProduct).where(RestockProduct.source == SOURCE)
    if not snapshot.complete:
        query = query.where(RestockProduct.external_id.in_(incoming))
    existing = {row.external_id: row for row in db.scalars(query.order_by(RestockProduct.id).with_for_update())}
    changes = 0
    for identifier, fields in incoming.items():
        row = existing.get(identifier)
        if row is None:
            db.add(RestockProduct(source=SOURCE, external_id=identifier, **fields))
        elif any(getattr(row, key) != value for key, value in fields.items()):
            for key, value in fields.items():
                setattr(row, key, value)
            row.version += 1
        else:
            continue
        changes += 1
    if snapshot.complete:
        for identifier in existing.keys() - incoming.keys():
            row = existing[identifier]
            if row.catalog_status != "missing":
                row.catalog_status = "missing"
                row.version += 1
                changes += 1
    db.flush()
    return changes


def synchronize(db, fetch_snapshot, *, force_full=False):
    """Ejecutar una lectura por vez y conservar la copia anterior ante un fallo."""
    if not db.scalar(select(func.pg_try_advisory_xact_lock(func.hashtextextended("restock:catalog:" + SOURCE, 0)))):
        raise Conflict("Ya hay una sincronización en curso. Volvé a intentar en un momento")
    state = db.get(RestockCatalogSync, SOURCE)
    if state is None:
        state = RestockCatalogSync(source=SOURCE)
        db.add(state)
    started_at = utcnow()
    state.last_attempt_at = started_at
    full = (force_full or state.watermark is None or state.last_full_sync_at is None
            or started_at - state.last_full_sync_at >= FULL_INTERVAL)
    known_ids = frozenset(db.scalars(select(RestockProduct.external_id).where(RestockProduct.source == SOURCE))) if full else frozenset()
    query = CatalogQuery(None if full else state.watermark - OVERLAP, known_ids)
    try:
        with db.begin_nested():
            snapshot = fetch_snapshot(query)
            if not isinstance(snapshot, CatalogSnapshot) or snapshot.complete is not full:
                raise ValueError("El alcance de la respuesta del catálogo no coincide")
            changed = apply_snapshot(db, snapshot)
    except Exception as error:
        logger.warning("Falló la sincronización del catálogo | tipo=%s", type(error).__name__)
        reason = str(error) if isinstance(error, CatalogReadError) else "No se pudo actualizar el catálogo."
        state.last_error = f"{reason} Se conserva la última copia local."
        db.commit()
        raise SyncFailed(state.last_error) from None
    state.last_success_at = utcnow()
    state.watermark = started_at
    if full:
        state.last_full_sync_at = state.last_success_at
    state.last_error = None
    db.commit()
    return changed

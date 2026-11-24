"""Proyección local del catálogo. El cliente HTTP depende del contrato pendiente."""
from dataclasses import dataclass
import logging

from sqlalchemy import func, select

from app.models.billing import utcnow
from app.models.restock import RestockCatalogSync, RestockProduct
from app.services.restock import Conflict, checked_text, product_fields

SOURCE = "dulce-salado"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogProduct:
    external_id: str
    name: str
    presentation: str = ""
    description: str = ""
    barcode: str = ""
    active: bool = True


@dataclass(frozen=True)
class CatalogSnapshot:
    products: tuple[CatalogProduct, ...]
    # True solo para una enumeración íntegra y verificada del catálogo.
    complete: bool = False


class SyncFailed(ValueError):
    pass


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
        incoming[identifier] = {**product_fields(vars(item)), "catalog_status": "active" if item.active else "inactive"}

    existing = {row.external_id: row for row in db.scalars(select(RestockProduct).where(RestockProduct.source == SOURCE)
                                                         .order_by(RestockProduct.id).with_for_update())}
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


def synchronize(db, fetch_snapshot):
    """Ejecutar una lectura por vez y conservar la copia anterior ante un fallo."""
    if not db.scalar(select(func.pg_try_advisory_xact_lock(func.hashtextextended("restock:catalog:" + SOURCE, 0)))):
        raise Conflict("Ya hay una sincronización en curso. Volvé a intentar en un momento")
    state = db.get(RestockCatalogSync, SOURCE)
    if state is None:
        state = RestockCatalogSync(source=SOURCE)
        db.add(state)
    state.last_attempt_at = utcnow()
    try:
        with db.begin_nested():
            changed = apply_snapshot(db, fetch_snapshot())
    except Exception as error:
        logger.warning("Falló la sincronización del catálogo | tipo=%s", type(error).__name__)
        state.last_error = "No se pudo actualizar el catálogo. Se conserva la última copia local."
        db.commit()
        raise SyncFailed(state.last_error) from None
    state.last_success_at = utcnow()
    state.last_error = None
    db.commit()
    return changed

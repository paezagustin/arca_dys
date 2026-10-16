from collections import defaultdict
from decimal import Decimal
from pathlib import PureWindowsPath
from uuid import uuid4
from sqlalchemy import select, text, func
from sqlalchemy.exc import IntegrityError
from app.models.imports import ImportBatch, ImportRow, ImportSupplierMap
from app.models.business import BusinessEntry, Supplier
from app.models.billing import utcnow
from app.services.business import money, record_date, clean_text, audit
from app.services.excel_reader import digest


def import_lock(db):
    db.execute(text("SELECT pg_advisory_xact_lock(72423, 1)"))


def prepare_import(db, content, dataset, filename, actor, parsed):
    dataset = clean_text(dataset, "el identificador del libro", 80, True)
    import_lock(db)
    from hashlib import sha256
    file_hash = sha256(content).hexdigest()
    existing = db.scalar(select(ImportBatch).where(ImportBatch.dataset == dataset, ImportBatch.file_hash == file_hash))
    if existing:
        return existing
    rows, report = parsed
    batch = ImportBatch(id=str(uuid4()), dataset=dataset, file_hash=file_hash,
        filename=PureWindowsPath(filename).name[:200], state="preview", report=report, actor=actor)
    db.add(batch)
    db.flush()
    for row in rows:
        db.add(ImportRow(batch_id=batch.id, **row))
    db.commit()
    return batch


def batch_or_error(db, identifier):
    row = db.get(ImportBatch, identifier)
    if row is None:
        raise ValueError("Lote no encontrado")
    return row


def normalized_proposal(proposed):
    kind = proposed.get("kind")
    if kind not in {"sale", "expense"}:
        raise ValueError("Tipo de fila no importable")
    return {"kind": kind, "entry_date": record_date(proposed.get("entry_date")),
        "amount": money(proposed.get("amount"), allow_zero=kind == "sale"),
        "category": "Ventas" if kind == "sale" else clean_text(proposed.get("category"), "la categoría", 100, True),
        "medium": "mixed" if kind == "sale" else "unspecified",
        "description": clean_text(proposed.get("description"), "la descripción", 2000),
        "classification": clean_text(proposed.get("classification"), "la clasificación", 100)}


def confirm_import(db, identifier, actor):
    import_lock(db)
    batch = batch_or_error(db, identifier)
    rows = list(db.scalars(select(ImportRow).where(ImportRow.batch_id == identifier, ImportRow.state == "ready").order_by(ImportRow.id)))
    maps = dict(db.execute(select(ImportSupplierMap.label, ImportSupplierMap.supplier_id).where(ImportSupplierMap.batch_id == identifier)).all())
    for row in rows:
        previous = db.scalar(select(ImportRow).where(ImportRow.source_key == row.source_key,
            ImportRow.state == "imported", ImportRow.id != row.id).order_by(ImportRow.id).limit(1))
        if previous:
            if previous.fingerprint == row.fingerprint:
                row.state, row.entry_id = "already", previous.entry_id
                row.issue = "Este origen ya fue importado; no se volvió a sumar"
            else:
                row.state, row.issue = "review", "El origen ya tiene otros valores importados. Revisá y corregí el registro existente; luego omití esta fila con un motivo."
                row.resolution = dict(row.resolution or {}, existing_entry_id=previous.entry_id)
            continue
        try:
            data = normalized_proposal(row.proposed)
            supplier_id = maps.get(row.proposed.get("label", "")) if row.kind == "expense" else None
            if supplier_id and not db.get(Supplier, supplier_id).active:
                raise ValueError("El proveedor elegido fue archivado. Revisá la asignación")
            # La base resuelve también la carrera con una venta manual concurrente.
            with db.begin_nested():
                entry = BusinessEntry(entry_key="excel:" + row.source_key, origin="excel", active=True, version=1,
                    supplier_id=supplier_id, **data)
                db.add(entry)
                audit(db, entry, actor, f"Importación {identifier} · {row.sheet}!{row.slot}{row.row_number}", None)
                row.state, row.entry_id, row.issue = "imported", entry.id, None
                db.flush()
        except (ValueError, IntegrityError) as error:
            row.state = "review"
            row.issue = str(error) if isinstance(error, ValueError) else "Ya existe una venta para esa fecha o un registro de ese origen. Revisá gestión antes de continuar."
    batch.state, batch.confirmed_at = "confirmed", utcnow()
    db.commit()
    return batch


def resolve_row(db, identifier, row_id, values, actor):
    import_lock(db)
    row = db.scalar(select(ImportRow).where(ImportRow.id == row_id, ImportRow.batch_id == identifier).with_for_update())
    if row is None or row.kind not in {"sale", "expense"} or row.state not in {"review", "ready", "skipped"}:
        raise ValueError("Esta fila no admite revisión; los registros importados se corrigen desde Gestión")
    reason = clean_text(values.get("reason"), "el motivo de revisión", 300, True)
    decisions = list((row.resolution or {}).get("history", []))
    action = values.get("action", "ready")
    if action == "skip":
        row.state = "skipped"
    elif action == "ready":
        proposal = dict(row.proposed, entry_date=values.get("entry_date"), amount=values.get("amount"),
            description=values.get("description", ""), category=values.get("category", "Compras"))
        normalized = normalized_proposal(proposal)
        proposal.update({key: str(value) if key in {"entry_date", "amount"} else value for key, value in normalized.items()})
        row.proposed, row.state = proposal, "ready"
    else:
        raise ValueError("Elegí guardar revisión u omitir")
    decisions.append({"actor": actor, "reason": reason, "action": action, "proposal": row.proposed, "at": utcnow().isoformat()})
    row.resolution = dict(row.resolution or {}, history=decisions)
    db.commit()


def assign_supplier(db, identifier, label, supplier_id, actor):
    import_lock(db)
    batch_or_error(db, identifier)
    label = clean_text(label, "la etiqueta", 200, True)
    exists = db.scalar(select(ImportRow.id).where(ImportRow.batch_id == identifier,
        ImportRow.kind == "expense", ImportRow.proposed["label"].as_string() == label).limit(1))
    if not exists:
        raise ValueError("La etiqueta no pertenece a este libro")
    row = db.get(ImportSupplierMap, (identifier, label))
    if not supplier_id:
        if row:
            db.delete(row)
    else:
        try:
            supplier = db.get(Supplier, int(supplier_id))
        except (ValueError, TypeError):
            supplier = None
        if supplier is None or not supplier.active:
            raise ValueError("Elegí un proveedor activo")
        if row:
            row.supplier_id, row.actor = supplier.id, actor
        else:
            db.add(ImportSupplierMap(batch_id=identifier, label=label, supplier_id=supplier.id, actor=actor))
    db.commit()


def prepared_totals(db, identifier):
    totals = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
    for row in db.scalars(select(ImportRow).where(ImportRow.batch_id == identifier, ImportRow.kind.in_(["sale", "expense"]))):
        if row.state not in {"ready", "imported"}:
            continue
        proposal = row.proposed
        if proposal.get("entry_date") and proposal.get("amount") is not None:
            totals[proposal["entry_date"][:7]]["sales" if row.kind == "sale" else row.slot] += Decimal(proposal["amount"])
    return {month: dict(values) for month, values in sorted(totals.items())}

"""Gestión manual: sin dependencias de facturación ni de Mercado Pago."""
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID
from sqlalchemy import select
from app.models.business import BusinessEntry, Supplier

KINDS = {"sale": "Venta del día", "expense": "Egreso"}
EXPENSE_TYPES = {"white": "En Blanco", "black": "En Negro"}


def clean_text(value, label, maximum, required=False):
    value = str(value or "").strip()
    if len(value) > maximum or (required and not value):
        raise ValueError(f"Revisá {label}: {'es obligatorio y ' if required else ''}admite hasta {maximum} caracteres")
    return value


def money(value, *, allow_zero=False):
    try:
        value = str(value).strip().replace(",", ".")
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0 or (amount == 0 and not allow_zero) or amount >= Decimal("10000000000000000") or amount != amount.quantize(Decimal("0.01")):
            raise ValueError()
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Ingresá un importe válido con hasta dos decimales, sin separador de miles") from None


def record_date(value):
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        raise ValueError("Ingresá una fecha válida") from None


def snapshot(row):
    fields = ("kind", "entry_date", "amount", "expense_type", "supplier_id", "description", "version") if isinstance(row, BusinessEntry) else ("name", "contact", "notes", "active", "version")
    return {key: str(getattr(row, key)) if isinstance(getattr(row, key), (date, Decimal)) else getattr(row, key) for key in fields}


def check_version(row, value):
    try:
        matches = row.version == int(value)
    except (ValueError, TypeError):
        matches = False
    if not matches:
        raise ValueError("Este registro cambió en otra ventana. Volvé a abrirlo antes de corregirlo")


def save_entry(db, values, actor, entry_id=None):
    row = db.scalar(select(BusinessEntry).where(BusinessEntry.id == entry_id).with_for_update()) if entry_id else None
    if entry_id and (row is None or not row.active):
        raise ValueError("Registro no encontrado")
    if row:
        check_version(row, values.get("version"))
    kind = str(values.get("kind", ""))
    if kind not in KINDS:
        raise ValueError("Elegí venta o egreso")
    expense_type = values.get("expense_type") if kind == "expense" else None
    if kind == "expense" and expense_type not in EXPENSE_TYPES:
        raise ValueError("Elegí En Blanco o En Negro")
    if row and row.kind != kind:
        raise ValueError("No se puede convertir una venta en un egreso ni un egreso en venta")
    supplier_id = None
    if values.get("supplier_id"):
        try:
            supplier_id = int(values["supplier_id"])
        except (ValueError, TypeError):
            raise ValueError("Elegí un proveedor válido") from None
        supplier = db.get(Supplier, supplier_id)
        if kind != "expense" or supplier is None or (not supplier.active and (row is None or row.supplier_id != supplier_id)):
            raise ValueError("El proveedor debe estar activo y solo se usa para egresos")
    data = {"kind": kind, "entry_date": record_date(values.get("entry_date")),
        "amount": money(values.get("amount"), allow_zero=kind == "sale"),
        "expense_type": expense_type, "supplier_id": supplier_id,
        "description": clean_text(values.get("description"), "la descripción", 2000) if kind == "expense" else ""}
    if row is None:
        try:
            key = str(UUID(str(values.get("entry_key", ""))))
        except (ValueError, TypeError):
            raise ValueError("Reabrí el formulario para guardar el registro") from None
        existing = db.scalar(select(BusinessEntry).where(BusinessEntry.entry_key == key))
        if existing:
            if all(getattr(existing, key) == value for key, value in data.items()):
                return existing
            raise ValueError("El formulario ya fue utilizado. Abrí uno nuevo")
        row = BusinessEntry(entry_key=key, origin="manual", version=1, **data)
        db.add(row)
    else:
        for key, value in data.items():
            setattr(row, key, value)
        row.version += 1
    db.flush()
    db.commit()
    return row


def save_supplier(db, values, actor, supplier_id=None):
    row = db.scalar(select(Supplier).where(Supplier.id == supplier_id).with_for_update()) if supplier_id else None
    if supplier_id and row is None:
        raise ValueError("Proveedor no encontrado")
    if row:
        check_version(row, values.get("version"))
    name = clean_text(values.get("name"), "el nombre", 150, True)
    data = {"name": name, "name_key": clean_text(" ".join(name.casefold().split()), "el nombre normalizado", 150, True),
        "contact": clean_text(values.get("contact"), "el contacto", 200),
        "notes": clean_text(values.get("notes"), "las notas", 2000), "active": values.get("active", "1") == "1"}

    if row is None:
        row = Supplier(version=1, **data)
        db.add(row)
    else:
        for key, value in data.items():
            setattr(row, key, value)
        row.version += 1
    db.flush()
    db.commit()
    return row

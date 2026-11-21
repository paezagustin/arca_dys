from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models.billing import utcnow
from app.models.registers import SalaryPayment, CustomerCredit, EMPLOYEES, SALARY_MEDIA
from app.services.business import money, record_date, clean_text, check_version


def set_credit_paid(row, paid, *, at=None):
    if not paid:
        row.paid_date = row.paid_at = None
    elif not row.paid:
        row.paid_at = at if at is not None else utcnow()
        row.paid_date = row.paid_at.astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    row.paid = paid


def save_register(db, model, values, identifier=None):
    row = db.scalar(select(model).where(model.id == identifier).with_for_update()) if identifier else None
    if identifier and (row is None or row.deleted_at is not None):
        raise ValueError("Registro no encontrado")
    if row:
        check_version(row, values.get("version"))
    data = {"entry_date": record_date(values.get("entry_date")), "amount": money(values.get("amount"))}
    if model is SalaryPayment:
        employee, medium = values.get("employee"), values.get("medium", "mercado pago")
        if employee not in EMPLOYEES or medium not in SALARY_MEDIA:
            raise ValueError("Elegí un empleado y un tipo de pago válidos")
        data.update(employee=employee, medium=medium)
    else:
        paid = values.get("paid", "0")
        if paid not in {"0", "1"}:
            raise ValueError("Elegí Sí o No en Pagó")
        data.update(customer=clean_text(values.get("customer"), "el nombre", 150, True),
            observation=clean_text(values.get("observation"), "la observación", 2000), paid=paid == "1")
    if row is None:
        try:
            key = str(UUID(str(values.get("entry_key", ""))))
        except (ValueError, TypeError):
            raise ValueError("Reabrí el formulario para guardar") from None
        previous = db.scalar(select(model).where(model.entry_key == key))
        if previous:
            if previous.deleted_at is not None:
                name = "pago de sueldo" if model is SalaryPayment else "fiado"
                raise ValueError(f"Este {name} fue eliminado. Abrí un formulario nuevo para registrar otro")
            if all(getattr(previous, key) == value for key, value in data.items()):
                return previous
            raise ValueError("Este formulario ya fue guardado. Abrí uno nuevo")
        row = model(entry_key=key, version=0)
        if model is CustomerCredit:
            row.created_at = utcnow()
        db.add(row)
    if model is CustomerCredit:
        set_credit_paid(row, data.pop("paid"), at=row.created_at if identifier is None else None)
    for key, value in data.items():
        setattr(row, key, value)
    row.version += 1
    db.commit()
    return row


def _lock_credit(db, identifier):
    row = db.scalar(select(CustomerCredit).where(CustomerCredit.id == identifier).with_for_update())
    if row is None:
        raise LookupError("Fiado no encontrado")
    return row


def mark_credit_paid(db, identifier, version):
    row = _lock_credit(db, identifier)
    if row.deleted_at is not None:
        raise LookupError("Fiado no encontrado")
    if not row.paid:
        check_version(row, version)
        set_credit_paid(row, True)
        row.version += 1
        db.commit()


def delete_credit(db, identifier, version):
    row = _lock_credit(db, identifier)
    if row.deleted_at is None:
        check_version(row, version)
        row.deleted_at = utcnow()
        row.version += 1
        db.commit()


def delete_salary(db, identifier, version):
    row = db.scalar(select(SalaryPayment).where(SalaryPayment.id == identifier).with_for_update())
    if row is None:
        raise LookupError("Pago de sueldo no encontrado")
    if row.deleted_at is None:
        check_version(row, version)
        row.deleted_at = utcnow()
        row.version += 1
        db.commit()
    return row

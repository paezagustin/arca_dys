from uuid import UUID
from sqlalchemy import select
from app.models.registers import SalaryPayment, CustomerCredit, EMPLOYEES, SALARY_MEDIA
from app.services.business import money, record_date, clean_text, check_version
from app.services.listings import business_today


def save_register(db, model, values, identifier=None):
    row = db.scalar(select(model).where(model.id == identifier).with_for_update()) if identifier else None
    if identifier and row is None:
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
            if all(getattr(previous, key) == value for key, value in data.items()):
                return previous
            raise ValueError("Este formulario ya fue guardado. Abrí uno nuevo")
        row = model(entry_key=key, version=0)
        db.add(row)
    if model is CustomerCredit:
        data["paid_date"] = None
        if data["paid"]:
            data["paid_date"] = row.paid_date if row.paid else business_today()
    for key, value in data.items():
        setattr(row, key, value)
    row.version += 1
    db.commit()
    return row

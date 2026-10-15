from datetime import date
from decimal import Decimal
from sqlalchemy import select, text
from app.core import config
from app.models.settings import BusinessSettings, SettingsChange


def defaults():
    simulated = config.INTEGRATIONS_MODE == "mock"
    return {"name": "Emisor de prueba" if simulated else "", "address": "Domicilio de prueba" if simulated else "",
        "cuit": "00000000000" if simulated else (config.ARCA_CUIT or ""),
        "tax_condition": "Monotributista" if simulated else "", "gross_income": "Prueba" if simulated else "",
        "start_date": "2026-01-01" if simulated else "", "point": config.ARCA_PTO_VTA,
        "minimum": str(config.LIMITE_FACTURACION_MINIMA), "maximum": str(config.LIMITE_FACTURACION_MAXIMA)}


def read_settings(db):
    row = db.get(BusinessSettings, 1)
    return (dict(row.values), row.version) if row else (defaults(), 0)


def validate_settings(values):
    cleaned = {}
    for field, maximum in [("name", 100), ("address", 180), ("gross_income", 60)]:
        value = str(values.get(field, "")).strip()
        if not value or len(value) > maximum or any(ord(c) < 32 for c in value):
            label = {"name": "Nombre o razón social", "address": "Domicilio comercial", "gross_income": "Ingresos Brutos"}[field]
            raise ValueError(f"Revisá {label}: es obligatorio y admite hasta {maximum} caracteres")
        cleaned[field] = value
    cuit = str(values.get("cuit", "")).replace("-", "").strip()
    if len(cuit) != 11 or not cuit.isascii() or not cuit.isdigit():
        raise ValueError("El CUIT debe tener 11 dígitos")
    if config.INTEGRATIONS_MODE != "mock":
        check = (11 - sum(int(n) * w for n, w in zip(cuit[:10], [5,4,3,2,7,6,5,4,3,2])) % 11) % 11
        if check == 10 or check != int(cuit[-1]):
            raise ValueError("El dígito de control del CUIT es inválido")
    condition = values.get("tax_condition")
    if condition not in {"Monotributista", "IVA Exento"}:
        raise ValueError("Seleccioná la condición fiscal correspondiente al emisor de Factura C")
    start = date.fromisoformat(str(values.get("start_date", "")))
    if start > date.today():
        raise ValueError("La fecha de inicio no puede ser futura")
    point = int(values.get("point", 0))
    if not 1 <= point <= 99998:
        raise ValueError("Punto de venta inválido")
    minimum, maximum = Decimal(str(values.get("minimum", ""))), Decimal(str(values.get("maximum", "")))
    if not minimum.is_finite() or not maximum.is_finite() or not 0 < minimum <= maximum < Decimal("10000000000000000") or any(n != n.quantize(Decimal("0.01")) for n in [minimum, maximum]):
        raise ValueError("Los límites deben ser positivos, con hasta dos decimales y mínimo no mayor al máximo")
    cleaned.update(cuit=cuit, tax_condition=condition, start_date=start.isoformat(), point=point,
                   minimum=str(minimum), maximum=str(maximum))
    return cleaned


def save_settings(db, values, expected_version, username):
    cleaned = validate_settings(values)
    db.execute(text("SELECT pg_advisory_xact_lock(72422,1)"))
    previous, version = read_settings(db)
    if version != expected_version:
        raise ValueError("La configuración cambió en otra pantalla. Actualizá antes de guardar.")
    row = db.get(BusinessSettings, 1)
    if row is None:
        row = BusinessSettings(id=1)
        db.add(row)
    row.values, row.version = cleaned, version + 1
    db.add(SettingsChange(username=username, previous=previous, current=cleaned))
    db.commit()


def fiscal_configuration(db):
    values, version = read_settings(db)
    values = validate_settings(values)
    if config.INTEGRATIONS_MODE == "production" and values["cuit"] != config.ARCA_CUIT:
        raise ValueError("El CUIT configurado no coincide con el de los certificados de ARCA")
    return dict(values, voucher_type=11, sale_condition="Efectivo", simulation=config.INTEGRATIONS_MODE == "mock"), version

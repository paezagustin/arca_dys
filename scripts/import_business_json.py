"""Carga inicial puntual de proveedores, ventas y egresos. Nunca inicia la aplicación."""
import argparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

FILES = {
    "suppliers": "proveedores_normalizados_corregidos.json",
    "sales": "ingresos_corregidos.json",
    "expenses": "egresos_corregidos.json",
}
DATASET = "initial-business-json-v1"
LOCK = 874521900012345678
TYPES = {"EN_BLANCO": "white", "EN_NEGRO": "black"}


def key_for(name):
    return " ".join(name.casefold().split())


def text_value(value, label, maximum=150):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"{label}: texto obligatorio de hasta {maximum} caracteres")
    return " ".join(value.split())


def money_value(value, label, zero=False):
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
            raise ValueError()
        number = Decimal(str(value).strip().replace(",", "."))
        if (not number.is_finite() or number < 0 or (not zero and number == 0)
                or number >= Decimal("10000000000000000") or number != number.quantize(Decimal(".01"))):
            raise ValueError()
        return format(number.quantize(Decimal(".01")), ".2f")
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label}: importe inválido; se requieren hasta dos decimales") from None


def date_value(value, label):
    try:
        day = date.fromisoformat(value)
        if day.isoformat() != value:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ValueError(f"{label}: fecha inválida, usar AAAA-MM-DD") from None


def no_duplicate_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("El JSON contiene un campo repetido: " + key)
        result[key] = value
    return result


@dataclass(frozen=True)
class Bundle:
    data: dict
    source_hashes: dict
    digest: str
    summary: dict
    aliases: dict


def summarize(data):
    monthly = {}
    for kind, rows in (("sale", data["sales"]), ("expense", data["expenses"])):
        for row in rows:
            group = "sale" if kind == "sale" else TYPES[row["tipo"]]
            month = row["fecha"][:7]
            item = monthly.setdefault(month, {"sale": Decimal(0), "white": Decimal(0), "black": Decimal(0)})
            item[group] += Decimal(row["monto"])
    return {"counts": {key: len(rows) for key, rows in data.items()},
        "monthly": {month: {key: format(value, ".2f") for key, value in amounts.items()}
                    for month, amounts in sorted(monthly.items())}}


def read_bundle(directory):
    raw, hashes = {}, {}
    for kind, filename in FILES.items():
        content = (Path(directory) / filename).read_bytes()
        if len(content) > 10 * 1024 * 1024:
            raise ValueError(filename + ": supera 10 MiB")
        try:
            rows = json.loads(content.decode("utf-8-sig"), parse_float=Decimal,
                object_pairs_hook=no_duplicate_fields, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Número no finito")))
        except (UnicodeError, ValueError) as error:
            raise ValueError(filename + ": JSON inválido (" + str(error) + ")") from None
        if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
            raise ValueError(filename + ": se espera una lista no vacía de registros")
        raw[kind], hashes[filename] = rows, sha256(content).hexdigest()
    data = {key: [] for key in FILES}
    aliases, canonical = {}, set()
    for n, row in enumerate(raw["suppliers"], 1):
        label = f"Proveedores, fila {n}"
        name = text_value(row.get("name"), label + ", nombre")
        alias = text_value(row.get("name_key"), label + ", clave")
        key = key_for(name)
        if len(key) > 150 or key in canonical or alias in aliases:
            raise ValueError(label + ": proveedor o clave duplicados")
        if set(row) - {"name", "name_key", "ya_presente_en_sql"}:
            raise ValueError(label + ": campos desconocidos")
        flag = row.get("ya_presente_en_sql", False)
        if not isinstance(flag, bool):
            raise ValueError(label + ": ya_presente_en_sql debe ser booleano")
        aliases[alias] = key
        canonical.add(key)
        data["suppliers"].append({"name": name, "name_key": key, "ya_presente_en_sql": flag})
    # Una clave recibida no puede designar dos proveedores distintos.
    for key in canonical:
        if key in aliases and aliases[key] != key:
            raise ValueError("Las claves de proveedores son ambiguas")
    days = set()
    for kind in ("sales", "expenses"):
        for n, row in enumerate(raw[kind], 1):
            label = f"{FILES[kind]}, fila {n}"
            day = date_value(row.get("fecha"), label)
            amount = money_value(row.get("monto"), label, zero=kind == "sales")
            record = {"fecha": day, "monto": amount}
            if kind == "sales":
                if set(row) != {"fecha", "monto"} or day in days:
                    raise ValueError(label + ": campos inesperados o más de una venta para la fecha")
                days.add(day)
            else:
                if set(row) - {"fecha", "monto", "tipo", "proveedor", "proveedor_name_key", "proveedor_original"}:
                    raise ValueError(label + ": campos desconocidos")
                if not isinstance(row.get("tipo"), str) or row["tipo"] not in TYPES:
                    raise ValueError(label + ": tipo debe ser EN_BLANCO o EN_NEGRO")
                alias = row.get("proveedor_name_key")
                if not isinstance(alias, str) or alias not in aliases:
                    raise ValueError(label + ": proveedor sin correspondencia en el archivo de proveedores")
                key = aliases[alias]
                name = text_value(row.get("proveedor"), label + ", proveedor")
                if key_for(name) != key:
                    raise ValueError(label + ": nombre y clave de proveedor no coinciden")
                original = text_value(row.get("proveedor_original", name), label + ", proveedor original", 2000)
                record.update(tipo=row["tipo"], proveedor=name, proveedor_name_key=key, proveedor_original=original)
            data[kind].append(record)
    encoded = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    summary = summarize(data)
    summary["normalized_supplier_keys"] = sum(alias != key for alias, key in aliases.items())
    return Bundle(data, hashes, sha256(encoded).hexdigest(), summary, aliases)


def import_bundle(target_engine, bundle, *, apply=False):
    # Imports diferidos: analizar JSON/--help no requiere DB ni inicia gateways.
    from sqlalchemy import select, text, func
    from sqlalchemy.orm import Session
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.models.business import BusinessEntry, Supplier
    from app.models.data_import import DataImport
    from app.models.billing import utcnow

    with Session(target_engine) as db, db.begin():
        expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        if db.scalar(text("SELECT version_num FROM alembic_version")) != expected:
            raise ValueError("Aplicá primero las migraciones del proyecto")
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK})
        if apply:
            # La carga puntual no debe mezclarse con escrituras de Gestión.
            db.execute(text("LOCK TABLE business_entries, suppliers IN SHARE ROW EXCLUSIVE MODE"))
        previous = list(db.scalars(select(DataImport).where(DataImport.dataset == DATASET)))
        if previous:
            if len(previous) != 1 or previous[0].file_hash != bundle.digest:
                raise ValueError("Ya se realizó la carga inicial con otros datos; no se modificó nada")
            return dict(bundle.summary, status="already_applied", database=target_engine.url.database)
        all_days = [row["fecha"] for kind in ("sales", "expenses") for row in bundle.data[kind]]
        start, end = date.fromisoformat(min(all_days)), date.fromisoformat(max(all_days))
        if db.scalar(select(BusinessEntry.id).where(BusinessEntry.entry_date.between(start, end)).limit(1)):
            raise ValueError("Hay movimientos de Gestión dentro del período a importar; no se pisan ni deduplican automáticamente")
        wanted = set(bundle.aliases) | set(bundle.aliases.values())
        existing = {row.name_key: row for row in db.scalars(select(Supplier).where(Supplier.name_key.in_(wanted)).with_for_update())}
        providers, created = {}, 0
        for row in bundle.data["suppliers"]:
            key = row["name_key"]
            candidate_keys = {key} | {alias for alias, target in bundle.aliases.items() if target == key}
            matches = {existing[item].id: existing[item] for item in candidate_keys if item in existing}
            if len(matches) > 1:
                raise ValueError("Hay proveedores existentes ambiguos para una clave; revisar antes de importar")
            provider = next(iter(matches.values()), None)
            if provider is None:
                provider = Supplier(name=row["name"], name_key=key, contact="", notes="", active=True, version=1)
                created += 1
                if apply:
                    db.add(provider)
            providers[key] = provider
        result = dict(bundle.summary, database=target_engine.url.database, suppliers_created=created,
            suppliers_reused=len(providers)-created, status="applied" if apply else "dry_run")
        if not apply:
            return result
        db.flush()
        prefix = "json:" + bundle.digest + ":"
        for kind in ("sales", "expenses"):
            for n, row in enumerate(bundle.data[kind], 1):
                expense = kind == "expenses"
                db.add(BusinessEntry(entry_key=f"{prefix}{'e' if expense else 's'}:{n}",
                    kind="expense" if expense else "sale", entry_date=date.fromisoformat(row["fecha"]),
                    amount=Decimal(row["monto"]), cash_amount=None, mp_amount=None,
                    expense_type=TYPES[row["tipo"]] if expense else None,
                    supplier_id=providers[row["proveedor_name_key"]].id if expense else None,
                    description="", origin="json", active=True, version=1))
        db.flush()
        month = func.to_char(BusinessEntry.entry_date, "YYYY-MM")
        counts = {"sales": 0, "expenses": 0}
        monthly = {key: {item: Decimal(0) for item in ("sale", "white", "black")} for key in bundle.summary["monthly"]}
        for period, kind, expense_type, count, amount in db.execute(select(month, BusinessEntry.kind, BusinessEntry.expense_type,
                func.count(), func.sum(BusinessEntry.amount)).where(BusinessEntry.entry_key.startswith(prefix)).group_by(month, BusinessEntry.kind, BusinessEntry.expense_type)):
            counts["sales" if kind == "sale" else "expenses"] += count
            monthly[period]["sale" if kind == "sale" else expense_type] += amount
        actual = {period: {key: format(value, ".2f") for key, value in groups.items()} for period, groups in monthly.items()}
        if actual != bundle.summary["monthly"] or any(counts[key] != bundle.summary["counts"][key] for key in counts):
            raise ValueError("La conciliación falló; se revierte toda la carga")
        db.add(DataImport(id=str(uuid4()), dataset=DATASET, file_hash=bundle.digest, filename="Carga inicial JSON",
            state="confirmed", report=dict(bundle.summary, source_hashes=bundle.source_hashes),
            actor="console-json", created_at=utcnow(), confirmed_at=utcnow()))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path, help="Carpeta con los tres JSON corregidos")
    parser.add_argument("--apply", action="store_true", help="Confirmar la carga atómica; sin esta opción sólo valida")
    args = parser.parse_args()
    try:
        bundle = read_bundle(args.directory)
        from app.core.database import engine
        result = import_bundle(engine, bundle, apply=args.apply)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + "\n")
    except Exception as error:
        from sqlalchemy.exc import SQLAlchemyError
        if not isinstance(error, SQLAlchemyError):
            raise
        parser.exit(2, "No se pudo completar la operación en la base. No se guardaron cambios; revisá conexión y migraciones.\n")


if __name__ == "__main__":
    main()

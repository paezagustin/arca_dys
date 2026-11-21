"""Cuentas de Fiados: Decimal, identidad explícita y serialización por cuenta."""
from decimal import Decimal
from difflib import SequenceMatcher
from hashlib import sha256
import json
import re
from urllib.parse import quote
import unicodedata
from uuid import UUID
from sqlalchemy import select, func, text
from app.models.credits import CreditCustomer, CreditMovement, CreditLegacyLink, CreditMovementChange
from app.models.registers import CustomerCredit
from app.models.billing import utcnow
from app.services.business import clean_text, check_version, money, record_date
from app.services.listings import business_today
from app.services.money import require_grouped_pesos


class SimilarCustomers(ValueError):
    def __init__(self, candidates):
        super().__init__("Hay personas con nombres similares. Elegí una existente o confirmá que es otra persona.")
        self.candidates = candidates


class CreditConflict(ValueError):
    pass


def _version(row, value):
    try:
        check_version(row, value)
    except ValueError as exc:
        raise CreditConflict(str(exc)) from exc


def normalized(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", str(value))
                            if not unicodedata.combining(c)).casefold().split())


def normalize_phone(value):
    raw = str(value or "")
    if not raw:
        return ""
    if not re.fullmatch(r"[1-9][0-9]{9}", raw):
        raise ValueError("Ingresá código de área y número: 10 dígitos, sin 0 inicial, 15, espacios ni signos")
    return raw


def change_movement(db, identifier, values, *, delete=False, actor="Local"):
    key = _key(values.get("entry_key"))
    data = {} if delete else {"amount": _amount(values.get("amount")),
        "day": _date(values.get("entry_date")), "note": clean_text(values.get("observation"), "el detalle", 2000)}
    digest = _hash({"movement": identifier, "delete": delete, **data})
    _lock_command(db, key)
    previous = db.scalar(select(CreditMovementChange).where(CreditMovementChange.entry_key == key))
    if previous:
        if previous.payload_hash != digest:
            raise CreditConflict("Este formulario ya fue usado con otros datos")
        return db.get(CreditMovement, previous.movement_id)
    original = db.get(CreditMovement, identifier)
    if original is None:
        raise LookupError("Movimiento no encontrado")
    owner = customer(db, original.customer_id, lock=True)
    _version(owner, values.get("version"))
    db.refresh(original)
    if original.deleted_at or original.kind not in {"purchase", "payment"} or db.scalar(
            select(CreditMovement.id).where(CreditMovement.reversal_of == identifier)):
        raise CreditConflict("Este movimiento no se puede editar o eliminar; revisá su historial")
    _version(original, values.get("movement_version"))
    delta = original.delta if delete else data["amount"] * (1 if original.kind == "purchase" else -1)
    if delete or delta != original.delta:
        running = Decimal(0)
        for movement in db.scalars(select(CreditMovement).where(CreditMovement.customer_id == owner.id,
                CreditMovement.deleted_at.is_(None)).order_by(CreditMovement.account_seq)):
            if movement.id == identifier and delete:
                continue
            running += delta if movement.id == identifier else movement.delta
            if running < 0:
                raise ValueError("La corrección dejaría pagos mayores a la deuda. Revisá primero los pagos de ese período")
            money(running, allow_zero=True)
    if delete:
        original.deleted_at = utcnow()
    else:
        original.delta, original.entry_date, original.observation = delta, data["day"], data["note"]
    original.version += 1
    original.change_key, original.change_hash, original.changed_by = key, digest, actor
    owner.version += 1
    db.commit()  # El trigger conserva antes/después en la misma transacción.
    return original


def whatsapp_statement(db, identifier, *, entire=False):
    person = customer(db, identifier, lock=True)
    query = select(CreditMovement).where(CreditMovement.customer_id == identifier, CreditMovement.deleted_at.is_(None))
    if not entire:
        query = query.where(CreditMovement.account_seq > current_boundary(db, identifier))
    rows = db.scalars(query.order_by(CreditMovement.account_seq)).all()
    pesos = lambda value: "$ " + f"{int(value):,}".replace(",", ".")
    labels = {"purchase":"Compra fiada", "payment":"Pago", "opening":"Saldo anterior", "reversal":"Anulación"}
    lines = ["🧁 *Dulce y Salado*", "📋 *Detalle de cuenta*", f"Cliente: {person.name}",
        "Historial completo" if entire else "Período actual", f"Al {business_today():%d/%m/%Y}", ""]
    for row in rows:
        lines += [f"*{row.entry_date:%d/%m/%Y} · {labels[row.kind]}*",
                  ("+" if row.delta > 0 else "−") + pesos(abs(row.delta))]
        if row.observation:
            lines.append(row.observation)
        lines.append("")
    if not rows:
        lines += ["No hay movimientos en este período.", ""]
    if entire:
        archived = db.scalars(select(CustomerCredit).join(CreditLegacyLink,
            CreditLegacyLink.legacy_credit_id == CustomerCredit.id).where(CreditLegacyLink.customer_id == identifier,
                CustomerCredit.paid.is_(True)).order_by(CustomerCredit.entry_date, CustomerCredit.id))
        for row in archived:
            lines += [f"Archivo anterior · {row.entry_date:%d/%m/%Y}",
                pesos(row.amount) if row.amount == row.amount.to_integral_value() else "Importe histórico para revisar",
                "Marcado pagado · " + (f"{row.paid_date:%d/%m/%Y}" if row.paid_date else "Fecha de pago desconocida")]
            if row.observation:
                lines.append(row.observation)
            lines.append("")
    lines += [f"*Saldo pendiente: {pesos(account_balance(db, identifier))}*", "Gracias."]
    message = "\n".join(lines)
    # Partes completas, sin omitir movimientos ni recortar observaciones largas.
    chunks, remaining = [], message
    while len(remaining) > 1500:
        split = remaining.rfind("\n", 0, 1500)
        if split < 500:
            split = 1500
        chunks.append(remaining[:split]); remaining = remaining[split:].lstrip("\n")
    chunks.append(remaining)
    parts = [f"Dulce y Salado · {n+1}/{len(chunks)}\n{part}" if len(chunks)>1 else part for n,part in enumerate(chunks)]
    destination = "549" + person.phone if person.phone else ""
    links = ["https://wa.me/" + destination + "?text=" + quote(part, safe="") for part in parts] if destination else []
    return {"person": person, "message": message, "whatsapp_links": links, "entire": entire, "destination": destination}


def _key(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        raise ValueError("Reabrí el formulario antes de guardar") from None


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                             separators=(",", ":")).encode()).hexdigest()


def _lock_command(db, key):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "credit:" + key})


def account_balance(db, customer_id):
    return db.scalar(select(func.coalesce(func.sum(CreditMovement.delta), 0))
                     .where(CreditMovement.customer_id == customer_id, CreditMovement.deleted_at.is_(None)))


def customer(db, identifier, *, lock=False):
    query = select(CreditCustomer).where(CreditCustomer.id == identifier)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise LookupError("Cuenta no encontrada")
    return row


def accounts_statement(query="", state="all"):
    balances = select(CreditMovement.customer_id,
        func.sum(CreditMovement.delta).label("balance")).where(CreditMovement.deleted_at.is_(None)).group_by(CreditMovement.customer_id).subquery()
    balance = func.coalesce(balances.c.balance, 0).label("balance")
    statement = select(CreditCustomer, balance).outerjoin(balances, balances.c.customer_id == CreditCustomer.id)
    for term in normalized(query).split():
        statement = statement.where(CreditCustomer.search_text.contains(term, autoescape=True))
    if state not in {"all", "debt", "clear"}:
        raise ValueError("Elegí un filtro de cuentas válido")
    if state != "all":
        statement = statement.where(balance > 0 if state == "debt" else balance == 0)
    return statement.order_by(CreditCustomer.name, CreditCustomer.id)


def find_customers(db, query):
    if len(query) > 150:
        raise ValueError("La búsqueda admite hasta 150 caracteres")
    return [{"id": row.id, "name": row.name, "alias": row.alias,
             "balance": str(int(balance)), "version": row.version}
            for row, balance in db.execute(accounts_statement(query).limit(8))]


def similar_customers(db, name, exclude=None):
    folded = normalized(name)
    if len(folded) < 3:
        return []
    first = folded.split()[0]
    query = select(CreditCustomer).where(CreditCustomer.search_text.contains(first, autoescape=True))
    if exclude:
        query = query.where(CreditCustomer.id != exclude)
    candidates = []
    for row in db.scalars(query.order_by(CreditCustomer.name, CreditCustomer.id).limit(40)):
        other = normalized(row.name)
        if folded == other or other.split()[0] == first or SequenceMatcher(None, folded, other).ratio() >= .78:
            candidates.append(row)
    return candidates[:8]


def _person_values(values):
    name = " ".join(word.capitalize() for word in clean_text(values.get("name"), "el nombre", 150, True).split())
    alias = clean_text(values.get("alias"), "la referencia", 80)
    return {"name": name, "alias": alias, "phone": normalize_phone(values.get("phone", "")), "search_text": normalized(name + " " + alias)}


def _new_customer(db, values, key):
    _lock_command(db, "customer-names")
    data = _person_values(values)
    matches = similar_customers(db, data["name"])
    if matches and values.get("distinct_person") != "1":
        raise SimilarCustomers(matches)
    row = CreditCustomer(entry_key=key, version=1, last_seq=0, created_at=utcnow(), **data)
    db.add(row)
    db.flush()
    return row


def save_customer(db, values, identifier=None):
    data = _person_values(values)
    key = _key(values.get("entry_key"))
    _lock_command(db, key)
    _lock_command(db, "customer-names")
    if identifier is None:
        previous = db.scalar(select(CreditCustomer).where(CreditCustomer.entry_key == key))
        if previous:
            if previous.name == data["name"] and previous.alias == data["alias"] and previous.phone == data["phone"]:
                return previous
            raise CreditConflict("Este formulario ya fue usado con otros datos")
        row = _new_customer(db, values, key)
    else:
        row = customer(db, identifier, lock=True)
        _version(row, values.get("version"))
        matches = similar_customers(db, data["name"], identifier) if normalized(data["name"]) != normalized(row.name) else []
        if matches and values.get("distinct_person") != "1":
            raise SimilarCustomers(matches)
        for field, value in data.items():
            setattr(row, field, value)
        row.version += 1
    db.commit()
    return row


def _identity(values):
    if values.get("new_customer") == "1":
        return {"new": _person_values(values)}
    try:
        identifier = int(values.get("customer_id", ""))
        if identifier < 1:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Seleccioná una persona de la lista o creá una nueva") from None
    return {"id": identifier}


def _resolve(db, identity, values, key):
    if "new" in identity:
        return _new_customer(db, values, key)
    try:
        row = customer(db, identity["id"], lock=True)
    except LookupError:
        raise ValueError("Seleccioná una persona existente") from None
    _version(row, values.get("version"))
    return row


def _date(value):
    day = record_date(value)
    if day > business_today():
        raise ValueError("La fecha no puede ser posterior a hoy")
    return day


def _amount(value):
    return money(require_grouped_pesos(value))


def _record(db, row, *, key, digest, kind, delta, day, note, actor, reversal_of=None):
    resulting = account_balance(db, row.id) + delta
    if resulting < 0:
        raise ValueError("El pago o la anulación supera la deuda. No se admite saldo a favor")
    money(resulting, allow_zero=True)
    row.last_seq += 1
    row.version += 1
    movement = CreditMovement(customer_id=row.id, account_seq=row.last_seq,
        entry_key=key, payload_hash=digest, kind=kind, delta=delta, entry_date=day,
        observation=note, actor=actor, reversal_of=reversal_of, created_at=utcnow())
    db.add(movement)
    db.flush()
    return movement


def save_movement(db, values, actor="Local"):
    key = _key(values.get("entry_key"))
    kind = values.get("kind", "purchase")
    if kind not in {"purchase", "payment", "settlement"}:
        raise ValueError("Elegí un tipo de movimiento válido")
    amount, day = _amount(values.get("amount")), _date(values.get("entry_date"))
    identity = _identity(values)
    if "new" in identity and kind != "purchase":
        raise ValueError("Elegí una cuenta existente para registrar el pago")
    note = clean_text(values.get("observation"), "la observación", 2000)
    digest = _hash({"identity": identity, "kind": kind, "amount": amount, "date": day, "note": note})
    _lock_command(db, key)
    previous = db.scalar(select(CreditMovement).where(CreditMovement.entry_key == key))
    if previous:
        if previous.payload_hash != digest:
            raise CreditConflict("Este formulario ya fue usado con otros datos")
        return previous
    row = _resolve(db, identity, values, key)
    if kind == "settlement" and amount != account_balance(db, row.id):
        raise CreditConflict("El saldo cambió. Volvé a revisar el importe para saldar")
    movement = _record(db, row, key=key, digest=digest, kind="purchase" if kind == "purchase" else "payment",
        delta=amount if kind == "purchase" else -amount, day=day, note=note, actor=actor)
    db.commit()
    return movement


def reverse_movement(db, identifier, values, actor="Local"):
    key = _key(values.get("entry_key"))
    reason = clean_text(values.get("reason"), "el motivo", 2000, True)
    digest = _hash({"reverse": identifier, "reason": reason})
    _lock_command(db, key)
    previous = db.scalar(select(CreditMovement).where(CreditMovement.entry_key == key))
    if previous:
        if previous.payload_hash != digest:
            raise CreditConflict("Este formulario ya fue usado con otros datos")
        return previous
    original = db.get(CreditMovement, identifier)
    if original is None:
        raise LookupError("Movimiento no encontrado")
    row = customer(db, original.customer_id, lock=True)
    _version(row, values.get("version"))
    if original.deleted_at is not None or original.kind == "reversal" or db.scalar(select(CreditMovement.id).where(CreditMovement.reversal_of == identifier)):
        raise CreditConflict("Este movimiento ya fue anulado o es una anulación")
    reversal = _record(db, row, key=key, digest=digest, kind="reversal", delta=-original.delta,
        day=business_today(), note=reason, actor=actor, reversal_of=identifier)
    db.commit()
    return reversal


def legacy_hash(row):
    return _hash({column.name: getattr(row, column.name) for column in CustomerCredit.__table__.columns})


def pending_legacy_statement():
    return select(CustomerCredit).where(CustomerCredit.deleted_at.is_(None),
        ~select(CreditLegacyLink.legacy_credit_id).where(CreditLegacyLink.legacy_credit_id == CustomerCredit.id).exists())


def pending_legacy_totals(db):
    pending = pending_legacy_statement().subquery()
    count = db.scalar(select(func.count()).select_from(pending))
    debt, cents = db.execute(select(func.coalesce(func.sum(pending.c.amount), 0),
        func.count().filter(pending.c.amount != func.trunc(pending.c.amount)))
        .where(pending.c.paid.is_(False))).one()
    return {"count": count, "debt": debt if not cents else None, "needs_review": bool(cents)}


def link_legacy(db, identifier, values, actor="Local"):
    key = _key(values.get("entry_key"))
    identity = _identity(values)
    digest = _hash({"legacy": identifier, "identity": identity, "source": values.get("source_hash")})
    _lock_command(db, key)
    previous = db.scalar(select(CreditLegacyLink).where(CreditLegacyLink.entry_key == key))
    if previous:
        if previous.payload_hash != digest:
            raise CreditConflict("Este formulario ya fue usado con otros datos")
        return previous
    original = db.scalar(select(CustomerCredit).where(CustomerCredit.id == identifier).with_for_update())
    if original is None or original.deleted_at is not None:
        raise LookupError("Fiado anterior no encontrado")
    if db.get(CreditLegacyLink, identifier):
        raise CreditConflict("Este registro anterior ya está vinculado; no se duplicó su saldo")
    if values.get("source_hash") != legacy_hash(original):
        raise CreditConflict("El registro anterior cambió. Reabrí la revisión")
    if not original.paid and original.amount != original.amount.to_integral_value():
        raise ValueError("Este importe anterior requiere conciliación; no se redondeó ni se trasladó")
    row = _resolve(db, identity, values, key)
    opening = None
    if not original.paid:
        opening = _record(db, row, key=key, digest=digest, kind="opening", delta=original.amount,
            day=original.entry_date, note=original.observation, actor=actor)
    else:
        row.version += 1
    link = CreditLegacyLink(legacy_credit_id=identifier, customer_id=row.id, entry_key=key,
        payload_hash=digest, source_hash=legacy_hash(original),
        opening_movement_id=opening.id if opening else None, actor=actor, created_at=utcnow())
    db.add(link)
    db.commit()
    return link


def history_statement(identifier):
    running = select(CreditMovement.id,
        func.sum(CreditMovement.delta).over(order_by=CreditMovement.account_seq).label("balance"))
    running = running.where(CreditMovement.customer_id == identifier, CreditMovement.deleted_at.is_(None)).subquery()
    return select(CreditMovement, running.c.balance).join(running, running.c.id == CreditMovement.id)


def current_boundary(db, identifier):
    running = select(CreditMovement.account_seq,
        func.sum(CreditMovement.delta).over(order_by=CreditMovement.account_seq).label("balance"))
    running = running.where(CreditMovement.customer_id == identifier, CreditMovement.deleted_at.is_(None)).subquery()
    return db.scalar(select(func.coalesce(func.max(running.c.account_seq), 0)).where(running.c.balance == 0))


def closed_periods_statement(identifier):
    running = select(CreditMovement.account_seq, CreditMovement.entry_date,
        func.sum(CreditMovement.delta).over(order_by=CreditMovement.account_seq).label("balance"))
    running = running.where(CreditMovement.customer_id == identifier, CreditMovement.deleted_at.is_(None)).subquery()
    closed = select(running.c.account_seq.label("end_seq"), running.c.entry_date,
        func.lag(running.c.account_seq, 1, 0).over(order_by=running.c.account_seq).label("previous_end"))
    return closed.where(running.c.balance == 0).subquery()


def payment_preview(db, values):
    amount, day = _amount(values.get("amount")), _date(values.get("entry_date"))
    identity = _identity(values)
    if "new" in identity or values.get("kind") not in {"payment", "settlement"}:
        raise ValueError("Elegí una cuenta existente para el pago")
    row = customer(db, identity["id"])
    _version(row, values.get("version"))
    balance = account_balance(db, row.id)
    if amount > balance:
        raise ValueError("El pago supera la deuda. No se admite saldo a favor")
    if values["kind"] == "settlement" and amount != balance:
        raise CreditConflict("El saldo cambió. Volvé a revisar el importe para saldar")
    clean_text(values.get("observation"), "la observación", 2000)
    return {"person": row, "amount": amount, "day": day, "balance": balance, "after": balance - amount}

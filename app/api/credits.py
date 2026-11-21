"""HTTP de Fiados. El diario y las transacciones pertenecen al servicio."""
from uuid import uuid4
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.credits import CreditMovement, CreditLegacyLink
from app.models.registers import CustomerCredit
from app.services import credits as service
from app.services.listings import paginate, business_today
from app.web import templates

router = APIRouter(prefix="/fiados", tags=["Fiados"])
LABELS = {"purchase": "Compra fiada", "payment": "Pago", "opening": "Saldo anterior incorporado", "reversal": "Anulación"}


def found(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


def defaults(**kwargs):
    return {"entry_key": str(uuid4()), "entry_date": business_today().isoformat(), **kwargs}


def form_page(request, db, mode, values, *, person=None, source=None, original=None, error=None, preview=None):
    candidates = error.candidates if isinstance(error, service.SimilarCustomers) else []
    if person is None and values.get("customer_id"):
        try:
            person = service.customer(db, int(values["customer_id"]))
        except (LookupError, ValueError):
            pass
    status = 409 if isinstance(error, service.CreditConflict) else 422 if error else 200
    return templates.TemplateResponse(request=request, name="credits/form.html", status_code=status,
        context={"mode": mode, "values": values, "person": person, "source": source, "original": original,
                 "error": str(error) if error else None, "candidates": candidates, "preview": preview,
                 "balance": service.account_balance(db, person.id) if person else 0,
                 "today": business_today(), "labels": LABELS})


@router.get("")
def accounts(request: Request, q: str = Query("", max_length=150), state: str = "debt",
             page: int = Query(1, ge=1), edit: int | None = None, db: Session = Depends(get_db)):
    if edit:
        return RedirectResponse(f"/fiados/anteriores/{edit}", status_code=303)
    try:
        query = service.accounts_statement(q, state)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    filtered = query.order_by(None).subquery()
    total = db.scalar(select(func.coalesce(func.sum(filtered.c.balance), 0)))
    return templates.TemplateResponse(request=request, name="credits/accounts.html", context={
        "accounts": paginate(db, query, page, scalars=False), "q": q, "state": state, "total": total,
        "legacy": service.pending_legacy_totals(db)})


@router.get("/personas/buscar")
def search(q: str = Query("", max_length=150), db: Session = Depends(get_db)):
    return service.find_customers(db, q)


@router.get("/personas/nueva")
def new_customer(request: Request, db: Session = Depends(get_db)):
    return form_page(request, db, "customer", defaults())


@router.get("/personas/{identifier}/editar")
def edit_customer(identifier: int, request: Request, db: Session = Depends(get_db)):
    person = found(service.customer, db, identifier)
    return form_page(request, db, "customer", defaults(name=person.name, alias=person.alias, phone=person.phone, version=person.version), person=person)


@router.post("/personas")
@router.post("/personas/{identifier}")
async def save_customer(request: Request, identifier: int | None = None, db: Session = Depends(get_db)):
    values = dict(await request.form())
    try:
        person = service.save_customer(db, values, identifier)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        error = exc if isinstance(exc, ValueError) else service.CreditConflict("El formulario ya fue usado. Reabrilo antes de guardar")
        return form_page(request, db, "customer", values,
            person=found(service.customer, db, identifier) if identifier else None, error=error)
    return RedirectResponse(f"/fiados/{person.id}?stored=person", status_code=303)


@router.get("/nuevo")
def new_movement(request: Request, customer_id: int | None = None, create_person: bool = False,
                 db: Session = Depends(get_db)):
    person = found(service.customer, db, customer_id) if customer_id else None
    values = defaults(kind="purchase", customer_id=person.id if person else "",
        version=person.version if person else "", customer_query=person.name if person else "",
        new_customer="1" if create_person else "0")
    return form_page(request, db, "movement", values, person=person)


@router.get("/anteriores")
def legacy_list(request: Request, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    rows = service.pending_legacy_statement().order_by(CustomerCredit.entry_date, CustomerCredit.id)
    return templates.TemplateResponse(request=request, name="credits/legacy.html", context={
        "records": paginate(db, rows, page), "legacy": service.pending_legacy_totals(db)})


@router.get("/anteriores/{identifier}")
def legacy_review(identifier: int, request: Request, db: Session = Depends(get_db)):
    source = db.get(CustomerCredit, identifier)
    if source is None or source.deleted_at is not None:
        raise HTTPException(404, "Fiado anterior no encontrado")
    linked = db.get(CreditLegacyLink, identifier)
    if linked:
        return RedirectResponse(f"/fiados/{linked.customer_id}?history=1", status_code=303)
    return form_page(request, db, "legacy", defaults(source_hash=service.legacy_hash(source),
        customer_query=source.customer, new_customer="0"), source=source)


@router.post("/anteriores/{identifier}/vincular")
async def transfer_legacy(identifier: int, request: Request, db: Session = Depends(get_db)):
    values = dict(await request.form())
    try:
        link = service.link_legacy(db, identifier, values, request.state.user.username)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        error = exc if isinstance(exc, ValueError) else service.CreditConflict("El registro ya fue vinculado. Reabrí la revisión")
        return form_page(request, db, "legacy", values, source=db.get(CustomerCredit, identifier), error=error)
    return RedirectResponse(f"/fiados/{link.customer_id}?stored=legacy", status_code=303)


@router.post("")
async def save_movement(request: Request, db: Session = Depends(get_db)):
    values = dict(await request.form())
    try:
        if values.get("kind") in {"payment", "settlement"} and values.get("confirmed") != "1":
            preview = service.payment_preview(db, values)
            return form_page(request, db, "movement", values, person=preview["person"], preview=preview)
        if values.get("id") or "paid" in values:
            raise service.CreditConflict("El formulario anterior ya no modifica Fiados. Abrí la cuenta y registrá un movimiento")
        movement = service.save_movement(db, values, request.state.user.username)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        error = exc if isinstance(exc, ValueError) else service.CreditConflict("El formulario ya fue usado. Revisá el historial")
        return form_page(request, db, "movement", values, error=error)
    return RedirectResponse(f"/fiados/{movement.customer_id}?stored=movement", status_code=303)


@router.post("/{identifier}/paid")
@router.post("/{identifier}/delete")
def retired_legacy_action(identifier: int):
    raise HTTPException(409, "El formulario anterior ya no modifica Fiados. Abrí la cuenta y registrá un pago o una anulación")


@router.get("/movimientos/{identifier}/anular")
def reversal_form(identifier: int, request: Request, db: Session = Depends(get_db)):
    original = db.get(CreditMovement, identifier)
    if original is None:
        raise HTTPException(404, "Movimiento no encontrado")
    person = service.customer(db, original.customer_id)
    return form_page(request, db, "reversal", defaults(version=person.version), person=person, original=original)


@router.post("/movimientos/{identifier}/anular")
async def reverse(identifier: int, request: Request, db: Session = Depends(get_db)):
    values = dict(await request.form())
    try:
        reversal = service.reverse_movement(db, identifier, values, request.state.user.username)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        original = db.get(CreditMovement, identifier)
        error = exc if isinstance(exc, ValueError) else service.CreditConflict("El movimiento ya fue anulado")
        return form_page(request, db, "reversal", values, original=original,
            person=service.customer(db, original.customer_id), error=error)
    return RedirectResponse(f"/fiados/{reversal.customer_id}?stored=reversal", status_code=303)


@router.get("/{identifier}/pago")
def payment_form(identifier: int, request: Request, settle: bool = False, db: Session = Depends(get_db)):
    person = found(service.customer, db, identifier)
    balance = service.account_balance(db, identifier)
    if balance <= 0:
        raise HTTPException(409, "La cuenta no tiene deuda para registrar un pago")
    return form_page(request, db, "movement", defaults(customer_id=identifier, version=person.version,
        kind="settlement" if settle else "payment", amount=str(int(balance)) if settle else ""), person=person)


@router.get("/movimientos/{identifier}/editar")
@router.get("/movimientos/{identifier}/eliminar")
def movement_change_form(identifier: int, request: Request, db: Session = Depends(get_db)):
    original = db.get(CreditMovement, identifier)
    if original is None or original.deleted_at is not None:
        raise HTTPException(404, "Movimiento no encontrado")
    person = service.customer(db, original.customer_id)
    return form_page(request, db, "delete" if request.url.path.endswith("/eliminar") else "edit", defaults(
        version=person.version, movement_version=original.version, amount=str(int(abs(original.delta))),
        entry_date=original.entry_date.isoformat(), observation=original.observation), person=person, original=original)


@router.post("/movimientos/{identifier}/editar")
@router.post("/movimientos/{identifier}/eliminar")
async def movement_change(identifier: int, request: Request, db: Session = Depends(get_db)):
    values = dict(await request.form())
    delete = request.url.path.endswith("/eliminar")
    try:
        row = service.change_movement(db, identifier, values, delete=delete, actor=request.state.user.username)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        original = db.get(CreditMovement, identifier)
        error = exc if isinstance(exc, ValueError) else service.CreditConflict("La cuenta cambió. Reabrí el movimiento")
        return form_page(request, db, "delete" if delete else "edit", values, original=original,
            person=service.customer(db, original.customer_id), error=error)
    return RedirectResponse(f"/fiados/{row.customer_id}?stored={'deleted' if delete else 'edited'}", status_code=303)


@router.get("/{identifier}/whatsapp")
def whatsapp_preview(identifier: int, request: Request, entire: bool = False, db: Session = Depends(get_db)):
    statement = found(service.whatsapp_statement, db, identifier, entire=entire)
    return templates.TemplateResponse(request=request, name="credits/whatsapp.html", context=statement)


@router.get("/{identifier}")
def account_detail(identifier: int, request: Request, history: bool = False, cycle_end: int | None = None,
                   page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    person = found(service.customer, db, identifier)
    balance = service.account_balance(db, identifier)
    periods = service.closed_periods_statement(identifier)
    closed = paginate(db, select(periods).order_by(periods.c.end_seq.desc()), page, size=10, scalars=False)
    selected_period = None
    if cycle_end is not None:
        selected_period = db.execute(select(periods).where(periods.c.end_seq == cycle_end)).first()
        if selected_period is None:
            raise HTTPException(404, "Período no encontrado")
        history = True
    movements = None
    if not history or selected_period:
        query = service.history_statement(identifier)
        if selected_period:
            query = query.where(CreditMovement.account_seq > selected_period.previous_end,
                                CreditMovement.account_seq <= selected_period.end_seq)
        else:
            query = query.where(CreditMovement.account_seq > service.current_boundary(db, identifier))
        movements = paginate(db, query.order_by(CreditMovement.account_seq.desc()), page, scalars=False)
    ids = [m.id for m, _ in movements.items] if movements else []
    reversed_ids = set(db.scalars(select(CreditMovement.reversal_of).where(CreditMovement.reversal_of.in_(ids)))) if ids else set()
    originals = select(CustomerCredit).join(CreditLegacyLink, CreditLegacyLink.legacy_credit_id == CustomerCredit.id)
    originals = originals.where(CreditLegacyLink.customer_id == identifier).order_by(CustomerCredit.id.desc())
    return templates.TemplateResponse(request=request, name="credits/account.html", context={
        "person": person, "balance": balance, "history": history, "periods": closed,
        "selected_period": selected_period, "movements": movements, "reversed_ids": reversed_ids,
        "originals": paginate(db, originals, page), "labels": LABELS})

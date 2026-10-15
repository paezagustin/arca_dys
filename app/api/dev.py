"""Herramientas disponibles exclusivamente en desarrollo/test simulado."""
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.simulation import payment_resource
from app.services.mp_inbox import MPInbox
from app.models.mp_event import MPEvent

router = APIRouter(prefix="/dev", tags=["Simulación local"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def index(request: Request):
    return templates.TemplateResponse("development.html", {"request": request})


@router.post("/payments")
async def add_payment(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        amount = Decimal(form.get("amount", "10000"))
        if not amount.is_finite() or amount <= 0 or amount > Decimal("2000000") or amount != amount.quantize(Decimal("0.01")):
            raise ValueError()
        identifier = str(form.get("payment_id") or "").removeprefix("SIM-") or None
        if identifier and (len(identifier) > 36 or not all(c.isalnum() or c in "_-" for c in identifier)):
            raise ValueError()
        resource = payment_resource(amount, form.get("scenario", "approved"), payment_id=identifier)
    except (ValueError, ArithmeticError):
        raise HTTPException(422, "Importe o escenario inválido")
    inbox = MPInbox()
    event_id = inbox.receive({"resource": resource})
    inbox.process_one(event_id)
    row = db.get(MPEvent, event_id)
    return RedirectResponse("/dev?result=" + ("simulated_error" if row.state == "error" else "created"), status_code=303)


@router.post("/examples")
def examples(db: Session = Depends(get_db)):
    for index, amount in enumerate([10000, 15000, 25000], 1):
        external_id = f"example-{index}"
        inbox = MPInbox()
        event_id = inbox.receive({"resource": payment_resource(amount, payment_id=external_id)})
        inbox.process_one(event_id)
    return RedirectResponse("/page/invoice", status_code=303)

"""Herramientas disponibles exclusivamente en desarrollo/test simulado."""
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.payment_repo import create_payment, payment_exists
from app.services.mp import call_api_mp
from app.services.payments import process_webhook
from app.services.simulation import payment_resource

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
        resource = payment_resource(amount, form.get("scenario", "approved"))
    except (ValueError, ArithmeticError):
        raise HTTPException(422, "Importe o escenario inválido")
    result = process_webhook(call_api_mp(resource))
    if result["ok"]:
        create_payment(db, result["datos"])
    return RedirectResponse("/dev?result=" + ("created" if result["ok"] else "simulated_error"), status_code=303)


@router.post("/examples")
def examples(db: Session = Depends(get_db)):
    for index, amount in enumerate([10000, 15000, 25000], 1):
        external_id = f"example-{index}"
        if not payment_exists(db, f"SIM-{external_id}"):
            result = process_webhook(call_api_mp(payment_resource(amount, payment_id=external_id)))
            create_payment(db, result["datos"])
    return RedirectResponse("/page/invoice", status_code=303)

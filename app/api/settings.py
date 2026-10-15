from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core import config
from app.api.access import require_admin
from app.models.mp_event import MPEvent
from app.services.settings import read_settings, save_settings
from app.services.mp_inbox import MPInbox
from app.services.listings import paginate
from app.web import templates

router = APIRouter(dependencies=[Depends(require_admin)], tags=["Configuración"])


@router.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    values, version = read_settings(db)
    return templates.TemplateResponse(request=request, name="settings.html", context={"values": values,
        "version": version, "saved": request.query_params.get("saved") == "1", "error": None})


@router.post("/settings")
async def update_settings(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        save_settings(db, dict(form), int(form.get("version", "-1")), request.state.user.username)
    except (ValueError, ArithmeticError, TypeError) as error:
        db.rollback()
        current, version = read_settings(db)
        values = dict(current, **{k: v for k, v in form.items() if k in current})
        return templates.TemplateResponse(request=request, name="settings.html", context={"values": values,
            "version": version, "saved": False, "error": str(error) or "Revisá los datos ingresados"}, status_code=422)
    return RedirectResponse("/settings?saved=1", status_code=303)


@router.get("/settings/mp")
def mp_settings(request: Request, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    events = paginate(db, select(MPEvent).order_by(MPEvent.received_at.desc(), MPEvent.id.desc()), page, 25)
    ready = {"Token de acceso": bool(config.MP_ACCESS_TOKEN), "Cuenta receptora": bool(config.MP_COLLECTOR_ID),
             "Firma de notificaciones": bool(config.MP_WEBHOOK_SECRET), "Entrada QR/IPN alternativa": len(config.MP_LEGACY_WEBHOOK_TOKEN) >= 32}
    return templates.TemplateResponse(request=request, name="mp_settings.html", context={"events": events, "ready": ready})


@router.post("/settings/mp/events/{event_id}/retry")
def retry_event(event_id: str):
    try:
        MPInbox().retry(event_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return RedirectResponse("/settings/mp?queued=1", status_code=303)


@router.post("/settings/mp/sync")
async def sync_payment(request: Request):
    form = await request.form()
    identifier = str(form.get("payment_id", ""))
    if not identifier.isascii() or not identifier.isdigit() or len(identifier) > 50:
        raise HTTPException(422, "Ingresá un ID de pago numérico")
    MPInbox().receive({"type": "payment", "data": {"id": identifier}, "source": "manual"})
    return RedirectResponse("/settings/mp?queued=1", status_code=303)

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.payments import process_webhook
from app.repositories.payment_repo import create_payment
from app.services.mp import call_api_mp
import logging

router = APIRouter(prefix="/mp", tags=["MercadoPago"])

logger = logging.getLogger(__name__)

@router.post("/webhook")
async def mp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    logger.info("Webhook MP recibido")

    payload = await request.json()

    logger.debug(f"Payload MP: {payload}")

    resource = payload.get("resource")
    if not resource:
        return {"ok": True}

    mp_payment = call_api_mp(resource)
    processed = process_webhook(mp_payment)

    if not processed:
        return {"ok": True}

    create_payment(db, processed)

    return {"ok": True}

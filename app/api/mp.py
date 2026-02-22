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
async def mp_webhook(request: Request,db: Session = Depends(get_db)):

    try:
        logger.info("Webhook MP received")
        
        payload = await request.json()

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")

        return {"status": "error", "message": str(e), "reason": "Invalid JSON"}

        payment_id = payload.get("resource",{})

        if not payment_id:
             logger.warning("No resource ID in webhook payload")
             return {"status": "ignored", "message": "No resource ID in payload", "reason": "Missing resource"}

        mp_payment = call_api_mp(payment_id)
        if mp_payment is None:
            return {"status": "error","reason": "mp_api_error"}
        processed = process_webhook(mp_payment)
    
        if not processed:
            return {"ok": True}

        create_payment(db, processed)

        return {"ok": True}

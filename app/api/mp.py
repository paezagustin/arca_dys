from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.payments import process_webhook
from app.repositories.payment_repo import create_payment
from app.repositories.error_log_repo import create_error_log
from app.services.mp import call_api_mp

import logging

router = APIRouter(prefix="/mp", tags=["MercadoPago"])
logger = logging.getLogger(__name__)





@router.post("/webhook")
async def mp_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        logger.info("Received MP webhook")
        payload = await request.json()
        #logger.info(f"Webhook payload received: {payload}")
        resource = payload.get('resource', {})
        #logger.info(f"Webhook payload: {resource}")
        if not resource:
            return {"status": "ignored", "reason": "no_resource"}
        
        # Llamar a API de MP
        payment_data = call_api_mp(resource)
        #logger.info(f"MP API response : {payment_data}")
        if payment_data is None:
            # Error consultando MP
            create_error_log(
                db=db,
                source="webhook_mp",
                error_type="api_error",
                message=f"Error calling MP API for resource.",
                resource_id=str(resource),
                raw_data=payload,
            )
            return {"status": "error", "reason": "mp_api_error"}
        
        # Procesar el pago
        resultado = process_webhook(payment_data)
        
        if not resultado["ok"]:
            # Error de validación
            create_error_log(
                db=db,
                source="webhook_mp",
                error_type=resultado["tipo"],
                message=resultado["error"],
                resource_id=str(payment_data.get("id")),
                raw_data=payment_data
            )
            return {"status": "ignored", "reason": resultado["error"]}
        logger.info(f"Webhook processed")
        # Todo OK - guardar el pago
        
        logger.info(f"Creating payment in DB with data")
        payment = create_payment(db, resultado["datos"])
        logger.info(f"Payment created in BBDD correctly")
        
        return {"status": "ok", "payment_id": payment.id}
        
    except Exception as e:
        # Error inesperado (bug nuestro)
        logger.error(f"Error in webhook: {e}", exc_info=True)
        
        create_error_log(
            db=db,
            source="webhook_mp",
            error_type="system",
            message=f"Error: {str(e)}",
            raw_data={"payload": str(request)} if request else None
        )
        
        return {"status": "error", "reason": "internal_error"}
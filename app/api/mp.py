from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.payments import pre_process_webhook
from app.repositories.payment_repo import create_payment, payment_exists
from app.services.mp import call_api_mp

router = APIRouter(prefix="/mp", tags=["MercadoPago"])


@router.post("/webhook")
async def mp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    payload = await request.json()

    resource = payload.get("resource")
    if not resource:
        return {"ok": True}

    mp_payment = call_api_mp(resource)
    processed = pre_process_webhook(mp_payment)

    if not processed:
        return {"ok": True}

    #Saco esto así entran todos los pagos aunque estén repetidos
    
    #if payment_exists(db, processed["id_payment_mp"]):
    #    return {"ok": True}

    create_payment(db, processed)

    return {"ok": True}

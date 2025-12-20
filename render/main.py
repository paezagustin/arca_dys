from fastapi import FastAPI, Request
import json
import db 
from render.repository import save_payment
from render.mp import get_payment

app = FastAPI()

@app.post("/mp/webhook")
async def mp_webhook(request: Request):
    payload = await request.json()
    payment_id = payload.get("data", {}).get("id")

    if not payment_id:
        return {"ignored": True}

    payment = get_payment(payment_id)
    if payment["status"] != "approved":
        return {"not_approved": True}

    saved = save_payment(payment)

    return {"ok": True, "saved": saved}


@app.on_event("startup")
def startup():
    db.init_db()

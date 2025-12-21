from fastapi import FastAPI, Request
import json
from render.db import init_db
from render.repository import save_payment
from render.mp import get_payment

app = FastAPI()

@app.post("/mp/webhook")
async def mp_webhook(request: Request):
    payload = await request.json()
    payment_id = payload.get("data", {}).get("id")

    #print("Received webhook for payment ID:", payment_id)
    print("Full payload:", json.dumps(payload))
    #if not payment_id:
    #    return {"ignored": True}

    amount = payload.get('ammount')
    client = payload.get('client_id')
    state = payload.get('payment').get('state')
    type_payment = payload.get('payment').get('type')
    print(f"Amount: {amount}, Client ID: {client}, State: {state}, Type: {type_payment}")

    if not payment_id:
        return {"ignored": True}

    #payment = get_payment(payment_id)
    #if payment["status"] != "approved":
    #    return {"not_approved": True}

    #saved = save_payment(payment)

    #return {"ok": True, "saved": saved}


@app.on_event("startup")
def startup():
    init_db()

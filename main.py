from fastapi import FastAPI, Request
import json

app = FastAPI()

@app.post("/mp/webhook")
async def mp_webhook(request: Request):
    payload = await request.json()

    print("RAW:", payload)

    payment_id = payload.get("data", {}).get("id")
    event_type = payload.get("action")

    if not payment_id:
        return {"ignored": True}

    print("EVENT:", event_type, "PAYMENT_ID:", payment_id)

    return {"ok": True}

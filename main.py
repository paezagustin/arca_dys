from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/mp/webhook")
async def mp_webhook(request: Request):
    payload = await request.json()
    print("MP WEBHOOK:", payload)
    return {"ok": True}

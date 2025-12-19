@app.post("/mp/webhook")
async def mp_webhook(request: Request):
    payload = await request.json()
    payment_id = payload.get("data", {}).get("id")

    if not payment_id:
        return {"ignored": True}

    payment = get_payment(payment_id)

    if payment["status"] != "approved":
        return {"not_approved": True}

    amount = payment["transaction_amount"]
    date = payment["date_approved"]

    print("PAGO OK:", payment_id, amount, date)

    return {"ok": True}

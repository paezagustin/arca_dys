import hmac
from fastapi import APIRouter, Request, HTTPException
from app.core import config
from app.services.mp_inbox import MPInbox, validate_signature

router = APIRouter(prefix="/mp", tags=["Mercado Pago"])


async def receive(request, legacy_token=None):
    if config.INTEGRATIONS_MODE != "mock":
        if not config.MP_COLLECTOR_ID:
            raise HTTPException(503, "Falta configurar la cuenta receptora")
        if legacy_token is not None:
            if len(config.MP_LEGACY_WEBHOOK_TOKEN) < 32 or not hmac.compare_digest(legacy_token, config.MP_LEGACY_WEBHOOK_TOKEN):
                raise HTTPException(401, "Entrada no autorizada")
        elif not validate_signature(request.headers.get("x-signature"), request.headers.get("x-request-id"),
                                    request.query_params.get("data.id"), config.MP_WEBHOOK_SECRET):
            raise HTTPException(401, "Firma de notificación inválida")
    content = await request.body()
    if len(content) > 262144:
        raise HTTPException(413, "Notificación demasiado grande")
    try:
        payload = await request.json() if content else {}
        event_id = MPInbox().receive(payload, dict(request.query_params))
    except (ValueError, TypeError):
        raise HTTPException(400, "Notificación inválida")
    # No se devuelve 200 hasta confirmar la recepción en PostgreSQL. El worker
    # retoma pendientes tras reinicios y nunca emite documentos fiscales.
    return {"status": "accepted", "event_id": event_id}


@router.post("/webhook")
async def webhook(request: Request):
    return await receive(request)


@router.post("/webhook/legacy/{token}")
async def legacy_webhook(token: str, request: Request):
    return await receive(request, token)

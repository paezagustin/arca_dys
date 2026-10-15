import logging
from app.core.config import INTEGRATIONS_MODE, MP_ACCESS_TOKEN
from app.core.safety import require_live_integrations

logger = logging.getLogger(__name__)


def call_api_mp(resource) -> dict | None:
    if INTEGRATIONS_MODE == "mock":
        from app.services.simulation import simulated_payment
        return simulated_payment(str(resource))
    require_live_integrations()
    if not MP_ACCESS_TOKEN:
        raise RuntimeError("MP_ACCESS_TOKEN no está configurado")
    import mercadopago
    try:
        result = mercadopago.SDK(MP_ACCESS_TOKEN).payment().get(resource)
        if result and result.get("status") == 200:
            return result.get("response")
        logger.warning("Mercado Pago no devolvió un pago válido")
    except Exception:
        logger.exception("Falló la consulta a Mercado Pago")
    return None

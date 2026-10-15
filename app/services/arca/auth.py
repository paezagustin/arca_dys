"""Cliente con certificados ya instalados; no ejecuta automatizaciones de cuenta."""
from pathlib import Path
from app.core import config
from app.core.safety import require_live_integrations
from app.services.arca.transport import BoundedAfip


class AFIPAuthError(Exception):
    pass


def get_afip_client():
    require_live_integrations()
    if not config.ARCA_CUIT or not config.ARCA_ACCESS_TOKEN:
        raise AFIPAuthError("Falta CUIT o token del proveedor fiscal")
    try:
        cert = Path(config.ARCA_CRT_PATH).read_text()
        key = Path(config.ARCA_KEY_PATH).read_text()
    except OSError as error:
        raise AFIPAuthError("No se pudieron leer los certificados configurados") from error
    return BoundedAfip({"CUIT": config.ARCA_CUIT, "access_token": config.ARCA_ACCESS_TOKEN,
                        "cert": cert, "key": key, "production": True})

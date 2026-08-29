from afip import Afip
from app.core.config import (
    ARCA_CUIT,
    ARCA_PASSWORD,
    ARCA_ACCESS_TOKEN,
    ARCA_ALIAS,
    ENV,
    ARCA_CRT_PATH,
    ARCA_KEY_PATH
)

class AFIPAuthError(Exception):
    """Error en el proceso de autenticación con AFIP"""
    pass


def get_afip_client() -> Afip:
    """
    Autentica contra AFIP y devuelve un cliente Afip listo para usar
    """
    if not all([ARCA_CUIT, ARCA_PASSWORD, ARCA_ACCESS_TOKEN]):
        raise AFIPAuthError("Credenciales AFIP incompletas en config")

    # Cliente base (sin cert)
    afip = Afip({
        "CUIT": ARCA_CUIT,
        "access_token": ARCA_ACCESS_TOKEN,
        "production": True if ENV == "production" else False
    })

    #Leer certificado y clave desde archivso
    try:
        with open(ARCA_CRT_PATH, "r") as cert_file:
            cert = cert_file.read()
        with open(ARCA_KEY_PATH, "r") as key_file:
            key = key_file.read()
    except Exception as e:
        raise AFIPAuthError(f"Error leyendo certificados desde archivos: {str(e)}")
    
    # =========================
    # Autorización WSFE
    # =========================
    data_auth_ws = {
        "cuit": ARCA_CUIT,
        "username": ARCA_CUIT,
        "password": ARCA_PASSWORD,
        "alias": ARCA_ALIAS,
        "service": "wsfe"
    }

    auth_mode = "auth-web-service-prod" if ENV == "production" else "auth-web-service-dev"

    auth_response = afip.createAutomation(
        auth_mode,
        data_auth_ws,
        True
    )

    if auth_response.get("status") != "complete":
        raise AFIPAuthError("Error autenticando WSFE")

    # =========================
    # Cliente final autenticado
    # =========================
    afip_auth = Afip({
        "CUIT": ARCA_CUIT,
        "access_token": ARCA_ACCESS_TOKEN,
        "cert": cert,
        "key": key,
        "production": True if ENV == "production" else False
    })

    return afip_auth

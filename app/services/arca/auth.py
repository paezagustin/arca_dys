# app/services/arca/auth.py

from afip import Afip
from app.core.config import (
    AFIP_CUIT,
    AFIP_PASSWORD,
    AFIP_ACCESS_TOKEN,
    AFIP_ALIAS,
    ENV,
)

class AFIPAuthError(Exception):
    """Error en el proceso de autenticación con AFIP"""
    pass


def get_afip_client() -> Afip:
    """
    Autentica contra AFIP y devuelve un cliente Afip listo para usar
    """
    if not all([AFIP_CUIT, AFIP_PASSWORD, AFIP_ACCESS_TOKEN]):
        raise AFIPAuthError("Credenciales AFIP incompletas en config")

    # Cliente base (sin cert)
    afip = Afip({
        "CUIT": AFIP_CUIT,
        "access_token": AFIP_ACCESS_TOKEN
    })

    # =========================
    # Creación del certificado
    # =========================
    data_create_cert = {
        "cuit": AFIP_CUIT,
        "username": AFIP_CUIT,
        "password": AFIP_PASSWORD,
        "alias": AFIP_ALIAS
    }

    cert_mode = "create-cert-prod" if ENV == "production" else "create-cert-dev"

    cert_response = afip.createAutomation(
        cert_mode,
        data_create_cert,
        True
    )

    if cert_response.get("status") != "complete":
        raise AFIPAuthError("Error creando certificado AFIP")

    cert = cert_response["data"].get("cert")
    key = cert_response["data"].get("key")

    # =========================
    # Autorización WSFE
    # =========================
    data_auth_ws = {
        "cuit": AFIP_CUIT,
        "username": AFIP_CUIT,
        "password": AFIP_PASSWORD,
        "alias": AFIP_ALIAS,
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
        "CUIT": AFIP_CUIT,
        "access_token": AFIP_ACCESS_TOKEN,
        "cert": cert,
        "key": key
    })

    return afip_auth

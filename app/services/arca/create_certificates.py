# =========================
# Creación del certificado
# =========================
from afip import Afip
from app.core.config import (
    ARCA_CUIT,
    ARCA_PASSWORD,
    ARCA_ACCESS_TOKEN,
    ARCA_ALIAS,
    ENV,
)

class AFIPAuthError(Exception):
    """Error en el proceso de autenticación con AFIP"""
    pass

def create_certificates(afip: Afip) -> dict:

    data_create_cert = {
        "cuit": ARCA_CUIT,
        "username": ARCA_CUIT,
        "password": ARCA_PASSWORD,
        "alias": ARCA_ALIAS
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

    
    return {
        "cert": cert,
        "key": key
    }

def save_certificates_to_files(cert: str, key: str, cert_path: str, key_path: str):
    """
    Guarda el certificado y la clave en archivos locales
    """
    try:
        with open(cert_path, "w") as cert_file:
            cert_file.write(cert)
        with open(key_path, "w") as key_file:
            key_file.write(key)
    except Exception as e:
        raise AFIPAuthError(f"Error guardando certificados en archivos: {str(e)}")
    
"""Extensiones pequeñas de afip.py 1.2.0 con timeout explícito y sin retries POST."""
import requests
from afip import Afip
from afip.web_service import WebService
from app.core.safety import require_live_integrations


def post_sdk(afip, path, payload):
    require_live_integrations()
    headers = {"sdk-version-number": afip.sdk_version_number, "sdk-library": "python",
               "sdk-environment": afip.environment, "Authorization": "Bearer " + afip.access_token}
    response = requests.post("https://app.afipsdk.com/api/v1/" + path, json=payload,
                             headers=headers, timeout=(5, 45), allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Respuesta inesperada del proveedor fiscal")
    return response.json()


class BoundedWebService(WebService):
    def executeRequest(self, method, params=None):
        return post_sdk(self.afip, "afip/requests", {"method": method, "params": params or {},
            "environment": self.afip.environment, "wsid": self.options["service"],
            "url": self.URL if self.afip.production else self.URL_TEST,
            "wsdl": self.WSDL if self.afip.production else self.WSDL_TEST, "soap_v_1_2": self.soapv12})


class BoundedAfip(Afip):
    def getServiceTA(self, service, force=False):
        return post_sdk(self, "afip/auth", {"environment": self.environment, "tax_id": self.CUIT,
            "wsid": service, "force_create": force, "cert": self.cert, "key": self.key})

    def webService(self, service, options=None):
        return BoundedWebService(self, dict(options or {}, service=service, generic=True))

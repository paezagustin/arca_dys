"""Lecturas MP exclusivamente sobre endpoints conocidos. Sin operaciones de dinero."""
import re
import requests
from app.core import config
from app.core.safety import require_live_integrations


class MPGateway:
    def _get(self, path):
        require_live_integrations()
        if not config.MP_ACCESS_TOKEN or not config.MP_COLLECTOR_ID:
            raise ValueError("Falta configurar token/cuenta de Mercado Pago")
        response = requests.get("https://api.mercadopago.com/" + path,
            headers={"Authorization": "Bearer " + config.MP_ACCESS_TOKEN}, timeout=(5, 10), allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Respuesta inesperada de Mercado Pago")
        return response.json()

    def _owner(self, value):
        if str(value) != config.MP_COLLECTOR_ID:
            raise ValueError("El recurso pertenece a otra cuenta MP")

    def payment(self, payment_id):
        if not re.fullmatch(r"[0-9]{1,50}", str(payment_id)):
            raise ValueError("ID de pago inválido")
        raw = self._get("v1/payments/" + str(payment_id))
        self._owner(raw.get("collector_id"))
        if str(raw.get("id")) != str(payment_id) or raw.get("live_mode") is not True:
            raise ValueError("Pago o entorno diferente al solicitado")
        return raw

    def fetch(self, topic, resource):
        if topic == "payment":
            return [self.payment(resource)]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", resource):
            raise ValueError("ID de recurso inválido")
        if topic == "merchant_order":
            order = self._get("merchant_orders/" + resource)
            if str(order.get("id")) != resource:
                raise ValueError("Orden distinta a la solicitada")
            self._owner(order.get("collector", {}).get("id"))
            return [self.payment(p["id"]) for p in order["payments"]]
        if topic == "order":
            order = self._get("v1/orders/" + resource)
            if str(order.get("id")) != resource:
                raise ValueError("Orden distinta a la solicitada")
            self._owner(order.get("user_id"))
            payments = []
            for item in order["transactions"]["payments"]:
                # Usar la identidad canónica; evita duplicar payment + order.
                # Un formato sin referencia permanece pendiente de revisión.
                reference = item.get("reference_id")
                if not reference:
                    if item.get("status") in {"created", "processing", "action_required"}:
                        continue
                    raise ValueError("Orden sin referencia de pago canónica; revisar contrato")
                raw = self.payment(reference)
                from decimal import Decimal
                if Decimal(str(raw["transaction_amount"])) != Decimal(str(item["amount"])):
                    raise ValueError("Importe de orden/pago inconsistente")
                payments.append(raw)
            return payments
        if topic == "point_integration_wh":
            intent = self._get("point/integration-api/payment-intents/" + resource)
            reference = intent.get("payment", {}).get("id")
            if reference is None:
                return []
            return [self.payment(reference)]
        return []


class MockMPGateway:
    def fetch(self, topic, resource):
        from app.services.simulation import simulated_payment
        payment = simulated_payment(resource)
        if payment is None:
            raise ValueError("Falla simulada al consultar MP")
        return [payment]


def get_mp_gateway():
    return MockMPGateway() if config.INTEGRATIONS_MODE == "mock" else MPGateway()


def call_api_mp(resource):
    # Compatibilidad con el cargador local; el webhook usa el inbox durable.
    try:
        return get_mp_gateway().fetch("payment", str(resource))[0]
    except (ValueError, IndexError):
        return None

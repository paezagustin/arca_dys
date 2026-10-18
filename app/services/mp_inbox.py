"""Recepción durable y procesamiento idempotente. Nunca importa el módulo fiscal."""
from datetime import timedelta
from hashlib import sha256
import hmac
import json
import re
from urllib.parse import urlparse
from uuid import uuid4
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.core.database import engine as default_engine
from app.models.billing import utcnow
from app.models.mp_event import MPEvent, PaymentChange
from app.models.payment import Payment
from app.models.mp_identity import MPPaymentIdentity
from app.services.mp import get_mp_gateway
from app.services.payments import normalize_payment, provider_date
from app.core.deployment import coordinated

TOPICS = {"payment", "merchant_order", "order", "point_integration_wh"}


def validate_signature(signature, request_id, query_id, secret):
    if not all([signature, request_id, query_id, secret]):
        return False
    try:
        fields = dict(part.strip().split("=", 1) for part in signature.split(","))
        timestamp, value = fields["ts"], fields["v1"]
        if not timestamp.isdigit() or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            return False
        manifest = f"id:{str(query_id).lower()};request-id:{request_id};ts:{timestamp};"
        expected = hmac.new(secret.encode(), manifest.encode(), "sha256").hexdigest()
        return hmac.compare_digest(expected, value.lower())
    except (ValueError, KeyError):
        return False


def parse_notification(payload, query):
    if not isinstance(payload, dict):
        raise ValueError("La notificación debe ser un objeto")
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError("Datos de notificación inválidos")
    topic = str(payload.get("type") or payload.get("topic") or query.get("topic") or "payment")
    topic = {"orders": "order", "merchant_orders": "merchant_order", "point_integration_ipn": "point_integration_wh"}.get(topic, topic)
    resource = str(data.get("id") or query.get("data.id") or payload.get("resource") or query.get("id") or "")
    if resource.startswith("https://"):
        url = urlparse(resource)
        patterns = {"payment": r"/v1/payments/([0-9]+)", "merchant_order": r"/merchant_orders/([0-9]+)",
                    "order": r"/v1/orders/([A-Za-z0-9_-]+)"}
        match = re.fullmatch(patterns.get(topic, r"(?!)"), url.path)
        if url.netloc != "api.mercadopago.com" or url.query or not match:
            raise ValueError("URL de recurso no admitida")
        resource = match.group(1)
    if not resource or len(resource) > 200 or len(topic) > 50 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", resource):
        raise ValueError("Identidad o tema de notificación inválido")
    if query.get("data.id") and str(data.get("id", query["data.id"])).lower() != query["data.id"].lower():
        raise ValueError("La identidad firmada no coincide con el cuerpo")
    return topic, resource


class MPInbox:
    def __init__(self, engine=default_engine, gateway_factory=get_mp_gateway):
        self.engine, self.gateway_factory = engine, gateway_factory

    def receive(self, payload, query=None):
        topic, resource = parse_notification(payload, query or {})
        # IPN no tiene identidad de evento fiable: conservar cada entrega. La
        # identidad del pago y la fecha del proveedor hacen idempotente su efecto.
        identity = str(payload.get("id") or uuid4())
        key = sha256(json.dumps([topic, resource, identity]).encode()).hexdigest()
        values = dict(id=str(uuid4()), dedup_key=key, topic=topic, resource=resource,
                      payload=payload, state="pending", attempts=0, received_at=utcnow(), next_attempt_at=utcnow())
        with Session(self.engine) as db:
            event_id = db.scalar(insert(MPEvent).values(**values).on_conflict_do_nothing(
                index_elements=["dedup_key"]).returning(MPEvent.id))
            if event_id is None:
                event_id = db.scalar(select(MPEvent.id).where(MPEvent.dedup_key == key))
            db.commit()
            return event_id

    @coordinated
    def process_one(self, event_id=None):
        with Session(self.engine) as db:
            query = select(MPEvent).where(MPEvent.state.in_(["pending", "error"]), MPEvent.next_attempt_at <= utcnow())
            if event_id:
                query = query.where(MPEvent.id == event_id)
            row = db.scalar(query.order_by(MPEvent.received_at, MPEvent.id).with_for_update(skip_locked=True).limit(1))
            if row is None:
                return False
            row.attempts += 1
            resources = None
            try:
                review = False
                with db.begin_nested():
                    identity = db.get(MPPaymentIdentity, row.resource) if row.topic == "payment" else None
                    if identity is not None and identity.legacy_duplicate:
                        # La entrega queda conservada. No consultar un proveedor para
                        # elegir automáticamente entre filas históricas divergentes.
                        changed, review = 0, True
                    elif row.topic not in TOPICS:
                        changed = 0
                    else:
                        resources = self.gateway_factory().fetch(row.topic, row.resource)
                        normalized = sorted([normalize_payment(raw) for raw in resources], key=lambda p: p["id_payment_mp"])
                        outcomes = [self._apply(db, row, data) for data in normalized]
                        changed, review = sum(value > 0 for value in outcomes), any(value < 0 for value in outcomes)
                row.state = "review" if review else ("processed" if changed else "ignored")
                row.error = "ID MP histórico repetido: entrega conservada, sin modificar ni facturar sus filas. Requiere conciliación manual." if review else None
                row.processed_at = utcnow()
            except Exception as error:
                row.state = "error"
                row.error = f"No se pudo consultar o validar el recurso ({type(error).__name__}). Se reintentará sin facturar."
                row.next_attempt_at = utcnow() + timedelta(seconds=min(300, 2 ** min(row.attempts, 8)))
            if resources is not None:
                row.resource_responses = [*(row.resource_responses or []), {
                    "attempt": row.attempts, "observed_at": utcnow().isoformat(),
                    "result": row.state, "resources": resources}]
            db.commit()
            return True

    def _apply(self, db, event, data):
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "mp:" + data["id_payment_mp"]})
        identity = db.get(MPPaymentIdentity, data["id_payment_mp"], with_for_update=True)
        if identity is not None and identity.legacy_duplicate:
            return -1
        payment = db.get(Payment, identity.payment_id, with_for_update=True) if identity else None
        if identity is not None and payment is None:
            raise ValueError("Identidad MP sin fila operativa; revisar integridad")
        previous = payment.status if payment else None
        previous_data = None
        if payment:
            last = payment.provider_updated_at
            if last is None and payment.raw_json and payment.raw_json.get("date_last_updated"):
                last = provider_date(payment.raw_json["date_last_updated"])
            if last and data["provider_updated_at"] < last:
                return 0
            from decimal import Decimal
            if Decimal(str(payment.mont)) != data["mont"]:
                raise ValueError("El importe original del pago cambió; requiere revisión")
            if last and data["provider_updated_at"] == last:
                if payment.status != data["status"]:
                    raise ValueError("Estados contradictorios con la misma fecha")
                return 0
            if data["date_approved"] is None:
                data["date_approved"] = payment.date_approved
            previous_data = db.scalar(text("SELECT row_to_json(p) FROM payments p WHERE id=:id"), {"id": payment.id})
            for name, value in data.items():
                setattr(payment, name, value)
        else:
            payment = Payment(**data, registered_arca=False)
            db.add(payment)
            db.flush()
        db.add(PaymentChange(payment_id=payment.id, event_id=event.id, previous_status=previous, previous_data=previous_data,
            new_status=data["status"], provider_updated_at=data["provider_updated_at"]))
        return 1

    def retry(self, event_id):
        with Session(self.engine) as db:
            row = db.get(MPEvent, event_id)
            if row is None:
                raise ValueError("Notificación no encontrada")
            row.state, row.next_attempt_at = "pending", utcnow()
            db.commit()

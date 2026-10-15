"""Ejecutor local de trabajo durable. Facturación solo de solicitudes confirmadas."""
import logging
from app.services.mp_inbox import MPInbox
from app.services.billing import BillingService

logger = logging.getLogger(__name__)


def worker(stop):
    inbox, billing = MPInbox(), BillingService()
    while not stop.is_set():
        processed = False
        for name, operation in [("mp", inbox.process_one), ("billing", billing.process_one_queued)]:
            if stop.is_set():
                return
            try:
                processed = operation() or processed
            except Exception as error:
                logger.error("Error de procesamiento | módulo=%s | tipo=%s", name, type(error).__name__)
        if not processed:
            stop.wait(3)

"""Barrera de mantenimiento persistente y coordinación entre procesos, sin DDL."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import os
from pathlib import Path
from sqlalchemy import text

LOCK = 72423
_held = ContextVar("deployment_operation", default=None)


class DeploymentBlocked(RuntimeError):
    pass


def control_directory():
    return Path(os.environ.get("DEPLOY_CONTROL_PATH", "/run/arca-deploy"))


def paused():
    directory = control_directory()
    # Producción debe tener el montaje del protocolo instalado. Ausencia falla cerrada.
    return (directory / "paused").exists() or (
        os.environ.get("ENV") == "production" and not (directory / "protocol-v1").is_file())


@contextmanager
def operation(engine):
    """El lock compartido cubre proveedor, commits y recuperación completa.

    El host publica paused ANTES de esperar el lock exclusivo. Toda nueva operación
    comprueba el marcador DESPUÉS de adquirir su lock: no hay check-then-restart.
    """
    if _held.get() is engine:
        yield
        return
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock_shared(:lock, 1)"), {"lock": LOCK})
        connection.commit()
        token = _held.set(engine)
        try:
            if paused():
                raise DeploymentBlocked("Actualización en curso. Intentá nuevamente en unos instantes.")
            yield
        finally:
            _held.reset(token)
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock_shared(:lock, 1)"), {"lock": LOCK})
            connection.commit()


def coordinated(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with operation(self.engine):
            return method(self, *args, **kwargs)
    return guarded

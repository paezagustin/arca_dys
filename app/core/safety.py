from app.core.config import settings


class IntegrationSafetyError(RuntimeError):
    pass


def require_live_integrations():
    if settings.environment != "production" or settings.integrations_mode != "production":
        raise IntegrationSafetyError("El entorno simulado bloquea clientes externos reales")

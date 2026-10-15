"""Configuración explícita: desarrollo y tests nunca habilitan servicios reales."""
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
if os.getenv("APP_ENV_FILE"):
    load_dotenv(os.environ["APP_ENV_FILE"], override=False)


@dataclass(frozen=True)
class Settings:
    environment: str
    integrations_mode: str
    database_url: str
    minimum_invoice: Decimal
    maximum_invoice: Decimal

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        environment = env.get("ENV", env.get("ENVIRONMENT", "development"))
        if environment not in {"development", "test", "production"}:
            raise ValueError("ENV debe ser development, test o production")
        if env.get("ENV") and env.get("ENVIRONMENT") and env["ENV"] != env["ENVIRONMENT"]:
            raise ValueError("ENV y ENVIRONMENT no coinciden")
        mode = env.get("INTEGRATIONS_MODE", "mock")
        if mode not in {"mock", "production"}:
            raise ValueError("INTEGRATIONS_MODE debe ser mock o production")
        if environment == "production" and mode != "production":
            raise ValueError("Producción requiere un modo de integración explícitamente productivo")
        if mode == "production" and (environment != "production" or env.get("ALLOW_LIVE_OPERATIONS") != "true"):
            raise ValueError("Integraciones reales requieren ENV=production y ALLOW_LIVE_OPERATIONS=true")
        database_url = env.get("DATABASE_URL", "")
        if not database_url:
            raise ValueError("DATABASE_URL no está definida")
        try:
            minimum = Decimal(env.get("LIMITE_FACTURACION_MINIMA", "1000"))
            maximum = Decimal(env.get("LIMITE_FACTURACION_MAXIMA", "2000000"))
            valid = (minimum.is_finite() and maximum.is_finite() and 0 < minimum <= maximum
                     and minimum == minimum.quantize(Decimal("0.01"))
                     and maximum == maximum.quantize(Decimal("0.01")))
        except (InvalidOperation, ValueError):
            valid = False
        if not valid:
            raise ValueError("Límites de facturación inválidos")
        return cls(environment, mode, database_url, minimum, maximum)


settings = Settings.from_env()
ENV = settings.environment
DEBUG = ENV == "development"
DATABASE_URL = settings.database_url
INTEGRATIONS_MODE = settings.integrations_mode
LIMITE_FACTURACION_MINIMA = settings.minimum_invoice
LIMITE_FACTURACION_MAXIMA = settings.maximum_invoice
ARCA_CUIT = os.getenv("ARCA_CUIT")
ARCA_PASSWORD = os.getenv("ARCA_PASSWORD")
ARCA_ACCESS_TOKEN = os.getenv("ARCA_ACCESS_TOKEN")
ARCA_ALIAS = os.getenv("ARCA_ALIAS", "afipsdk")
ARCA_PTO_VTA = int(os.getenv("ARCA_PTO_VTA", "10"))
ARCA_CRT_PATH = os.getenv("ARCA_CRT_PATH", "crt_afipsdk.crt")
ARCA_KEY_PATH = os.getenv("ARCA_KEY_PATH", "key_afipsdk.key")
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
MP_LEGACY_WEBHOOK_TOKEN = os.getenv("MP_LEGACY_WEBHOOK_TOKEN", "")
MP_COLLECTOR_ID = os.getenv("MP_COLLECTOR_ID", "")

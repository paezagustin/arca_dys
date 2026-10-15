import subprocess
import sys
from decimal import Decimal
import pytest
from app.core.config import Settings
from app.core.safety import IntegrationSafetyError, require_live_integrations
from app.services.arca.auth import get_afip_client
from app.services.arca.billing import validate_amount, AFIPBillingError
from app.services.mp import call_api_mp


@pytest.mark.parametrize("environment", ["development", "test"])
def test_nonproduction_rejects_live_even_with_permission_flag(environment):
    with pytest.raises(ValueError):
        Settings.from_env({"ENV": environment, "INTEGRATIONS_MODE": "production",
                           "ALLOW_LIVE_OPERATIONS": "true", "DATABASE_URL": "postgresql://unused"})


@pytest.mark.parametrize("flag", [None, "false", "TRUE", "1"])
def test_production_requires_explicit_opt_in(flag):
    env = {"ENV": "production", "INTEGRATIONS_MODE": "production", "DATABASE_URL": "postgresql://unused"}
    if flag is not None:
        env["ALLOW_LIVE_OPERATIONS"] = flag
    with pytest.raises(ValueError):
        Settings.from_env(env)


def test_production_cannot_silently_simulate():
    with pytest.raises(ValueError):
        Settings.from_env({"ENV": "production", "DATABASE_URL": "postgresql://unused"})


@pytest.mark.parametrize("overrides", [{"ENV": "devselopment"}, {"ENVIRONMENT": "production"},
    {"INTEGRATIONS_MODE": "typo"}, {"LIMITE_FACTURACION_MINIMA": "NaN"},
    {"LIMITE_FACTURACION_MINIMA": "Infinity"}, {"LIMITE_FACTURACION_MINIMA": "-1"},
    {"LIMITE_FACTURACION_MAXIMA": "999"}, {"LIMITE_FACTURACION_MAXIMA": "2000.001"}])
def test_bad_configuration_fails_closed(overrides):
    env = {"ENV": "test", "DATABASE_URL": "postgresql://unused"}
    env.update(overrides)
    with pytest.raises(ValueError):
        Settings.from_env(env)


def test_mock_refuses_real_clients_and_payment_ids():
    with pytest.raises(IntegrationSafetyError):
        require_live_integrations()
    with pytest.raises(IntegrationSafetyError):
        get_afip_client()
    assert call_api_mp("123456789") is None


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "texto", "0", "999.99", "2000000.01", "1000.001"])
def test_invalid_amounts_are_rejected(value):
    with pytest.raises(AFIPBillingError):
        validate_amount(value)


@pytest.mark.parametrize("value", ["1000", "1000.01", "2000000"])
def test_configured_boundaries(value):
    assert Decimal(str(validate_amount(value))) == Decimal(value)


def test_production_does_not_register_simulation_routes():
    import os
    env = dict(os.environ, ENV="production", INTEGRATIONS_MODE="production", ALLOW_LIVE_OPERATIONS="true")
    result = subprocess.run([sys.executable, "-c",
        "from app.main import app; assert not any(r.path.startswith(('/dev', '/test')) for r in app.routes)"],
        env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_web_refuses_stale_schema():
    from sqlalchemy import text
    from app.core.database import engine
    from app.main import app
    from fastapi.testclient import TestClient
    with engine.begin() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        connection.execute(text("UPDATE alembic_version SET version_num='stale'"))
    try:
        with pytest.raises(RuntimeError, match="revisión esperada"):
            with TestClient(app):
                pass
    finally:
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num=:revision"), {"revision": revision})

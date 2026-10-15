import os
import pytest
import requests
from sqlalchemy import text
from sqlalchemy.engine import make_url

if os.environ.get("ENV") != "test" or os.environ.get("INTEGRATIONS_MODE") != "mock":
    raise RuntimeError("La suite requiere ENV=test e INTEGRATIONS_MODE=mock")
target = make_url(os.environ.get("DATABASE_URL", ""))
if target.database != "arca_dys_test" or target.host != "postgres":
    raise RuntimeError("La suite solo puede usar arca_dys_test en el servicio postgres aislado")

from app.core.database import Base, engine
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_data(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Las pruebas no pueden realizar llamadas HTTP externas")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    statement = text("TRUNCATE " + ", ".join('"' + name + '"' for name in Base.metadata.tables) + " RESTART IDENTITY CASCADE")
    with engine.begin() as connection:
        connection.execute(statement)
    yield
    with engine.begin() as connection:
        connection.execute(statement)


@pytest.fixture
def client():
    with TestClient(app) as instance:
        yield instance

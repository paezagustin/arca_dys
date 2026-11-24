from collections import deque
from datetime import UTC, datetime, timedelta
import json
from urllib.parse import urlsplit

import pytest
import requests
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.main import app
from app.models.restock import RestockCatalogSync, RestockProduct
from app.services import dys_catalog, restock_catalog
from app.services.dys_catalog import CatalogReadError, fetch_catalog

BASE_URL = "http://catalog.test:8000"
TOKEN = "example-for-isolated-tests"
SOURCE = restock_catalog.SOURCE
STAMP = "2026-11-23T15:02:10.654321Z"


def row(identifier, **fields):
    return {"id": identifier, "name": "Pasta de avellanas", "description": None, "brand": None,
            "barcode": "000123", "sale_unit": "100 gr", "is_active": True,
            "category": {"id": 5, "name": "Repostería", "is_active": True},
            "created_at": STAMP, "updated_at": STAMP, **fields}


def page(*results, after=None):
    return {"results": list(results), "next_after_id": after}


@pytest.fixture
def http(monkeypatch):
    replies, calls = deque(), []

    def get(session, url, *, params, timeout, allow_redirects, stream):
        assert f"{urlsplit(url).scheme}://{urlsplit(url).netloc}" == BASE_URL
        assert session.headers["Authorization"] == f"Bearer {TOKEN}"
        assert session.headers["Accept"] == "application/json"
        assert not session.trust_env and not allow_redirects and stream
        assert 0 < timeout[0] <= 3 and 0 < timeout[1] <= 8
        calls.append((urlsplit(url).path, dict(params) if params is not None else None))
        if not replies:
            pytest.fail("La consulta realizó una solicitud adicional")
        reply = replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        status, payload, *content_type = reply
        response = requests.Response()
        response.status_code = status
        response.headers["Content-Type"] = content_type[0] if content_type else "application/json; charset=utf-8"
        response._content = json.dumps(payload).encode()
        response._content_consumed = True
        return response

    monkeypatch.setattr(requests.Session, "get", get)
    monkeypatch.setattr(dys_catalog, "PAGE_SIZE", 2)
    yield replies, calls
    assert not replies


def test_complete_pagination_retirement_and_detail_reconciliation(http):
    responses, calls = http
    responses.extend([
        (200, page(row(1, description="Porción de 100 g"), row(2, brand="Marca", sale_unit="unidad"), after=2)),
        (200, page(row(3, is_active=False, barcode=None))),
        (200, row(4, sale_unit="pack")),
        (404, {"error": {"code": "not_found"}}),
        (200, page(row(1), after=1)),
    ])
    snapshot = fetch_catalog(BASE_URL, TOKEN, restock_catalog.CatalogQuery(None, frozenset({"2", "4", "5"})))
    assert snapshot.complete
    assert [product.external_id for product in snapshot.products] == ["1", "2", "3", "4"]
    assert [product.barcode for product in snapshot.products[:3]] == ["000123", "000123", ""]
    assert snapshot.products[1].presentation == "unidad · Marca"
    assert snapshot.products[2].active is False
    assert calls == [
        (dys_catalog.PRODUCTS_PATH, {"limit": 2, "after_id": 0}),
        (dys_catalog.PRODUCTS_PATH, {"limit": 2, "after_id": 2}),
        (dys_catalog.PRODUCTS_PATH + "4/", None),
        (dys_catalog.PRODUCTS_PATH + "5/", None),
        (dys_catalog.PRODUCTS_PATH, {"limit": 1}),
    ]


@pytest.mark.parametrize("response", [
    (200, None), (404, "not found", "text/html"), (401, {"error": {"code": "unauthorized"}}),
    (200, row(7)), (404, {"error": {"code": "other"}}),
])
def test_unexpected_detail_is_never_a_retirement(http, response):
    responses, _ = http
    responses.extend([(200, page()), response])
    with pytest.raises(CatalogReadError):
        fetch_catalog(BASE_URL, TOKEN, restock_catalog.CatalogQuery(None, frozenset({"5"})))


@pytest.mark.parametrize("payload", [page(row(1), row(2), after=3), page(row(1), row(1)), page(row(True)),
                                      page(row(3, barcode=123)), {"results": []}])
def test_rejects_invalid_items_and_cursors(http, payload):
    responses, _ = http
    responses.append((200, payload))
    with pytest.raises(CatalogReadError, match="API v1"):
        fetch_catalog(BASE_URL, TOKEN, restock_catalog.CatalogQuery(None))


def test_incomplete_read_never_advances_and_next_run_reuses_watermark(client, monkeypatch, http):
    responses, calls = http
    now = datetime(2026, 11, 23, 16, 0, tzinfo=UTC)
    monkeypatch.setattr(restock_catalog, "utcnow", lambda: now)
    monkeypatch.setattr(app.state, "restock_catalog_fetch", lambda query: fetch_catalog(BASE_URL, TOKEN, query))
    url = "/faltantes/productos/sincronizar"
    headers = {"Accept": "application/json"}

    responses.append((200, page(row(1, description="Bolsa térmica"), row(2))))
    assert client.post(url, headers=headers).json()["changed"] == 2
    now += timedelta(hours=1)
    responses.extend([(200, page(row(1, name="Nombre nuevo"), row(3), after=3)), requests.Timeout(TOKEN)])
    failed = client.post(url, headers=headers)
    assert failed.status_code == 502 and TOKEN not in failed.text
    assert TOKEN not in client.get("/faltantes/productos").text
    with SessionLocal() as db:
        state = db.get(RestockCatalogSync, SOURCE)
        assert state.watermark == state.last_full_sync_at == datetime(2026, 11, 23, 16, tzinfo=UTC)
        assert state.last_attempt_at == now
        assert state.last_error
        assert db.scalar(select(func.count(RestockProduct.id))) == 2
        assert db.scalar(select(RestockProduct.name).where(RestockProduct.external_id == "1")) == "Pasta de avellanas"

    now += timedelta(hours=1)
    responses.append((200, page(row(1, name="Nombre nuevo", is_active=False))))
    assert client.post(url, headers=headers).json()["changed"] == 1
    expected = "2026-11-23T15:55:00.000000Z"
    assert [params["updated_since"] for _, params in calls[1:]] == [expected] * 3
    with SessionLocal() as db:
        state = db.get(RestockCatalogSync, SOURCE)
        assert state.watermark == now and state.last_error is None
        assert db.scalar(select(RestockProduct.catalog_status).where(RestockProduct.external_id == "2")) == "active"


def test_full_sync_due_reconciles_category_and_missing_products(client, monkeypatch, http):
    responses, calls = http
    now = datetime(2026, 11, 23, 16, 0, tzinfo=UTC)
    monkeypatch.setattr(restock_catalog, "utcnow", lambda: now)
    monkeypatch.setattr(app.state, "restock_catalog_fetch", lambda query: fetch_catalog(BASE_URL, TOKEN, query))
    catalog_url = "/faltantes/productos/sincronizar"
    headers = {"Accept": "application/json"}
    responses.append((200, page(row(1), row(2))))
    assert client.post(catalog_url, headers=headers).json()["changed"] == 2

    now += restock_catalog.FULL_INTERVAL
    category = {"id": 5, "name": "Archivo", "is_active": False}
    responses.extend([(200, page(row(1, category=category))),
                      (404, {"error": {"code": "not_found"}}), (200, page(row(1, category=category)))])
    assert client.post(catalog_url, headers=headers).json()["changed"] == 2
    assert all("updated_since" not in params for _, params in calls if params is not None)
    with SessionLocal() as db:
        rows = {p.external_id: p for p in db.scalars(select(RestockProduct))}
        assert rows["1"].catalog_status == "inactive" and rows["1"].catalog_product_active is True
        assert rows["1"].catalog_category_active is False and rows["1"].catalog_category_name == "Archivo"
        assert rows["2"].catalog_status == "missing"
        assert db.get(RestockCatalogSync, SOURCE).last_full_sync_at == now

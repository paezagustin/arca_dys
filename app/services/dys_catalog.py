"""Cliente de solo lectura para la API interna del catálogo Dulce y Salado v1."""
from datetime import UTC, datetime
import json
import os
from time import monotonic
from urllib.parse import urlsplit

import requests

from app.services.restock_catalog import CatalogCategory, CatalogProduct, CatalogReadError, CatalogSnapshot

PRODUCTS_PATH = "/api/internal/v1/products/"
PAGE_SIZE = 200
MAX_ID = 2**63 - 1
MAX_BODY = 16 * 1024 * 1024
MAX_DURATION = 60
SALE_UNITS = {"100 gr", "kg", "caja", "pack", "paquete", "bolsa", "unidad", "metro"}


def invalid_reply():
    return CatalogReadError("La respuesta del catálogo no coincide con la API v1.")


def api_id(value):
    if type(value) is not int or not 1 <= value <= MAX_ID:
        raise invalid_reply()
    return value


def api_text(value, limit, *, nullable=False):
    if value is None and nullable:
        return ""
    if not isinstance(value, str) or len(value) > limit:
        raise invalid_reply()
    return value


def api_flag(value):
    if type(value) is not bool:
        raise invalid_reply()
    return value


def api_product(values):
    try:
        category = values["category"]
        group = CatalogCategory(api_id(category["id"]), api_text(category["name"], 100), api_flag(category["is_active"]))
        unit = values["sale_unit"]
        if unit not in SALE_UNITS:
            raise invalid_reply()
        for field in ("created_at", "updated_at"):
            when = api_text(values[field], 40)
            if "T" not in when or not when.endswith("Z"):
                raise invalid_reply()
            datetime.fromisoformat(when)
        name = api_text(values["name"], 180)
        if not name.strip():
            raise invalid_reply()
        brand = api_text(values["brand"], 100, nullable=True).strip()
        return CatalogProduct(str(api_id(values["id"])), name, " · ".join(filter(None, (unit, brand))),
                              api_text(values["description"], 65536, nullable=True),
                              api_text(values["barcode"], 100, nullable=True), api_flag(values["is_active"]), group)
    except (KeyError, TypeError, ValueError):
        raise invalid_reply() from None


def _json(session, url, deadline, *, params=None, detail=False):
    try:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise CatalogReadError("La lectura del catálogo superó el tiempo disponible.")
        with session.get(url, params=params, timeout=(min(3, remaining), min(8, remaining)),
                         allow_redirects=False, stream=True) as response:
            if response.status_code == 401:
                raise CatalogReadError("El catálogo rechazó la credencial de servicio.")
            if response.status_code != 200 and not (detail and response.status_code == 404):
                raise CatalogReadError(f"El servicio de catálogo devolvió HTTP {response.status_code}.")
            if response.headers.get("Content-Type", "").partition(";")[0].strip().lower() != "application/json":
                raise invalid_reply()
            content = bytearray()
            for chunk in response.iter_content(65536):
                if monotonic() >= deadline:
                    raise CatalogReadError("La lectura del catálogo superó el tiempo disponible.")
                if len(content) + len(chunk) > MAX_BODY:
                    raise invalid_reply()
                content.extend(chunk)
            try:
                result = json.loads(content)
            except (ValueError, UnicodeError):
                raise invalid_reply() from None
            if response.status_code == 404:
                if result == {"error": {"code": "not_found"}}:
                    return None
                raise invalid_reply()
            if not isinstance(result, dict):
                raise invalid_reply()
            return result
    except requests.RequestException:
        raise CatalogReadError("No se pudo conectar con el catálogo interno.") from None


def _page(payload, after, limit):
    if not isinstance(payload, dict) or set(payload) != {"results", "next_after_id"}:
        raise invalid_reply()
    results, next_after = payload["results"], payload["next_after_id"]
    if not isinstance(results, list) or len(results) > limit:
        raise invalid_reply()
    products = []
    last = after
    for row in results:
        product = api_product(row)
        identifier = int(product.external_id)
        if identifier <= last:
            raise invalid_reply()
        last = identifier
        products.append(product)
    if next_after is not None and (len(products) != limit or api_id(next_after) != last):
        raise invalid_reply()
    return products, next_after


def fetch_catalog(base_url, token, query):
    try:
        base = urlsplit(base_url)
        valid = (base.scheme in {"http", "https"} and base.hostname and base.username is None
                 and base.password is None and base.path in {"", "/"} and not base.query and not base.fragment
                 and (base.port is None or base.port > 0))
    except ValueError:
        valid = False
    if not valid:
        raise CatalogReadError("La dirección del catálogo interno no es válida.")
    url = base_url.rstrip("/") + PRODUCTS_PATH
    deadline = monotonic() + MAX_DURATION
    full = query.updated_since is None
    params = {"limit": PAGE_SIZE, "after_id": 0}
    if not full:
        params["updated_since"] = query.updated_since.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    products = {}
    with requests.Session() as session:
        session.trust_env = False
        session.headers.update({"Accept": "application/json", "Authorization": f"Bearer {token}"})
        while True:
            page, next_after = _page(_json(session, url, deadline, params=params), params["after_id"], PAGE_SIZE)
            products.update((row.external_id, row) for row in page)
            if next_after is None:
                break
            params["after_id"] = next_after
        if full:
            has_missing = False
            for identifier in sorted(query.known_ids - products.keys()):
                if not identifier.isascii() or not identifier.isdecimal() or len(identifier) > 19:
                    raise invalid_reply()
                if identifier != str(api_id(int(identifier))):
                    raise invalid_reply()
                result = _json(session, f"{url}{identifier}/", deadline, detail=True)
                if result is None:
                    has_missing = True
                    continue
                product = api_product(result)
                if product.external_id != identifier:
                    raise invalid_reply()
                products[identifier] = product
            if has_missing:
                # El detalle y una API desactivada usan el mismo 404. Confirmar que el listado siga habilitado.
                _page(_json(session, url, deadline, params={"limit": 1}), 0, 1)
    return CatalogSnapshot(tuple(products.values()), complete=full)


def configured_fetch():
    url = os.getenv("DYS_ARCA_CATALOG_URL", "").strip()
    token = os.getenv("DYS_ARCA_CATALOG_TOKEN", "")
    if not url or not token:
        return None

    def fetch(query):
        return fetch_catalog(url, token, query)

    return fetch

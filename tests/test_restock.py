from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import re
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.main import app
from app.models.business import Supplier
from app.models.restock import RestockCatalogSync, RestockNeed, RestockProduct, RestockProductSupplier, SupplierOrder, SupplierOrderLine
from app.services import restock, restock_catalog
from app.services.listings import business_today


def key():
    return str(uuid4())


@pytest.fixture
def guest():
    with TestClient(app) as browser:
        page = browser.get("/faltantes")
        assert page.status_code == 200
        form = browser.get("/faltantes/productos/nuevo")
        browser.headers["x-csrf-token"] = re.search(r'name="csrf_token" value="([^"]+)"', form.text)[1]
        yield browser


@pytest.fixture
def vendors():
    with SessionLocal() as db:
        parra = Supplier(name="Parra", name_key="parra", contact="WhatsApp: +54 9 11 0000 0000")
        other = Supplier(name="Distribuidora B", name_key="distribuidora b")
        db.add_all([parra, other])
        db.flush()
        ids = parra.id, other.id
        db.commit()
        return ids


def post(guest, path, data=None, status=200):
    reply = guest.post("/faltantes" + path, data=data or {}, headers={"Accept": "application/json"})
    assert reply.status_code == status, reply.text[:1000]
    return reply.json()


def make_product(guest, name, suppliers=(), **fields):
    post(guest, "/productos/nuevo", {"name": name, "supplier_id": list(suppliers), "request_key": key(), **fields})
    with SessionLocal() as db:
        return db.scalar(select(RestockProduct.id).where(RestockProduct.name == name).order_by(RestockProduct.id.desc()))


def make_need(guest, product, **fields):
    post(guest, f"/registrar/{product}", {"request_key": key(), **fields})
    with SessionLocal() as db:
        return db.scalar(select(RestockNeed.id).where(RestockNeed.product_id == product).order_by(RestockNeed.id.desc()))


def draft(vendor, *ids):
    values = {"request_key": key(), "confirmed": "1", "need_id": list(ids)}
    with SessionLocal() as db:
        values["supplier_version"] = db.get(Supplier, vendor).version
        for identifier in ids:
            row = db.get(RestockNeed, identifier)
            values[f"version_{identifier}"] = row.version
            values[f"product_version_{identifier}"] = row.product.version
    return values


def receive(guest, order, actions, *, status=200):
    with SessionLocal() as db:
        row = db.get(SupplierOrder, order)
        values = {"version": row.version}
        for line in row.lines:
            if line.need_id in actions:
                action, notes = actions[line.need_id]
                values[f"outcome_{line.id}"] = action
                values[f"receipt_{line.id}"] = notes
    return post(guest, f"/historial/{order}/recepcion", values, status)


def order_id(result):
    return int(result["url"].split("?")[0].rsplit("/", 1)[1])


def test_products_search_associations_filters_and_preferred(guest, vendors):
    parra, other = vendors
    product = make_product(guest, "Cúrcuma molida", (parra, other, parra), presentation="Bolsa de 25 kg", barcode="001123456", preferred=parra)
    local = make_product(guest, "Envase de vidrio")
    candidate = {"name": "Curcuma molida", "presentation": "Paquete de 100 g", "request_key": key()}
    reply = post(guest, "/productos/nuevo", candidate, 409)
    assert reply["duplicates"][0]["presentation"] == "Bolsa de 25 kg"
    post(guest, "/productos/nuevo", {**candidate, "allow_duplicate": "1"})
    post(guest, "/productos/nuevo", {**candidate, "allow_duplicate": "1"})

    assert "Cúrcuma molida" in guest.get("/faltantes/buscar", params={"q": "CURC bolsa"}).text
    assert "Bolsa de 25 kg" in guest.get("/faltantes/buscar", params={"q": "001123456"}).text
    assert "Curcuma molida" in guest.get("/faltantes/buscar", params={"q": "curcuma 100"}).text
    result = guest.get("/faltantes/productos?vinculo=without").text
    assert "Envase de vidrio" in result and "Cúrcuma molida" not in result
    result = guest.get("/faltantes/productos?vinculo=with").text
    assert "Cúrcuma molida" in result and "Envase de vidrio" not in result

    values = {"name": "Cúrcuma especial", "active": "1", "presentation": "Bolsa de 25 kg", "version": "1",
              "supplier_id": [parra, other], "preferred": other}
    post(guest, f"/productos/{product}", values)
    post(guest, f"/productos/{product}", values, 409)
    post(guest, f"/productos/proveedores/{other}", {"product_id": [product, local, local]})
    linked = guest.get(f"/faltantes/productos/proveedores/{other}").text
    assert "Envase de vidrio" in linked and "Cúrcuma especial" in linked
    with SessionLocal() as db:
        row = db.get(RestockProduct, product)
        assert len(row.suppliers) == 2
        assert [link.supplier_id for link in row.suppliers if link.preferred] == [other]
        assert db.scalar(select(func.count(RestockProduct.id))) == 3
        with pytest.raises(IntegrityError):
            db.execute(insert(RestockProductSupplier).values(product_id=product, supplier_id=parra))
        db.rollback()


def test_shared_shortage_order_retries_and_snapshots(guest, vendors):
    parra, other = vendors
    oats = make_product(guest, "Avena arrollada", vendors, presentation="Bolsa de 25 kg", preferred=parra)
    cocoa = make_product(guest, "Cacao amargo", [parra])
    a, b = make_need(guest, oats), make_need(guest, cocoa)
    quick = {"name": "Etiquetas blancas", "request_key": key()}
    post(guest, "/productos/rapido", quick)
    post(guest, "/productos/rapido", quick)
    duplicate = post(guest, f"/registrar/{oats}", {"request_key": key()}, 409)
    assert "pendiente desde el" in duplicate["detail"]
    assert "Etiquetas blancas" in guest.get("/faltantes?proveedor=none").text
    for vendor in vendors:
        assert "Avena arrollada" in guest.get(f"/faltantes?proveedor={vendor}").text
    options = guest.get(f"/faltantes/pedidos?proveedor={parra}").text
    assert "Avena arrollada" in options and "Cacao amargo" in options and 'data-restock-whatsapp="5491100000000"' in options
    values = {**draft(parra, a), f"quantity_{a}": "2,5", f"unit_{a}": "bolsas", f"notes_{a}": "Para la semana"}
    first = order_id(post(guest, f"/pedidos/{parra}", values))
    assert order_id(post(guest, f"/pedidos/{parra}", values)) == first
    post(guest, f"/pedidos/{parra}", {**values, "order_notes": "Distinto"}, 409)
    assert "Cacao amargo" in guest.get(f"/faltantes/pedidos?proveedor={parra}").text
    assert "Avena arrollada" not in guest.get(f"/faltantes/pedidos?proveedor={other}").text
    ordered = post(guest, f"/registrar/{oats}", {"request_key": key()}, 409)
    assert f"Parra (pedido #{first})" in ordered["detail"]
    assert "Avena arrollada" in guest.get(f"/faltantes?estado=ordered&proveedor={parra}").text
    assert "Avena arrollada" not in guest.get(f"/faltantes?estado=ordered&proveedor={other}").text

    receive(guest, first, {a: ("undelivered", "Se agotó")})
    for vendor in vendors:
        assert "Avena arrollada" in guest.get(f"/faltantes?proveedor={vendor}").text
    second = order_id(post(guest, f"/pedidos/{other}", draft(other, a)))
    receive(guest, second, {a: ("received", "Completo")})
    receive(guest, second, {a: ("received", "Reenviado")}, status=409)
    assert make_need(guest, oats) != a

    post(guest, f"/productos/{oats}", {"name": "Avena renombrada", "presentation": "Saco chico", "active": "0",
                                        "version": "1", "supplier_id": [other]})
    today = business_today().isoformat()
    history = guest.get("/faltantes/historial", params={"q": "avena 25", "estado": "short", "desde": today, "hasta": today}).text
    assert f"#{first} · Parra" in history and f"#{second} · Distribuidora B" not in history
    detail = guest.get(f"/faltantes/historial/{first}").text
    assert "Avena arrollada" in detail and "Bolsa de 25 kg" in detail and "2,5 bolsas" in detail
    assert "No entregado" in detail and "Se agotó" in detail and "Avena renombrada" not in detail
    assert "Recibido completamente" in guest.get(f"/faltantes/historial/{second}").text
    with SessionLocal() as db:
        assert db.get(RestockNeed, b).status == "pending"
        labels = db.scalar(select(RestockProduct.id).where(RestockProduct.name == "Etiquetas blancas"))
        assert db.scalar(select(func.count()).select_from(RestockNeed).where(RestockNeed.product_id == labels)) == 1
    post(guest, f"/productos/proveedores/{other}", {"product_id": [labels]})
    assert "Etiquetas blancas" not in guest.get("/faltantes?proveedor=none").text


def test_partial_receipt_cancellation_and_archived_vendor(guest, client, vendors):
    parra, _ = vendors
    needs = [make_need(guest, make_product(guest, name, [parra])) for name in ("Harina", "Aceite", "Nueces")]
    first, second, third = needs
    order = order_id(post(guest, f"/pedidos/{parra}", draft(parra, *needs)))
    receive(guest, order, {first: ("received", "Llegó completo"), third: ("waiting", "Llega el jueves")})
    detail = guest.get(f"/faltantes/historial/{order}").text
    assert "Recibido parcialmente" in detail and "Llega el jueves" in detail
    receive(guest, order, {second: ("cancelled", "Se anuló")})
    receive(guest, order, {third: ("undelivered", "Sin entrega")})
    new_order = order_id(post(guest, f"/pedidos/{parra}", draft(parra, second, third)))
    receive(guest, new_order, {second: ("cancelled", ""), third: ("cancelled", "")})
    assert "Cerrado con faltantes" in guest.get(f"/faltantes/historial/{order}").text
    filtered = guest.get(f"/faltantes/historial?estado=cancelled&proveedor={parra}").text
    assert f"#{new_order} · Parra" in filtered and f"#{order} · Parra" not in filtered

    attempt = client.post(f"/business/suppliers/{parra}/delete", data={"version": "1"})
    assert attempt.status_code == 422 and "registros vinculados" in attempt.text
    archived = client.post(f"/business/suppliers/{parra}", data={"version": "1", "name": "Parra nuevo", "active": "0"})
    assert archived.status_code == 200
    assert "El proveedor ya no está activo" in guest.get(f"/faltantes/pedidos?proveedor={parra}").text
    assert f"#{order} · Parra" in guest.get(f"/faltantes/historial?proveedor={parra}").text
    post(guest, f"/pedidos/{parra}", draft(parra, second), 409)
    with SessionLocal() as db:
        assert db.get(RestockNeed, first).status == "received"
        assert db.get(RestockNeed, second).status == db.get(RestockNeed, third).status == "pending"


def run_race(*actions):
    ready = Barrier(len(actions), timeout=10)

    def attempt(action):
        with SessionLocal() as db:
            ready.wait()
            try:
                action(db)
                db.commit()
                return "saved"
            except restock.Conflict:
                db.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return sorted(pool.map(attempt, actions))


def test_concurrent_shortage_and_db_unique_active(guest):
    product = make_product(guest, "Avena")
    actions = [lambda db: restock.register_need(db, product, {"request_key": key()}) for _ in range(2)]
    assert run_race(*actions) == ["conflict", "saved"]
    with SessionLocal() as db:
        row = db.scalar(select(RestockNeed))
        identifier, version, previous_key = row.id, row.version, row.request_key
        db.add(RestockNeed(product_id=product, request_key=key(), status="ordered"))
        with pytest.raises(IntegrityError):
            db.commit()
    post(guest, f"/cancelar/{identifier}", {"version": version})
    post(guest, f"/registrar/{product}", {"request_key": previous_key}, 409)
    assert make_need(guest, product) != identifier
    assert "Avena" in guest.get("/faltantes?estado=cancelled").text


def test_concurrent_orders_are_all_or_nothing(guest, vendors):
    shared = make_need(guest, make_product(guest, "Avena", vendors))
    extras = [make_need(guest, make_product(guest, str(vendor), [vendor])) for vendor in vendors]
    picked = [restock.Selection(row, 1, 1, restock.purchase_fields({})) for row in [shared, *extras]]

    def attempt(db, vendor, extra):
        restock.register_order(db, vendor, {"request_key": key(), "supplier_version": "1"}, [picked[0], extra])

    assert run_race(*(lambda db, vendor=vendor, extra=extra: attempt(db, vendor, extra)
                      for vendor, extra in zip(vendors, picked[1:]))) == ["conflict", "saved"]
    with SessionLocal() as db:
        saved = db.scalars(select(SupplierOrder)).one()
        assert {line.need_id for line in saved.lines} == {shared, extras[vendors.index(saved.supplier_id)]}
        assert db.get(RestockNeed, extras[1 - vendors.index(saved.supplier_id)]).status == "pending"
        assert db.scalar(select(func.count(SupplierOrderLine.id))) == 2


def test_invalid_commands_and_transaction_rollback(guest, vendors):
    parra, _ = vendors
    product = make_product(guest, "Cajas", [parra])
    for value in ("NaN", "0", "-1", "8.4.3", "1,1234", "1E3"):
        post(guest, f"/registrar/{product}", {"request_key": key(), "quantity": value}, 422)
    post(guest, "/productos/rapido", {"request_key": key(), "name": "Producto atómico", "quantity": "0"}, 422)
    assert "Producto atómico" not in guest.get("/faltantes/productos").text
    shortage = make_need(guest, product, quantity="1,25", unit="cajas")
    post(guest, f"/editar/{shortage}", {"version": "1", "quantity": "3", "notes": "Más cajas"})
    post(guest, f"/editar/{shortage}", {"version": "1", "quantity": "2"}, 409)
    assert "Más cajas" in guest.get("/faltantes").text
    post(guest, f"/pedidos/{parra}", draft(parra), 422)
    post(guest, f"/pedidos/{parra}", {**draft(parra, shortage), "confirmed": "0"}, 422)
    post(guest, f"/pedidos/{parra}", draft(parra, shortage, shortage), 422)

    with SessionLocal() as db:
        restock.register_order(db, parra, {"request_key": key(), "supplier_version": "1"},
            [restock.Selection(shortage, 2, 1, {"quantity": Decimal("0")})])
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.get(RestockNeed, shortage).status == "pending"
        assert db.get(RestockNeed, shortage).quantity == Decimal("3")
        assert db.scalar(select(func.count(SupplierOrder.id))) == 0
    wrong_dates = guest.get("/faltantes?desde=2099-12-30&hasta=2099-01-01")
    assert wrong_dates.status_code == 422


def test_access_csrf_and_no_store(guest):
    with TestClient(app) as fresh:
        denied = fresh.post("/faltantes/productos/nuevo", data={"request_key": key(), "name": "Fichas"})
        assert denied.status_code == 403
        assert fresh.get("/faltantes/productos").status_code == 200
        denied = fresh.post("/faltantes/productos/nuevo", data={"request_key": key(), "name": "Fichas"})
        assert denied.status_code == 403
    for path in ("", "/pedidos", "/historial", "/productos", "/buscar?q=avena"):
        response = guest.get("/faltantes" + path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
    assert guest.get("/settings", follow_redirects=False).headers["location"] == "/login"


def test_catalog_projection_preserves_links_history_and_local_rows(guest, vendors, monkeypatch):
    parra, _ = vendors
    assert "Conexión con la API pendiente" in guest.get("/faltantes/productos").text
    post(guest, "/productos/sincronizar", status=503)
    local = make_product(guest, "Avena del negocio", [parra])
    item = restock_catalog.CatalogProduct
    snapshot = restock_catalog.CatalogSnapshot
    incoming = snapshot((item("DYS-000001", "Avena del negocio", "Bolsa de 25 kg"),
                         item("DYS-000002", "Avena del negocio", "Paquete chico")), complete=True)
    monkeypatch.setattr(app.state, "restock_catalog_fetch", lambda: incoming, raising=False)
    post(guest, "/productos/sincronizar")
    post(guest, "/productos/sincronizar")
    with SessionLocal() as db:
        product = db.scalar(select(RestockProduct).where(RestockProduct.external_id == "DYS-000001"))
        identifier = product.id
        assert product.version == 1
        assert db.scalar(select(func.count(RestockProduct.id))) == 3
    post(guest, f"/productos/{identifier}", {"version": "1", "active": "1", "supplier_id": [parra], "name": "No reemplazar"})
    need = make_need(guest, identifier)
    before_rename = order_id(post(guest, f"/pedidos/{parra}", draft(parra, need)))
    incoming = snapshot((item("DYS-000001", "Avena renombrada", "Bolsón", active=False),))
    post(guest, "/productos/sincronizar")
    assert "Inactivo en el catálogo" in guest.get("/faltantes?estado=ordered").text
    assert "Avena del negocio" in guest.get(f"/faltantes/historial/{before_rename}").text
    assert "Bolsa de 25 kg" in guest.get(f"/faltantes/historial/{before_rename}").text
    with SessionLocal() as db:
        assert db.get(RestockProduct, identifier).name == "Avena renombrada"
        assert [link.supplier_id for link in db.get(RestockProduct, identifier).suppliers] == [parra]
        assert db.scalar(select(RestockProduct.catalog_status).where(RestockProduct.external_id == "DYS-000002")) == "active"
    receive(guest, before_rename, {need: ("undelivered", "Sin mercadería")})
    after_rename = order_id(post(guest, f"/pedidos/{parra}", draft(parra, need)))
    incoming = snapshot((), complete=True)
    post(guest, "/productos/sincronizar")
    assert "Retirado del catálogo" in guest.get("/faltantes?estado=ordered").text
    receive(guest, after_rename, {need: ("received", "")})
    post(guest, f"/registrar/{identifier}", {"request_key": key()}, 409)

    with SessionLocal() as db:
        last_success = db.get(RestockCatalogSync, restock_catalog.SOURCE).last_success_at
    incoming = snapshot((item("DYS-000001", "No guardar"), item("DYS-000001", "ID repetido")), complete=True)
    post(guest, "/productos/sincronizar", status=502)
    with SessionLocal() as db:
        assert db.get(RestockProduct, local).name == "Avena del negocio"
        assert db.get(RestockProduct, identifier).name == "Avena renombrada"
        assert db.get(RestockCatalogSync, restock_catalog.SOURCE).last_success_at == last_success
    rendered = guest.get("/faltantes/productos").text
    assert "Última sincronización exitosa" in rendered and "Se conserva la última copia local" in rendered
    assert "ID repetido" not in rendered and "No guardar" not in rendered

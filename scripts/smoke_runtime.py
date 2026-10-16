"""Prueba HTTP de la imagen productiva en simulación y DB efímera propia."""
import os
import re
import resource
import subprocess
import sys
import time
from decimal import Decimal
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor
from urllib.error import URLError
from urllib.parse import urlencode
from uuid import uuid4
from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config
from app.core.database import engine
from app.services.listings import business_today


def run():
    if os.environ.get("ENV") != "test" or os.environ.get("INTEGRATIONS_MODE") != "mock" or engine.url.host != "postgres" or engine.url.database != "arca_dys_test":
        raise RuntimeError("Usar exclusivamente la red y base del Compose test")
    name = "runtime_smoke_" + uuid4().hex
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
        db.execute(text(f'CREATE DATABASE "{name}"'))
    scratch = create_engine(engine.url.set(database=name))
    process = None
    try:
        with scratch.begin() as db:
            config = Config("alembic.ini")
            config.attributes["connection"] = db
            command.upgrade(config, "head")
        environment = dict(os.environ, ENV="development", INTEGRATIONS_MODE="mock", ALLOW_LIVE_OPERATIONS="false",
            DATABASE_URL=engine.url.set(database=name).render_as_string(hide_password=False))
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010"],
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        origin = "http://127.0.0.1:8010"

        def get(path):
            return opener.open(origin + path, timeout=10)

        def hidden(body, name):
            match = re.search(r'name="' + re.escape(name) + r'" value="([^"]+)"', body)
            if not match:
                raise RuntimeError("No se encontró el campo esperado del formulario")
            return match.group(1)

        def post(path, data):
            return opener.open(origin + path, data=urlencode(data).encode(), timeout=20)

        for _ in range(120):
            try:
                with get("/health") as response:
                    assert response.status == 200
                break
            except URLError:
                if process.poll() is not None:
                    raise RuntimeError("El servidor no pudo iniciar")
                time.sleep(.25)
        else:
            raise RuntimeError("El servidor no inició dentro del tiempo previsto")
        for path in ("/page/invoice", "/business", "/dashboard", "/salaries", "/fiados"):
            with get(path) as response:
                assert response.status == 200 and "/login" not in response.url
        with get("/business/entries/new?kind=sale") as response:
            page = response.read().decode()
        day = str(business_today())
        with post("/business/entries/new", {"csrf_token": hidden(page, "csrf_token"),
                "entry_key": hidden(page, "entry_key"), "kind": "sale", "entry_date": day,
                "cash_amount": "1000.10", "mp_amount": "500.20"}) as response:
            assert response.status == 200
        for path, fields in (("/salaries", {"employee": "Francisco", "medium": "mercado pago", "amount": "100.05"}),
                ("/fiados", {"customer": "Cliente ficticio runtime", "observation": "Prueba", "paid": "0", "amount": "20.25"})):
            with get(path) as response:
                page = response.read().decode()
            with post(path, dict(fields, csrf_token=hidden(page, "csrf_token"), entry_key=hidden(page, "entry_key"), entry_date=day)) as response:
                assert response.status == 200
        with get("/dashboard?fecha_desde=" + day + "&fecha_hasta=" + day) as response:
            page = response.read().decode()
            assert "$ 1.400,25" in page and "Pago de sueldos" in page
        with get("/login") as response:
            csrf = hidden(response.read().decode(), "login_csrf")
        with post("/login", {"username": "admin", "password": "pruebas-locales", "login_csrf": csrf}) as response:
            assert response.status == 200
        with get("/page/invoice/manual") as response:
            csrf = hidden(response.read().decode(), "csrf_token")
        with post("/ARCA/invoice/manual/preview", {"amount": "1500.55", "csrf_token": csrf}) as response:
            page = response.read().decode()
            preview_path = response.url.removeprefix(origin)
            csrf = hidden(page, "csrf_token")
        with post(preview_path + "/confirm", {"csrf_token": csrf}) as response:
            status_path = response.url.removeprefix(origin)
        for _ in range(80):
            with get(status_path) as response:
                page = response.read().decode()
            match = re.search(r'href="(/ARCA/invoice/\d+/pdf)"', page)
            if match:
                with get(match.group(1)) as response:
                    assert response.read().startswith(b"%PDF")
                break
            time.sleep(.25)
        else:
            raise RuntimeError("La cola fiscal simulada no completó la solicitud")
        with get("/dashboard") as response:
            page = response.read().decode()
            assert response.status == 200 and "Ganancia" in page and "/dashboard/export?" in page
        durations = []
        for _ in range(10):
            started = time.perf_counter()
            with get("/health") as response:
                response.read()
            durations.append(time.perf_counter() - started)
        with scratch.connect() as db:
            assert db.execute(text("SELECT count(*) FROM invoices")).scalar_one() == 1
            assert db.execute(text("SELECT count(*) FROM payments")).scalar_one() == 0
            assert db.execute(text("SELECT cash_amount,mp_amount,amount FROM business_entries")).one() == (Decimal("1000.10"), Decimal("500.20"), Decimal("1500.30"))
            assert db.execute(text("SELECT count(*) FROM salary_payments")).scalar_one() == 1
            assert db.execute(text("SELECT paid FROM customer_credits")).scalar_one() is False
        process.terminate()
        process.wait(timeout=60)
        rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        print("Imagen de ejecución: caja, sueldos, fiados, resumen anónimo, login, CSRF, confirmación, worker, factura simulada y PDF: OK.")
        print(f"Medición del entorno de ensayo: RSS máximo hijo {rss} KiB; health promedio {sum(durations)/len(durations)*1000:.1f} ms.")
        print("Sin accesos externos; base efímera propia eliminada al terminar.")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=60)
        scratch.dispose()
        if not name.startswith("runtime_smoke_") or not name[len("runtime_smoke_"):].isalnum():
            raise RuntimeError("Nombre efímero inesperado; no se eliminó ninguna base")
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
            db.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))


if __name__ == "__main__":
    run()

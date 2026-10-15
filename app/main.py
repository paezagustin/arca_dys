from contextlib import asynccontextmanager
from pathlib import Path
import logging
from threading import Thread, Event
from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import ENV, INTEGRATIONS_MODE
from app.core.database import engine
from app.core.logging import setup_logging
from app.api import invoice, mp, page, page_reports_statistics
from app.api import access, settings as settings_routes

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    # El esquema se cambia exclusivamente mediante Alembic.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if revision != expected:
        raise RuntimeError("La base no está en la revisión esperada; aplicar las migraciones antes de iniciar")
    logger.info("Inicio | entorno=%s | integraciones=%s | migración=%s", ENV, INTEGRATIONS_MODE, revision)
    from app.core.database import SessionLocal
    from app.services.access import ensure_local_admin
    with SessionLocal() as db:
        ensure_local_admin(db)
    stop = Event()
    thread = None
    if ENV != "test":
        from app.services.mp_inbox import worker
        thread = Thread(target=worker, args=(stop,), daemon=True, name="mp-inbox")
        thread.start()
    try:
        yield
    finally:
        stop.set()
        if thread:
            thread.join(timeout=2)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None,
              dependencies=[Depends(access.require_web_access)])
app.state.integrations_mode = INTEGRATIONS_MODE
app.include_router(mp.router)
app.include_router(page.router)
app.include_router(invoice.router)
app.include_router(page_reports_statistics.router)
app.include_router(access.router)
app.include_router(settings_routes.router)
assets = Path(__file__).resolve().parent / "assets"
if assets.is_dir():
    app.mount("/assets", StaticFiles(directory=assets), name="assets")
if ENV in {"development", "test"} and INTEGRATIONS_MODE == "mock":
    from app.api import dev, test_errors
    app.include_router(dev.router)
    app.include_router(test_errors.router)


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/dev" if ENV != "production" and INTEGRATIONS_MODE == "mock" else "/page/invoice")


@app.get("/health", include_in_schema=False)
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "environment": ENV, "integrations": INTEGRATIONS_MODE}


@app.middleware("http")
async def privacy_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if not request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store"
    return response

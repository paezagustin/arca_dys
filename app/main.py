from fastapi import FastAPI
from app.core.database import engine, Base
from app.api import invoice, mp, page
import app.models
from app.core.logging import setup_logging
import logging
from sqlalchemy.exc import OperationalError
import time


setup_logging()
logger = logging.getLogger(__name__)
logger.info("🚀 ARCA API iniciando...")


app = FastAPI()

# Crear tablas
#Base.metadata.create_all(bind=engine)

@app.on_event("startup")
def startup_db():
    retries = 10
    while retries > 0:
        try:
            logger.info("📦 Intentando conectar a la DB...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ DB conectada y tablas creadas")
            return
        except OperationalError as e:
            retries -= 1
            logger.warning("⏳ DB no lista, reintentando en 2s...")
            time.sleep(2)

    logger.error("❌ No se pudo conectar a la DB")
    raise RuntimeError("Database not available")

# Routers
app.include_router(mp.router)
app.include_router(page.router)
app.include_router(invoice.router)

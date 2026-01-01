import os
from dotenv import load_dotenv
from pathlib import Path

# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parents[2]

# Cargar .env
load_dotenv(BASE_DIR / ".env")

# =========================
# APP
# =========================
ENV = os.getenv("ENV", "development")
DEBUG = ENV == "development"

# =========================
# DATABASE
# =========================
# app/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# app/data/app.db
DB_PATH = os.path.join(BASE_DIR, "data", "app.db")
#print("DB:", DB_PATH)

DATABASE_URL = f"sqlite:///{DB_PATH}"
#DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# AFIP / ARCA
# =========================
AFIP_CUIT = os.getenv("AFIP_CUIT")
AFIP_PASSWORD = os.getenv("AFIP_PASSWORD")
AFIP_ACCESS_TOKEN = os.getenv("AFIP_ACCESS_TOKEN")
AFIP_ALIAS = os.getenv("AFIP_ALIAS", "afipsdk")
AFIP_PTO_VTA = int(os.getenv("AFIP_PTO_VTA", 10))

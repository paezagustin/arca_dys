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
ENV = os.getenv("ENV", "devselopment")
DEBUG = ENV == "development"

# =========================
# DATABASE
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está definida en el entorno")


# =========================
# ARCA
# =========================
ARCA_CUIT = os.getenv("ARCA_CUIT")
ARCA_PASSWORD = os.getenv("ARCA_PASSWORD")
ARCA_ACCESS_TOKEN = os.getenv("ARCA_ACCESS_TOKEN")
ARCA_ALIAS = os.getenv("ARCA_ALIAS", "afipsdk")
ARCA_PTO_VTA = int(os.getenv("ARCA_PTO_VTA", 10))
ARCA_CRT_PATH = os.getenv("ARCA_CRT_PATH", "crt_afipsdk.crt")
ARCA_KEY_PATH = os.getenv("ARCA_KEY_PATH", "key_afipsdk.key")
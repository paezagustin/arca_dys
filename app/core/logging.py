import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.config import ENV

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL = logging.DEBUG if ENV == "development" else logging.INFO

def setup_logging():
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    # Log general
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOG_LEVEL)

    # Log errores
    error_handler = RotatingFileHandler(
        LOG_DIR / "errors.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(LOG_LEVEL)

    logging.basicConfig(
        level=LOG_LEVEL,
        handlers=[file_handler, error_handler, console_handler],
    )

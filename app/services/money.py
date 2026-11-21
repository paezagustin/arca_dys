"""Pesos enteros en la interfaz, conservando Decimal para los importes originales."""

from decimal import Decimal
import re

PESO_INPUT_DIGITS = 16
PESO_INPUT_LIMIT = 10**PESO_INPUT_DIGITS


def whole_pesos(value):
    return int(Decimal(str(value)))


def format_whole_pesos(value):
    return "$ " + f"{whole_pesos(value):,}".replace(",", ".")


def require_whole_pesos(value):
    raw = str(value).strip()
    digits = raw.lstrip("0")
    if not raw.isascii() or not raw.isdecimal() or len(digits) > PESO_INPUT_DIGITS:
        raise ValueError("Ingresá un importe en pesos enteros, sin separadores")
    return Decimal(digits or "0")


def require_grouped_pesos(value):
    """Formulario de Fiados: puntos solo como grupos de miles, nunca decimales."""
    raw = str(value).strip()
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)", raw):
        raise ValueError("Ingresá un importe en pesos enteros")
    return require_whole_pesos(raw.replace(".", ""))

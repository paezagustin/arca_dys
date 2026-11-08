from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from pathlib import Path
from fastapi.templating import Jinja2Templates
from app.services.money import PESO_INPUT_LIMIT, format_whole_pesos, whole_pesos

templates = Jinja2Templates(directory="app/templates")


def money(value):
    if value is None:
        return "—"
    amount = Decimal(str(value))
    if not amount.is_finite():
        return "Revisar importe"
    return format_whole_pesos(amount)


def money_input(value):
    try:
        amount = Decimal(str(value))
        return str(whole_pesos(amount)) if amount.is_finite() and 0 <= amount < PESO_INPUT_LIMIT else ""
    except (ArithmeticError, ValueError):
        return ""


def local_date(value):
    if value is None:
        return "Sin fecha"
    if isinstance(value, datetime):
        if value.tzinfo:
            value = value.astimezone(ZoneInfo("America/Argentina/Buenos_Aires"))
        return value.strftime("%d/%m/%Y %H:%M")
    return value.strftime("%d/%m/%Y")


def page_url(request, key, value):
    items = [(k,v) for k,v in request.query_params.multi_items() if k != key]
    items.append((key, str(value)))
    return request.url.path + "?" + urlencode(items)


templates.env.filters.update(money=money, money_input=money_input, local_date=local_date)
templates.env.globals["page_url"] = page_url


def asset_url(name):
    # El navegador debe renovar CSS/JS después de una actualización del sistema.
    return f"/assets/{name}?v={(Path(__file__).parent / 'assets' / name).stat().st_mtime_ns}"


templates.env.globals["asset_url"] = asset_url

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = BASE_DIR / "app" / "templates"


class PDFGenerationError(Exception):
    pass

def generate_invoice_pdf(
    afip_client,
    datos_factura: dict,
    monto_total: float
) -> str:
    """
    Genera el PDF de la factura y devuelve la URL del archivo
    """

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("bill.html")
    cuit = os.getenv("ARCA_CUIT")
    monto_1 = round(monto_total / 2, 2)
    monto_2 = round(monto_total - monto_1, 2)

    fecha = datos_factura["fecha"]
    fecha_str = f"{fecha.day}/{fecha.month}/{fecha.year}"

    html = template.render(
        numero_comprobante=datos_factura["numero_factura"],
        cuit=cuit,
        fecha_comprobante=fecha_str,
        cae=datos_factura["cae"],
        cae_vencimiento=datos_factura["vencimiento_cae"],
        monto_total=monto_total,
        monto_1=monto_1,
        monto_2=monto_2,
    )

    nombre = f"Factura_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    options = {
        "width": 8,
        "marginLeft": 0.4,
        "marginRight": 0.4,
        "marginTop": 0.4,
        "marginBottom": 0.4
    }

    try:
        res = afip_client.ElectronicBilling.createPDF({
            "html": html,
            "file_name": nombre,
            "options": options
        })
    except Exception as e:
        raise PDFGenerationError(str(e))

    return res["file"]

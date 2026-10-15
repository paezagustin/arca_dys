import os

from pathlib import Path
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
from jinja2 import Environment, FileSystemLoader, Template
from app.models.invoice import Invoice
from app.core.config import (
    ARCA_CUIT,
)
import logging

logger = logging.getLogger(__name__)


def generar_pdf_factura(invoice: Invoice) -> bytes:
    """
    Genera el PDF de una factura usando el template bill.html.

    Args:
        invoice: Objeto Invoice de la base de datos

    Returns:
        bytes: Contenido del PDF
    """


    from app.core.config import INTEGRATIONS_MODE
    if INTEGRATIONS_MODE == "mock":
        from app.services.simulation import simulated_pdf
        return simulated_pdf(invoice)
    from playwright.sync_api import sync_playwright
    try:
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        template = env.get_template("bill.html")
        cuit = os.getenv("ARCA_CUIT")

        # Preparar datos para el template
        datos = {
            # Datos de la factura
            "numero_comprobante": invoice.invoice_number,
            "fecha_comprobante": invoice.invoice_date.strftime("%d/%m/%Y"),
            "cae": invoice.cae,
            "cae_vencimiento": invoice.cae_due_date.strftime("%d/%m/%Y"),
            "monto_total": invoice.total_amount,

            # Datos del emisor (desde config)
            "cuit": cuit,

            # Desglose del monto (ejemplo: 50% cotillón, 50% repostería)
            "monto_1": round(invoice.total_amount / 2, 2),
            "monto_2": round(invoice.total_amount - round(invoice.total_amount / 2, 2), 2),
        }
        logger.info('dato cuit', datos['cuit'])
        html_renderizado = template.render(**datos)

    except Exception as e:
        logger.error(f"Error renderizando template: {e}")
        raise

    # Generar PDF
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_renderizado)
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"}
            )
            browser.close()
        #pdf_bytes = HTML(string=html_renderizado).write_pdf()
        logger.info(f"PDF generado para factura {invoice.invoice_number}")
        return pdf_bytes

    except Exception as e:
        logger.error(f"Error generando PDF con WeasyPrint: {e}")
        raise


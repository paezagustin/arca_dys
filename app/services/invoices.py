import os

from app.services.arca.pdf import TEMPLATES_DIR
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader, Template
from app.models.invoice import Invoice
from app.core.config import (
    ARCA_CUIT,
    EMISOR_RAZON_SOCIAL,
    EMISOR_DOMICILIO,
    EMISOR_COND_IVA,
    EMISOR_INGRESOS_BRUTOS,
    RUBRO_PRODUCTOS,
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
    
    # Preparar datos para el template
    datos = {
        # Datos de la factura
        "numero_comprobante": invoice.invoice_number,
        "fecha_comprobante": invoice.invoice_date.strftime("%d/%m/%Y"),
        "cae": invoice.cae,
        "cae_vencimiento": invoice.cae_due_date.strftime("%d/%m/%Y"),
        "monto_total": invoice.total_amount,
        
        # Datos del emisor (desde config)
        "cuit": ARCA_CUIT,
        
        # Desglose del monto (ejemplo: 50% cotillón, 50% repostería)
        "monto_1": round(invoice.total_amount / 2, 2),
        "monto_2": round(invoice.total_amount - round(invoice.total_amount / 2, 2), 2),
    }
    try:
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        template = env.get_template("bill.html")
        cuit = os.getenv("ARCA_CUIT")
        # Renderizar HTML   
        html_renderizado = template.render(**datos)
        
    except Exception as e:
        logger.error(f"Error renderizando template: {e}")
        raise
    
    # Generar PDF
    try:
        pdf_bytes = HTML(string=html_renderizado).write_pdf()
        logger.info(f"PDF generado para factura {invoice.invoice_number}")
        return pdf_bytes
        
    except Exception as e:
        logger.error(f"Error generando PDF con WeasyPrint: {e}")
        raise
from datetime import date
from app.services.arca.auth import get_afip_client
from app.services.arca.billing import generate_invoice
from app.services.arca.pdf import generate_invoice_pdf
from app.repositories.log_invoice_repo import create_log_invoice
from sqlalchemy.orm import Session
import logging

class InvoiceError(Exception):
    pass

logger = logging.getLogger(__name__)

def pipeline_invoice(
    db: Session,
    monto_total: float,
    fecha_hoy: date
) -> str:
    """
    Pipeline completo de facturación ARCA
    """

    try:
        print("Iniciando pipeline de facturación...")
        afip_client = get_afip_client()
        print("AFIP client obtenido.")
        datos_factura = generate_invoice(
            afip_client,
            monto_total,
            fecha_hoy
        )
        print("Factura emitida:", datos_factura)
        pdf_url = generate_invoice_pdf(
            afip_client,
            datos_factura,
            monto_total
        )
        print("PDF de factura generado:", pdf_url)
        print('-'*20)
    except Exception as e:
        # Guarda el error en logs_invoice
        # Lo comente porq falla y tira error 
        # create_log_invoice is an invalid keywork argument for LogInvoice . 
        # create_log_invoice(db=db,error=str(e))
        logger.error(f"AFIP ERROR: {str(e)}")
        raise InvoiceError(str(e))

    return datos_factura,pdf_url

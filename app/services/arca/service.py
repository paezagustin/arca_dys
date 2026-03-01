from datetime import date
from app.services.arca.auth import get_afip_client
from app.services.arca.billing import generate_invoice
from app.services.arca.pdf import generate_invoice_pdf
from app.repositories.log_invoice_repo import create_log_invoice
from sqlalchemy.orm import Session
import logging
import os

from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

def pipeline_invoice(
    db: Session,
    monto_total: float,
    fecha_hoy: date
) -> dict:
    """
    Pipeline de facturación ARCA.
    
    Returns:
        {
            "ok": True/False,
            "datos_factura": {...} o None,  # numero_factura, cae, vencimiento_cae
            "pdf_url": "..." o None,
            "error": "mensaje" si ok=False,
            "tipo": "auth|billing|pdf|system",
            "retryable": True/False
        }
    """
    # 1ra etapa: Autenticación con AFIP
    try:
        
        logger.info("Facturation pipeline started")
        afip_client = get_afip_client()
    except Exception as e:
        error_msg = f"Error to obtain AFIP client: {str(e)}"
        logger.error(error_msg)
        return {
            "ok": False,
            "error": error_msg,
            "tipo": "auth",
            "retryable": False,  # Requiere fix manual (certificados, etc.)
            "datos_factura": None,
            "pdf_url": None
        }


    # 2da etapa: Generar factura
    try:
        logger.info("Obtaining invoice data from AFIP")

        datos_factura = generate_invoice(
            afip_client,
            monto_total,
            fecha_hoy
        )
        if not datos_factura or not datos_factura.get("cae"):
            error_msg = "Invoice generated without CAE."
            logger.error(error_msg)
            return {
                "ok": False,
                "error": error_msg,
                "tipo": "billing",
                "retryable": False,  # Datos inválidos, no reintentar
                "datos_factura": None,
                "pdf_url": None
            }

    except Exception as e:
        error_msg = f"Error generating invoice: {str(e)}"
        logger.warning(error_msg)
        
        return {
            "ok": False,
            "error": error_msg,
            "tipo": "billing",
            "retryable": True,  # Puede ser timeout de ARCA, reintentar
            "datos_factura": None,
            "pdf_url": None
        }
    
    # 3ra etapa: Generar PDF de factura
    pdf_url = None
    pdf_error = None
    try:
        logger.info("Generating invoice PDF")
        
        pdf_url = generate_invoice_pdf(
            afip_client,
            datos_factura,
            monto_total
        )
    
    except Exception as e:
        pdf_error = f"PDF failed: {str(e)}"
        logger.warning(pdf_error)

    
    status = "completed" if pdf_url else "partial"
    logger.info (f"Invoice pipeline completed with status: {status}")
    logger.info (f"Invoice:{datos_factura['numero_factura']} - CAE: {datos_factura.get('cae')} - PDF URL: {pdf_url}")

    return {
        "ok": True,
        "datos_factura": {
            "numero_factura": datos_factura.get("numero_factura"),
            "cae": datos_factura.get("cae"),
            "vencimiento_cae": datos_factura.get("vencimiento_cae")
        },
        "pdf_url": pdf_url,
        "pdf_error": pdf_error,  # Para loguear si falló
        "error": None,
        "tipo": None,
        "retryable": False
    }




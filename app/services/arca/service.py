from datetime import date
from app.services.arca.auth import get_afip_client
from app.services.arca.billing import generate_invoice
from app.services.arca.pdf import generate_invoice_pdf
from app.repositories.log_invoice_repo import create_log_invoice
from sqlalchemy.orm import Session
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class InvoiceError(Exception):
    pass
class InvoiceStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED_RETRY = "failed_retry"      # Se puede reintentar
    FAILED_FATAL = "failed_fatal"      # Requiere intervención manual
    PARTIAL = "partial"                # Factura OK pero PDF falló


@dataclass
class InvoiceResult:
    status: InvoiceStatus
    invoice_number: Optional[str] = None
    cae: Optional[str] = None
    pdf_url: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False


class ARCAError(Exception):
    """Error base de ARCA"""
    def __init__(self, message: str, retryable: bool = False):
        self.message = message
        self.retryable = retryable
        super().__init__(message)

class ARCAAuthError(ARCAError):
    """Error de autenticación - NO retryable (requiere fix manual)"""
    def __init__(self, message: str):
        super().__init__(message, retryable=False)

class ARCAValidationError(ARCAError):
    """Error de validación de datos - NO retryable (datos malos)"""
    def __init__(self, message: str):
        super().__init__(message, retryable=False)

class ARCATransientError(ARCAError):
    """Error temporal - SI retryable (timeout, 5xx)"""
    def __init__(self, message: str):
        super().__init__(message, retryable=True)


logger = logging.getLogger(__name__)

def pipeline_invoice(
    db: Session,
    monto_total: float,
    fecha_hoy: date
) -> InvoiceResult:

    """
    Pipeline completo de facturación ARCA
    """
    # 1ra etapa: Autenticación con AFIP
    try:
        
        logger.info("Facturation pipeline started")
        afip_client = get_afip_client()
    except Exception as e:
        error_msg = f"Error to obtain AFIP client: {str(e)}"
        logger.error(error_msg)
        create_log_invoice(
            db=db,
            level= "CRITICAL",
            phase = "authentication",
            error=error_msg,
            retryable = False
        )
        return InvoiceResult(
            status=InvoiceStatus.FAILED_FATAL,
            error_message=error_msg,
            retryable=False
        )

    # 2da etapa: Generar factura
    try:
        logger.info("Obtaining invoice data from AFIP")

        datos_factura = generate_invoice(
            afip_client,
            monto_total,
            fecha_hoy
        )
        if not datos_factura.get("cae"):
            raise ARCAValidationError("Bill generated without CAE.")

    except ARCAValidationError as e:
        error_msg = f"Validation error - failed: {e.message}"
        logger.error(error_msg)
        create_log_invoice(
            db=db,
            level= "ERROR",
            phase = "billing",
            error=error_msg,
            retryable = False
        )
        return InvoiceResult(
            status=InvoiceStatus.FAILED_FATAL,
            error_message=error_msg,
            retryable=False
        )
    except Exception as e:
        error_msg = f"Error during billing: {str(e)}"
        logger.warning(error_msg)
        create_log_invoice(db = db, level = "WARNING", phase = "billing", error=error_msg, retryable=True)
        return InvoiceResult(
            status=InvoiceStatus.FAILED_RETRY,
            error_message=error_msg,
            retryable=True
        )
    # 3ra etapa: Generar PDF de factura
    pdf_url = None
    try:
        logger.info("Generating invoice PDF")
        
        pdf_url = generate_invoice_pdf(
            afip_client,
            datos_factura,
            monto_total
        )
    
    except Exception as e:
        error_msg = f"Error generating invoice PDF: {str(e)}"
        logger.warning(error_msg)
        create_log_invoice(db = db, level = "WARNING", phase = "pdf_generation", error=error_msg, retryable=True)
        invoice_number = datos_factura.get("numero_factura")

    status = InvoiceStatus.COMPLETED if pdf_url else InvoiceStatus.PARTIAL
    logger.info (f"Invoice pipeline completed with status: {status.value}")
    logger.info (f"Invoice:{datos_factura['numero_factura']} - CAE: {datos_factura.get('cae')} - PDF URL: {pdf_url}")

    return InvoiceResult(
        status=status,
        invoice_number=datos_factura.get("numero_factura"),
        cae=datos_factura.get("cae"),
        pdf_url=pdf_url,
        error_message=None,
        retryable=False
    )

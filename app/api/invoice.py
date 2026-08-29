from datetime import datetime
from http.client import HTTPException
import logging

from requests import Response
from fastapi import Response as FastAPIResponse
from app.models.invoice import Invoice
from app.services.invoices import generar_pdf_factura
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.error_log_repo import create_error_log
from app.repositories.invoice_repo import create_invoice, update_status_invoice
from app.repositories.payment_invoice_repo import link_payment_to_invoice
from app.repositories.payment_repo import (
    get_payments_by_ids_to_bill,
    mark_payment_as_registered,
)
from app.services.arca.service import pipeline_invoice

from dateutil import parser
router = APIRouter(prefix="/ARCA", tags=["ARCA"])
logger = logging.getLogger(__name__)


def _facturar_pagos(
    db: Session,
    pagos: list,
    origen: str = "desconocido",
    requested_ids: list[int] | None = None,
):
    try:
        pagos_ids = [p.id for p in pagos]
        logger.info(
            "Inicio facturacion | origen=%s | requested_ids=%s | pagos_filtrados=%s",
            origen,
            requested_ids if requested_ids is not None else [],
            pagos_ids,
        )

        if not pagos:
            logger.warning("No hay pagos para facturar | origen=%s", origen)
            return HTMLResponse("<h2>No hay pagos para facturar hoy</h2>")

        total = sum(p.mont for p in pagos)
        logger.info(
            "Pipeline ARCA | origen=%s | cantidad_pagos=%s | total=%s",
            origen,
            len(pagos),
            total,
        )

        resultado = pipeline_invoice(
            db=db,
            monto_total=total,
            fecha_hoy=datetime.now().date(),
        )

        if not resultado["ok"]:
            logger.error(
                "Error pipeline ARCA | origen=%s | tipo=%s | retryable=%s | error=%s",
                origen,
                resultado.get("tipo"),
                resultado.get("retryable"),
                resultado.get("error"),
            )
            create_error_log(
                db=db,
                source="facturacion_arca",
                error_type="api_error",
                message=resultado["error"],
                resource_id="INVOICE-ERROR",
                raw_data=resultado,
            )
            return HTMLResponse(
                f"""
                <h1>Error en Facturacion</h1>
                <p><strong>{resultado["error"]}</strong></p>
                <p>Tipo: {resultado["tipo"]}</p>
                <p>Reintentable: {"Si" if resultado["retryable"] else "No"}</p>
                <p>Los pagos NO fueron marcados como facturados.</p>
            """,
                status_code=500,
            )

        logger.info(
            "Factura OK | origen=%s | nro=%s | cae=%s | pagos=%s",
            origen,
            resultado["datos_factura"]["numero_factura"],
            resultado["datos_factura"]["cae"],
            pagos_ids,
        )
        datos_factura = resultado["datos_factura"]
        pdf_url = resultado["pdf_url"]

        invoice = create_invoice(
            db,
            invoice_number=datos_factura["numero_factura"],
            total_amount=total,
            invoice_date=datetime.now().date(),
            cae=datos_factura["cae"],
            cae_due_date = parser.parse(datos_factura['vencimiento_cae']).date(),
            pdf_url=pdf_url,
        )

        for pago in pagos:
            mark_payment_as_registered(db, pago.id)
            link_payment_to_invoice(db, payment_id=pago.id, invoice_id=invoice.id)

        logger.info(
            "Pagos marcados como facturados | origen=%s | invoice_id=%s | pagos=%s",
            origen,
            invoice.id,
            pagos_ids,
        )

        if resultado.get("pdf_error"):
            create_error_log(
                db=db,
                source="facturacion_arca",
                error_type="pdf",
                message=resultado["pdf_error"],
                resource_id=str(invoice.id),
                raw_data={
                    "cae": resultado["datos_factura"]["cae"],
                    "numero_factura": resultado["datos_factura"]["numero_factura"],
                },
            )

            return HTMLResponse(
                f"""
                <h1>Factura Generada</h1>
                <p>Numero: {datos_factura["numero_factura"]}</p>
                <p>CAE: {datos_factura["cae"]}</p>
                <p>Monto: ${total}</p>
                <p>PDF: {pdf_url or "No generado (ver error_logs)"}</p>
            """
            )

        updated = update_status_invoice(
            db=db,
            invoice_id=invoice.id,
            new_status="completed",
        )

        if not updated:
            raise Exception("No se pudo actualizar el estado de la factura")
            
        return HTMLResponse(f"""
                <script>
                    alert("Factura generada correctamente");
                    window.open("{pdf_url}", "_blank");
                    window.location.href = "/page/invoice?success=true";
                </script>
            """
        )

    except Exception as e:
        logger.error(
            "Unexpected Error en facturacion | origen=%s | requested_ids=%s | error=%s",
            origen,
            requested_ids if requested_ids is not None else [],
            str(e),
            exc_info=True,
        )

        create_error_log(
            db=db,
            source="facturacion_arca",
            error_type="system",
            message=f"Error inesperado: {str(e)}",
            raw_data=None,
        )

        return HTMLResponse(
            """
            <h1>Error del Sistema</h1>
            <p>Ocurrio un error inesperado. Contactar soporte.</p>
        """,
            status_code=500,
        )


@router.post("/invoice")
async def facturar_todo(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    raw_ids = form_data.getlist("visible_payment_ids")
    logger.info("Click FACTURAR TODO | raw_ids=%s", raw_ids)

    try:
        payment_ids = [int(pid) for pid in raw_ids]
    except (TypeError, ValueError):
        logger.exception("IDs invalidos en FACTURAR TODO | raw_ids=%s", raw_ids)
        return HTMLResponse(
            "<h2>IDs de pagos invalidos en el listado</h2>", status_code=422
        )

    logger.info("FACTURAR TODO | ids_parseados=%s", payment_ids)
    pagos = get_payments_by_ids_to_bill(db, payment_ids)
    logger.info("FACTURAR TODO | pagos_encontrados=%s", [p.id for p in pagos])
    return _facturar_pagos(
        db=db,
        pagos=pagos,
        origen="facturar_todo",
        requested_ids=payment_ids,
    )


@router.post("/invoice/selected")
async def facturar_seleccionados(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    raw_ids = form_data.getlist("payment_ids")
    logger.info("Click FACTURAR SELECCIONADOS | raw_ids=%s", raw_ids)

    try:
        payment_ids = [int(pid) for pid in raw_ids]
    except (TypeError, ValueError):
        logger.exception("IDs invalidos en FACTURAR SELECCIONADOS | raw_ids=%s", raw_ids)
        return HTMLResponse(
            "<h2>IDs de pagos invalidos en la seleccion</h2>", status_code=422
        )

    logger.info("FACTURAR SELECCIONADOS | ids_parseados=%s", payment_ids)
    pagos = get_payments_by_ids_to_bill(db, payment_ids)
    logger.info("FACTURAR SELECCIONADOS | pagos_encontrados=%s", [p.id for p in pagos])
    return _facturar_pagos(
        db=db,
        pagos=pagos,
        origen="facturar_seleccionados",
        requested_ids=payment_ids,
    )





@router.get('/invoice/{invoice_id}/pdf')
def descargar_pdf_factura(invoice_id: int, db: Session = Depends(get_db)):
    logger.info("Descarga PDF | invoice_id=%s", invoice_id)
    
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        create_error_log(
            db=db,
            source="descarga_pdf",
            error_type="not_found",
            message=f"Factura con ID {invoice_id} no encontrada",
            resource_id=str(invoice_id),
            raw_data=None,
        )
        raise HTTPException(status_code=404, detail="Factura no encontrada")  # ✅ RAISE

    try:
        pdf_bytes = generar_pdf_factura(invoice)  # ✅ Recibir los bytes
    except Exception as e:
        logger.error(f"Error generando PDF para factura {invoice_id}: {e}", exc_info=True)
        create_error_log(
            db=db,
            source="descarga_pdf",
            error_type="pdf_generation",
            message=f"Error generando PDF: {str(e)}",
            resource_id=str(invoice_id),
            raw_data=None,
        )
        raise HTTPException(status_code=500, detail="Error generando PDF")  # ✅ RAISE

    # ✅ Response con los bytes del PDF
    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=factura_{invoice.invoice_number}.pdf"
        }
    )

from datetime import datetime
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.error_log_repo import create_error_log
from app.repositories.invoice_repo import create_invoice, update_status_invoice
from app.repositories.payment_invoice_repo import link_payment_to_invoice
from app.repositories.payment_repo import (
    get_payments_by_ids_to_bill,
    get_today_payments,
    mark_payment_as_registered,
)
from app.services.arca.service import pipeline_invoice

router = APIRouter(prefix="/ARCA", tags=["ARCA"])
logger = logging.getLogger(__name__)


def _facturar_pagos(db: Session, pagos: list):
    try:
        if not pagos:
            return HTMLResponse("<h2>No hay pagos para facturar hoy</h2>")

        total = sum(p.mont for p in pagos)
        logger.info(f"Trying bill: {total}")

        resultado = pipeline_invoice(
            db=db,
            monto_total=total,
            fecha_hoy=datetime.now().date(),
        )

        if not resultado["ok"]:
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
            f"Factura OK | Nro {resultado['datos_factura']['numero_factura']} | CAE {resultado['datos_factura']['cae']}"
        )
        datos_factura = resultado["datos_factura"]
        pdf_url = resultado["pdf_url"]

        invoice = create_invoice(
            db,
            invoice_number=datos_factura["numero_factura"],
            total_amount=total,
            invoice_date=datetime.now().date(),
            cae=datos_factura["cae"],
            cae_due_date=datetime.strptime(
                datos_factura["vencimiento_cae"], "%Y%m%d"
            ).date(),
            pdf_url=pdf_url,
            status="completed",
        )

        for pago in pagos:
            mark_payment_as_registered(db, pago.id)
            link_payment_to_invoice(db, payment_id=pago.id, invoice_id=invoice.id)

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

        return HTMLResponse(
            f"""
                <script>
                    alert("Factura generada correctamente");
                    window.open("{pdf_url}", "_blank");
                    window.history.back();
                </script>
            """
        )

    except Exception as e:
        logger.error(f"Unexpected Error: {e}", exc_info=True)

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
def facturar_todo(db: Session = Depends(get_db)):
    pagos_hoy = get_today_payments(db)
    return _facturar_pagos(db=db, pagos=pagos_hoy)


@router.post("/invoice/selected")
async def facturar_seleccionados(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    raw_ids = form_data.getlist("payment_ids")

    try:
        payment_ids = [int(pid) for pid in raw_ids]
    except (TypeError, ValueError):
        return HTMLResponse(
            "<h2>IDs de pagos invalidos en la seleccion</h2>", status_code=422
        )

    pagos = get_payments_by_ids_to_bill(db, payment_ids)
    return _facturar_pagos(db=db, pagos=pagos)

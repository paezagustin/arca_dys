
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.payment_repo import get_today_payments, mark_payment_as_registered
from app.services.arca.service import pipeline_invoice
from app.repositories.payment_invoice_repo import link_payment_to_invoice
from app.repositories.invoice_repo import create_invoice, update_status_invoice
from fastapi.responses import HTMLResponse
from app.repositories.error_log_repo import create_error_log
from dateutil import parser
import logging
router = APIRouter(prefix="/ARCA", tags=["ARCA"])
logger = logging.getLogger(__name__)

@router.post("/invoice")
def facturar(db: Session = Depends(get_db)):
    try:
        pagos_hoy = get_today_payments(db)
        if not pagos_hoy:
            return HTMLResponse("<h2>No hay pagos para facturar hoy</h2>")
        total = sum(p.mont for p in pagos_hoy)

        logger.info(f"Trying bill: {total}")

        resultado = pipeline_invoice(
            db=db,
            monto_total=total,
            fecha_hoy=datetime.now().date()
        )
        
        if not resultado["ok"]:
            create_error_log(
                db=db,
                source="facturacion_arca",
                error_type="api_error",
                message=resultado["error"],
                resource_id="INVOICE-ERROR",
                raw_data=resultado
            )
            return HTMLResponse(f"""
                <h1>❌ Error en Facturación</h1>
                <p><strong>{resultado["error"]}</strong></p>
                <p>Tipo: {resultado["tipo"]}</p>
                <p>Reintentable: {"Sí" if resultado["retryable"] else "No"}</p>
                <p>Los pagos NO fueron marcados como facturados.</p>
            """, status_code=500)
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
            cae_due_date = parser.parse(datos_factura['vencimiento_cae']).date(),
            pdf_url=pdf_url,
        )
        

        for pago in pagos_hoy:
            #Poner en true el campo registered_arca
            mark_payment_as_registered(db, pago.id)

            link_payment_to_invoice(db,
                                payment_id=pago.id,
                                invoice_id=invoice.id
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
                    "numero_factura": resultado["datos_factura"]["numero_factura"]
                }
            )
        
            return HTMLResponse(f"""
                <h1>✅ Factura Generada</h1>
                <p>Número: {datos_factura["numero_factura"]}</p>
                <p>CAE: {datos_factura["cae"]}</p>
                <p>Monto: ${total}</p>
                <p>PDF: {pdf_url or "No generado (ver error_logs)"}</p>
            """)


        updated = update_status_invoice(
            db=db,
            invoice_id=invoice.id,
            new_status="completed"
        )

        if not updated:
            raise Exception("No se pudo actualizar el estado de la factura")
            
        return HTMLResponse(f"""
                <script>
                    alert("✅ Factura generada correctamente");
                    window.open("{pdf_url}", "_blank");
                    window.history.back();
                </script>
            """)

    except Exception as e:
        # Error inesperado (bug nuestro)
        logger.error(f"Unexpected Error: {e}", exc_info=True)
        
        create_error_log(
            db=db,
            source="facturacion_arca",
            error_type="system",
            message=f"Error inesperado: {str(e)}",
            raw_data=None
        )
        
        return HTMLResponse("""
            <h1>❌ Error del Sistema</h1>
            <p>Ocurrió un error inesperado. Contactar soporte.</p>
        """, status_code=500)



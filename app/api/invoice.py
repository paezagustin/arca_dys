
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.payment_repo import get_today_payments, mark_payment_as_registered
from app.services.arca.service import pipeline_invoice
from app.repositories.payment_invoice_repo import link_payment_to_invoice
from app.repositories.invoice_repo import create_invoice, update_status_invoice
from fastapi.responses import HTMLResponse
from dateutil import parser
import logging

router = APIRouter(prefix="/ARCA", tags=["ARCA"])

logger = logging.getLogger(__name__)

@router.post("/invoice")
def facturar(db: Session = Depends(get_db)):
    try:
        pagos_hoy = get_today_payments(db)
        
        total = sum(p.mont for p in pagos_hoy)

        logger.info(f"Intentando facturar monto total: {total}")

        datos_factura,pdf_url = pipeline_invoice(
            db=db,
            monto_total=total,
            fecha_hoy=datetime.now().date()
        )
        
        logger.info(
        f"Factura OK | Nro {datos_factura['numero_factura']} | CAE {datos_factura['cae']}"
        )   
        
        invoice = create_invoice(db, 
                                invoice_number = datos_factura['numero_factura'],
                                total_amount = total,
                                invoice_date = datetime.now().date(),
                                cae = datos_factura['cae'],
                                cae_due_date = parser.parse(datos_factura['vencimiento_cae']).date(),
                                pdf_url = pdf_url

        )

        for pago in pagos_hoy:
            #Poner en true el campo registered_arca
            mark_payment_as_registered(db, pago.id)

            link_payment_to_invoice(db,
                                payment_id=pago.id,
                                invoice_id=invoice.id
                                )
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
        # ❌ ERROR → mostrar error real
        logger.error("Error al facturar", exc_info=True)
        return HTMLResponse(f"""
            <script>
                alert("❌ Error al facturar:\\n{str(e)}");
                console.error("{str(e)}");
                window.history.back();
            </script>
        """)





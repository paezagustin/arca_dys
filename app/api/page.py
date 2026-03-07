from datetime import date
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
#from app.dependencies.ip_whitelist import ip_whitelist
from app.repositories.payment_repo import get_invoice_report_payments

router = APIRouter(prefix="/page", tags=["Jinja2"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/invoice", response_class=HTMLResponse)
def pageInvoice(
    request: Request,
    facturado: str = Query(default="no"),
    fecha_desde: date | None = Query(default=None),
    fecha_hasta: date | None = Query(default=None),
    db: Session = Depends(get_db)#,
    #_: None = Depends(ip_whitelist)
):
    # Vista inicial: pagos del dia no facturados
    if fecha_desde is None and fecha_hasta is None:
        today = date.today()
        fecha_desde = today
        fecha_hasta = today

    if facturado not in ("todo", "si", "no"):
        facturado = "no"

    pagos = get_invoice_report_payments(
        db=db,
        facturado=facturado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    
    total = sum(p.mont for p in pagos)
    cantidad = len(pagos)
    
    return templates.TemplateResponse(
        "pagina_facturacion.html",
        {
            "request": request,
            "pagos": pagos,
            "total": total,
            "cantidad": cantidad,
            "facturado": facturado,
            "fecha_desde": fecha_desde.isoformat() if fecha_desde else "",
            "fecha_hasta": fecha_hasta.isoformat() if fecha_hasta else "",
        }
    )



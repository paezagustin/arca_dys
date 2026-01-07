from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
#from app.dependencies.ip_whitelist import ip_whitelist
from app.repositories.payment_repo import get_today_payments

router = APIRouter(prefix="/page", tags=["Jinja2"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/invoice", response_class=HTMLResponse)
def pageInvoice(
    request: Request,
    db: Session = Depends(get_db)#,
    #_: None = Depends(ip_whitelist)
):
    pagos = get_today_payments(db)
    
    total = sum(p.mont for p in pagos)
    cantidad = len(pagos)
    
    return templates.TemplateResponse(
        "pagina_facturacion.html",
        {
            "request": request,
            "pagos": pagos,
            "total": total,
            "cantidad": cantidad
        }
    )



from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.payment_repo import (
    get_duplicated_mp_ids,
    get_duplicated_amounts,
)

router = APIRouter(prefix="/page", tags=["Reports"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/reports-statistics", response_class=HTMLResponse)
def pageReportsStatistics(
    request: Request,
    db: Session = Depends(get_db)
):
    pagos_por_mp = get_duplicated_mp_ids(db)
    pagos_por_monto = get_duplicated_amounts(db)

    return templates.TemplateResponse(
        "pagina_reports_statistics.html",
        {
            "request": request,
            "pagos_por_mp": pagos_por_mp,
            "pagos_por_monto": pagos_por_monto
        }
    )
from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.payment import Payment
from app.services.listings import paginate
from app.web import templates

router = APIRouter(prefix="/page", tags=["Auditoría"])


@router.get("/reports-statistics")
@router.get("/reports-stadistics")
def payment_audit(request: Request, ids_page: int = Query(1, ge=1), amounts_page: int = Query(1, ge=1),
                  page_size: int = Query(25, ge=10, le=100), db: Session = Depends(get_db)):
    repeated_ids = select(Payment.id_payment_mp).group_by(Payment.id_payment_mp).having(func.count() > 1)
    repeated_amounts = select(Payment.mont).where(Payment.mont.isnot(None)).group_by(Payment.mont).having(func.count() > 1)
    by_id = select(Payment).where(Payment.id_payment_mp.in_(repeated_ids)).order_by(Payment.id_payment_mp, Payment.id)
    by_amount = select(Payment).where(Payment.mont.in_(repeated_amounts)).order_by(Payment.mont, Payment.id)
    return templates.TemplateResponse(request=request, name="pagina_reports_statistics.html", context={
        "by_id": paginate(db, by_id, ids_page, page_size), "by_amount": paginate(db, by_amount, amounts_page, page_size), "page_size": page_size})

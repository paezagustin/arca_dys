from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.imports import ImportBatch, ImportRow
from app.services.listings import paginate
from app.web import templates

router = APIRouter(prefix="/dashboard", tags=["Resumen"])


@router.get("/history")
def history(request: Request, batch: str = "", page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    selected = db.get(ImportBatch, batch) if batch else db.scalar(select(ImportBatch).where(ImportBatch.state == "confirmed").order_by(ImportBatch.confirmed_at.desc()).limit(1))
    if batch and selected is None:
        raise HTTPException(404, "Lote no encontrado")
    query = select(ImportRow).where(ImportRow.batch_id == (selected.id if selected else ""), ImportRow.kind == "historical",
        ImportRow.row_number >= 65, or_(
            func.json_extract_path_text(ImportRow.raw, func.concat("C", ImportRow.row_number), "type") == "d",
            func.json_extract_path_text(ImportRow.raw, func.concat("H", ImportRow.row_number), "type") == "d"))
    originals = paginate(db, query.order_by(ImportRow.row_number, ImportRow.id), page)
    records = []
    for original in originals.items:
        for block, date_column, received_column, issued_column in (("Izquierdo · C:F", "C", "D", "E"), ("Derecho · H:K", "H", "I", "J")):
            def value(column):
                cell = original.raw.get(f"{column}{original.row_number}", {})
                return cell.get("cached") if cell.get("type") == "f" else cell.get("value")
            period = value(date_column)
            if not isinstance(period, str) or original.raw.get(f"{date_column}{original.row_number}", {}).get("type") != "d":
                continue
            received, issued = value(received_column), value(issued_column)
            try:
                difference = Decimal(str(issued)) - Decimal(str(received))
                if not difference.is_finite():
                    difference = None
            except (ValueError, TypeError, InvalidOperation):
                difference = None
            records.append({"period": period[:7], "block": block, "received": received, "issued": issued,
                "difference": difference, "source": original})
    return templates.TemplateResponse(request=request, name="historical_dashboard.html", context={"batch": selected, "rows": originals, "records": records})

from decimal import Decimal, InvalidOperation
from datetime import timedelta
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.imports import ImportBatch, ImportRow
from app.services.listings import paginate, parse_filters
from app.services.listings import business_today
from app.services.metrics import year_metrics, period_metrics, period_total, change, bounds, expense_groups, chart_bars, MONTHS
from app.web import templates

router = APIRouter(prefix="/dashboard", tags=["Resumen"])


def selected_period(year, month, start, end):
    if not start and not end:
        return (*bounds(year, month), False)
    try:
        filters = parse_filters("todo", start, end, default_today=False)
        if not filters.start or not filters.end:
            raise ValueError("Completá Fecha desde y Fecha hasta")
        return filters.start, filters.end, True
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/export")
def export(year: int | None = Query(None, ge=2, le=9998), month: int = Query(0, ge=0, le=12),
           fecha_desde: str = "", fecha_hasta: str = "", db: Session = Depends(get_db)):
    from app.services.excel_export import export_business
    year = year or business_today().year
    start, end, custom = selected_period(year, month, fecha_desde, fecha_hasta)
    try:
        content = export_business(db, start, end)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    period = f"{start}_{end}" if custom else (f"{year}-{month:02}" if month else str(year))
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="ingresos-egresos-{period}.xlsx"'})


@router.get("")
def dashboard(request: Request, year: int | None = Query(None, ge=2, le=9998), month: int = Query(0, ge=0, le=12),
              fecha_desde: str = "", fecha_hasta: str = "", suppliers_page: int = Query(1, ge=1), categories_page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    year = year or business_today().year
    rows = year_metrics(db, year)
    start, end, custom = selected_period(year, month, fecha_desde, fecha_hasta)
    selected = period_metrics(db, start, end) if custom else (rows[month-1] if month else period_total(rows))
    if custom:
        duration = end - start + timedelta(days=1)
        try:
            prior_start, prior_end = start-duration, start-timedelta(days=1)
            previous = period_metrics(db, prior_start, prior_end)
            comparison_label = f"{prior_start:%d/%m/%Y} al {prior_end:%d/%m/%Y}"
        except OverflowError:
            previous, comparison_label = {key: None for key in selected}, "período anterior"
    elif month > 1:
        previous, comparison_label = rows[month-2], f"{MONTHS[month-2]} {year}"
    else:
        prior = year_metrics(db, year-1)
        previous = prior[-1] if month else period_total(prior)
        comparison_label = f"Diciembre {year-1}" if month else str(year-1)
    suppliers = expense_groups(start, end, suppliers=True)
    categories = expense_groups(start, end)
    bars, maximum = chart_bars(rows)
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"year": year, "month": month, "months": MONTHS,
        "rows": rows, "summary": selected, "comparison_label": comparison_label,
        "changes": {key: change(selected[key], previous[key]) for key in ("sale", "expense_white", "expense_black", "expense", "salary", "result")},
        "custom": custom,
        "start": start, "end": end, "bars": bars, "maximum": maximum,
        "suppliers": paginate(db, suppliers, suppliers_page, scalars=False), "categories": paginate(db, categories, categories_page, scalars=False)})


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

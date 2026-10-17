from datetime import timedelta
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.core.database import get_db
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

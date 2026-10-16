from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.billing import BillingRequest
from app.models.invoice import Invoice
from app.repositories.error_log_repo import create_error_log
from app.services.billing import BillingService, BillingConflict, get_billing_service
from app.services.invoices import generar_pdf_factura
from app.models.settings import BillingPreview
from app.services.billing_preview import preview_invoice, confirm_preview, owns_preview
from app.services.settings import read_settings
from app.web import templates
from app.services.listings import parse_filters, payment_statement
from app.models.payment import Payment
from sqlalchemy import select

router = APIRouter(prefix="/ARCA", tags=["Facturación"])


@router.post("/invoice/manual/preview")
async def manual_preview(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        row = preview_invoice(db, request.state.user.id, manual_amount=form.get("amount"), session_hash=request.state.session_hash)
    except (ValueError, ArithmeticError) as error:
        raise HTTPException(422, str(error)) from error
    return RedirectResponse(f"/ARCA/previews/{row.id}", status_code=303)


@router.get("/previews/{preview_id}")
def preview_page(preview_id: str, request: Request, db: Session = Depends(get_db)):
    row = db.get(BillingPreview, preview_id)
    if row is None or not owns_preview(row, request.state.user.id, request.state.session_hash):
        raise HTTPException(404, "Confirmación no encontrada")
    return templates.TemplateResponse(request=request, name="billing_preview.html", context={"preview": row})


@router.post("/previews/{preview_id}/confirm")
def confirm(preview_id: str, request: Request, db: Session = Depends(get_db), service: BillingService = Depends(get_billing_service)):
    try:
        request_id = confirm_preview(db, preview_id, request.state.user.id, service, session_hash=request.state.session_hash)
    except BillingConflict as error:
        raise HTTPException(409, str(error)) from error
    except (ValueError, ArithmeticError) as error:
        raise HTTPException(422, str(error)) from error
    return RedirectResponse(f"/ARCA/requests/{request_id}", status_code=303)


async def issue_selection(request, field, db):
    form = await request.form()
    try:
        filters = parse_filters(str(form.get("facturado", "no")), form.get("fecha_desde"), form.get("fecha_hasta"))
        eligible_query = payment_statement(filters, eligible=True).with_only_columns(Payment.id)
        if field == "visible_payment_ids":
            ids = sorted(db.scalars(eligible_query))  # TODO el filtro, nunca IDs de la página.
        else:
            ids = sorted(set(int(value) for value in form.getlist(field)))
            eligible = set(db.scalars(eligible_query.where(Payment.id.in_(ids))))
            if set(ids) != eligible:
                raise BillingConflict("Algún pago no pertenece al filtro o dejó de estar disponible. Actualizá el listado.")
        outcome = preview_invoice(db, request.state.user.id, ids, session_hash=request.state.session_hash)
    except BillingConflict as error:
        raise HTTPException(409, str(error)) from error
    except (ValueError, ArithmeticError) as error:
        raise HTTPException(422, str(error)) from error
    return RedirectResponse(f"/ARCA/previews/{outcome.id}", status_code=303)


@router.post("/invoice")
async def facturar_todo(request: Request, db: Session = Depends(get_db)):
    return await issue_selection(request, "visible_payment_ids", db)


@router.post("/invoice/selected")
async def facturar_seleccionados(request: Request, db: Session = Depends(get_db)):
    return await issue_selection(request, "payment_ids", db)


@router.get("/requests/{request_id}")
def request_status(request_id: str, request: Request, db: Session = Depends(get_db)):
    row = db.get(BillingRequest, request_id)
    if row is None:
        raise HTTPException(404, "Solicitud no encontrada")
    return templates.TemplateResponse(request=request, name="billing_request.html", context={"operation": row})


@router.post("/requests/{request_id}/recover")
def recover(request_id: str, service: BillingService = Depends(get_billing_service)):
    try:
        outcome = service.schedule(request_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return RedirectResponse(f"/ARCA/requests/{outcome.request_id}", status_code=303)


@router.post("/requests/{request_id}/retry")
def retry(request_id: str, service: BillingService = Depends(get_billing_service)):
    try:
        outcome = service.schedule(request_id, retry=True)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return RedirectResponse(f"/ARCA/requests/{outcome.request_id}", status_code=303)


@router.get("/invoice/{invoice_id}/pdf")
def descargar_pdf_factura(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Factura no encontrada")
    try:
        content = generar_pdf_factura(invoice)
    except Exception:
        db.rollback()
        create_error_log(db, "descarga_pdf", "pdf_generation", "No se pudo generar el PDF; la factura sigue autorizada.", str(invoice_id))
        raise HTTPException(503, "La factura está guardada. Intentá descargar el PDF nuevamente; no hace falta facturar otra vez.")
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="factura_{invoice.id}.pdf"'})

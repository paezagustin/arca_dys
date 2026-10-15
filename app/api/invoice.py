from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.billing import BillingRequest
from app.models.invoice import Invoice
from app.repositories.error_log_repo import create_error_log
from app.services.billing import BillingService, BillingConflict, get_billing_service
from app.services.invoices import generar_pdf_factura

router = APIRouter(prefix="/ARCA", tags=["Facturación"])
templates = Jinja2Templates(directory="app/templates")


async def issue_selection(request, field, service):
    form = await request.form()
    try:
        ids = [int(value) for value in form.getlist(field)]
        outcome = service.issue(ids)
    except BillingConflict as error:
        raise HTTPException(409, str(error)) from error
    except (ValueError, ArithmeticError) as error:
        raise HTTPException(422, str(error)) from error
    return RedirectResponse(f"/ARCA/requests/{outcome.request_id}", status_code=303)


@router.post("/invoice")
async def facturar_todo(request: Request, service: BillingService = Depends(get_billing_service)):
    return await issue_selection(request, "visible_payment_ids", service)


@router.post("/invoice/selected")
async def facturar_seleccionados(request: Request, service: BillingService = Depends(get_billing_service)):
    return await issue_selection(request, "payment_ids", service)


@router.get("/requests/{request_id}")
def request_status(request_id: str, request: Request, db: Session = Depends(get_db)):
    row = db.get(BillingRequest, request_id)
    if row is None:
        raise HTTPException(404, "Solicitud no encontrada")
    return templates.TemplateResponse(request=request, name="billing_request.html", context={"operation": row})


@router.post("/requests/{request_id}/recover")
def recover(request_id: str, service: BillingService = Depends(get_billing_service)):
    try:
        outcome = service.recover(request_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return RedirectResponse(f"/ARCA/requests/{outcome.request_id}", status_code=303)


@router.post("/requests/{request_id}/retry")
def retry(request_id: str, service: BillingService = Depends(get_billing_service)):
    try:
        outcome = service.recover(request_id, retry=True)
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

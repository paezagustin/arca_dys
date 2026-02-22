import mercadopago

def call_api_mp(resource) -> dict:
    print("Calling MercadoPago API for resource")

    sdk = mercadopago.SDK("APP_USR-2170308863522747-122910-dd6487377aa91decd0d6181626e61da3-427540214")
    payment_info = sdk.payment().get(resource)

    return payment_info["response"]

# app/services/mp_service.py
from datetime import datetime
from app.models.payment import Payment
from app.core.exceptions import MPValidationError, MPAPIError
import httpx

class MPValidationError(Exception):
    """Pago no cumple criterios para facturación"""
    pass

class MPAPIError(Exception):
    """Error comunicándose con MP"""
    pass

async def process_mp_webhook(db: Session, payload: dict) -> Payment:
    """
    Procesa webhook de MP con validaciones exhaustivas.
    """
    
    # 1. EXTRAER DATOS (con defaults seguros)
    resource = payload.get('resource') or payload.get('data', {}).get('id')
    if not resource:
        raise MPValidationError("No se encontró resource ID en payload")
    
    # 2. CONSULTAR API DE MP (con retry)
    payment_data = await fetch_mp_payment(resource)
    
    # 3. VALIDACIONES DE NEGOCIO
    validations = [
        (payment_data.get('status') == 'approved', "Pago no aprobado"),
        (payment_data.get('transaction_amount', 0) > 0, "Monto inválido"),
        (payment_data.get('currency_id') == 'ARS', "Moneda no es ARS"),
        (not payment_data.get('refunds'), "Pago tiene devoluciones"),
    ]
    
    failed_validations = [msg for check, msg in validations if not check]
    
    if failed_validations:
        # Guardar como NO FACTURABLE pero registrado
        payment = create_payment(
            db=db,
            mp_id=payment_data['id'],
            amount=payment_data.get('transaction_amount', 0),
            status=payment_data['status'],
            bill=False,  # <-- NO se factura
            error_reason="; ".join(failed_validations),
            raw_data=payment_data
        )
        logger.info(f"Pago {payment.mp_id} registrado pero NO facturable: {failed_validations}")
        return payment
    
    # 4. PAGO VÁLIDO - Guardar para facturación
    payment = create_payment(
        db=db,
        mp_id=payment_data['id'],
        amount=payment_data['transaction_amount'],
        status='approved',
        bill=True,  # <-- Se facturará hoy
        raw_data=payment_data
    )
    
    logger.info(f"Pago {payment.mp_id} guardado para facturación: ${payment.amount}")
    return payment


async def fetch_mp_payment(resource_id: str, retries: int = 3) -> dict:
    """
    Consulta API de MP con retry exponencial.
    """
    mp_token = config.MP_ACCESS_TOKEN
    
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://api.mercadopago.com/v1/payments/{resource_id}",
                    headers={"Authorization": f"Bearer {mp_token}"}
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.TimeoutException:
            if attempt == retries - 1:
                raise MPAPIError(f"Timeout después de {retries} intentos")
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(f"Timeout MP, reintentando en {wait_time}s...")
            await asyncio.sleep(wait_time)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                # Error de MP, reintentar
                if attempt == retries - 1:
                    raise MPAPIError(f"MP API error {e.response.status_code}")
                await asyncio.sleep(2 ** attempt)
            else:
                # 4xx - No reintentar
                raise MPAPIError(f"MP API client error: {e.response.status_code}")
    
    raise MPAPIError("Max retries exceeded")
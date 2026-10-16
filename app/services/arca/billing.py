from decimal import Decimal
from app.core.config import LIMITE_FACTURACION_MINIMA, LIMITE_FACTURACION_MAXIMA


class AFIPBillingError(ValueError):
    """Importe inválido antes de emitir. Nunca representa una respuesta incierta."""


def validate_amount(monto, minimum=None, maximum=None):
    minimum = LIMITE_FACTURACION_MINIMA if minimum is None else minimum
    maximum = LIMITE_FACTURACION_MAXIMA if maximum is None else maximum
    try:
        value = Decimal(str(monto))
        if not value.is_finite() or value != value.quantize(Decimal("0.01")):
            raise ValueError()
    except (ValueError, ArithmeticError) as error:
        raise AFIPBillingError("El importe debe ser válido con hasta dos decimales") from error
    if not minimum <= value <= maximum:
        raise AFIPBillingError(f"El importe debe estar entre {minimum} y {maximum}")
    if Decimal(str(float(value))) != value:
        raise AFIPBillingError("El importe excede la precisión admitida para enviar al proveedor; no se redondeará automáticamente")
    return value

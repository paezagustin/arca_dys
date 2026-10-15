from datetime import datetime
from app.core.config import ARCA_PTO_VTA, LIMITE_FACTURACION_MINIMA, LIMITE_FACTURACION_MAXIMA
from decimal import Decimal
from afip import Afip

class AFIPBillingError(Exception):
    """Error al emitir comprobante en AFIP"""
    pass


def generate_invoice(
    afip_client: Afip,
    monto_total: float,
    fecha_hoy: datetime.date
) -> dict:
    """
    Emite una factura C en AFIP y devuelve datos fiscales
    """
    monto_total = validate_amount(monto=monto_total) 
    #wsfe = afip_client.webService("wsfe")

    # Parámetros fijos (Factura C - Consumidor Final)
    punto_de_venta = ARCA_PTO_VTA
    tipo_de_factura = 11
    concepto = 1
    tipo_doc = 99
    nro_doc = 0
    condicion_iva_receptor = 5

    # Último comprobante
    last_voucher = afip_client.ElectronicBilling.getLastVoucher(
        punto_de_venta,
        tipo_de_factura
    )

    nro_factura = last_voucher + 1
    fecha_cbte = int(fecha_hoy.strftime("%Y%m%d"))

    data = {
        "CantReg": 1,
        "PtoVta": punto_de_venta,
        "CbteTipo": tipo_de_factura,
        "Concepto": concepto,
        "DocTipo": tipo_doc,
        "DocNro": nro_doc,
        "CbteDesde": nro_factura,
        "CbteHasta": nro_factura,
        "CbteFch": fecha_cbte,
        "ImpTotal": monto_total,
        "ImpTotConc": 0,
        "ImpNeto": monto_total,
        "ImpOpEx": 0,
        "ImpIVA": 0,
        "ImpTrib": 0,
        "MonId": "PES",
        "MonCotiz": 1,
        "CondicionIVAReceptorId": condicion_iva_receptor
    }

    try:
        # afip.py 1.2.0 devuelve por defecto solo CAE/vencimiento. Pedir el
        # FECAESolicitarResult completo, sin la solicitud ni su autenticación.
        res = afip_client.ElectronicBilling.createVoucher(data, return_response=True)
    except Exception as e:
        raise AFIPBillingError(str(e)) from e

    try:
        detail = res["FeDetResp"]["FECAEDetResponse"]
        if isinstance(detail, (list, tuple)):
            if len(detail) != 1:
                raise ValueError("Se esperaba la respuesta de un comprobante")
            detail = detail[0]
        if res["FeCabResp"]["Resultado"] != "A" or detail["Resultado"] != "A" or not detail["CAE"]:
            raise ValueError("El comprobante no está autorizado")
        due_date = datetime.strptime(str(detail["CAEFchVto"]), "%Y%m%d").date().isoformat()
    except (KeyError, TypeError, ValueError) as e:
        raise AFIPBillingError("Respuesta de emisión sin autorización válida") from e

    return {
        "numero_factura": nro_factura,
        "cae": detail["CAE"],
        "vencimiento_cae": due_date,
        "fecha": fecha_hoy,
        "raw_afip_response": res,
    }

def validate_amount(monto: float) -> float:
    """
    Valida monto para AFIP:
    - entre 1000 y 2.000.000
    """
    try:
        value = Decimal(str(monto))
        if not value.is_finite() or value != value.quantize(Decimal("0.01")):
            raise ValueError()
    except (ValueError, ArithmeticError):
        raise AFIPBillingError("El importe debe ser válido con hasta dos decimales")
    if not LIMITE_FACTURACION_MINIMA <= value <= LIMITE_FACTURACION_MAXIMA:
        raise AFIPBillingError(f"El importe debe estar entre {LIMITE_FACTURACION_MINIMA} y {LIMITE_FACTURACION_MAXIMA}")
    return float(value)  # Float se conserva hasta la migración específica del esquema.

from datetime import datetime
from app.core.config import ARCA_PTO_VTA
from decimal import Decimal, ROUND_HALF_UP
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
    fecha_cbte = int(datetime.today().strftime("%Y%m%d"))

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
        res = afip_client.ElectronicBilling.createVoucher(data)
    except Exception as e:
        raise AFIPBillingError(str(e))

    return {
        "numero_factura": nro_factura,
        "cae": res["CAE"],
        "vencimiento_cae": res["CAEFchVto"],
        "fecha": fecha_hoy
    }

def validate_amount(monto: float) -> float:
    """
    Valida monto para AFIP:
    - entre 1000 y 2.000.000
    """
    if monto < 1000:
        raise AFIPBillingError("Monto menor al mínimo permitido (1000)")

    if monto > 2000000:
        raise AFIPBillingError("Monto mayor al máximo permitido (2.000.000)")

    return monto
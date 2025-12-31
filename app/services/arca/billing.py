
# app/services/arca/billing.py

from datetime import datetime
from app.core.config import AFIP_PTO_VTA


class AFIPBillingError(Exception):
    """Error al emitir comprobante en AFIP"""
    pass


def emitir_factura(
    afip_client,
    monto_total: float,
    fecha_hoy: datetime.date
) -> dict:
    """
    Emite una factura C en AFIP y devuelve datos fiscales
    """

    wsfe = afip_client.webService("wsfe")

    # Parámetros fijos (Factura C - Consumidor Final)
    punto_de_venta = AFIP_PTO_VTA
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

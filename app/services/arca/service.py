from datetime import date
from app.services.arca.auth import get_afip_client
from app.services.arca.billing import emitir_factura
from app.services.arca.pdf import generar_pdf_factura


class FacturacionError(Exception):
    pass


def pipeline_facturacion(
    monto_total: float,
    fecha_hoy: date
) -> str:
    """
    Pipeline completo de facturación ARCA
    """

    try:
        afip_client = get_afip_client()
        datos_factura = emitir_factura(
            afip_client,
            monto_total,
            fecha_hoy
        )
        pdf_url = generar_pdf_factura(
            afip_client,
            datos_factura,
            monto_total
        )
    except Exception as e:
        raise FacturacionError(str(e))

    return pdf_url

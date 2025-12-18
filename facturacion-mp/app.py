import os, requests
from datetime import date, datetime
from dateutil import parser
from jinja2 import Template
from afip import Afip

# ================= CONFIG =================
MP_TOKEN = os.getenv("MP_TOKEN")
MP_USER_ID = int(os.getenv("MP_USER_ID"))
CUIT = os.getenv("AFIP_CUIT")
AFIP_TOKEN = os.getenv("AFIP_ACCESS_TOKEN")
AFIP_PASSWORD = os.getenv("AFIP_PASSWORD")
DRY_RUN = os.getenv("DRY_RUN") == "1"

HEADERS = {"Authorization": f"Bearer {MP_TOKEN}"}
URL = "https://api.mercadopago.com/v1/payments/search"

# ================= MERCADO PAGO =================
params = {
    "sort": "date_created",
    "criteria": "desc",
    "limit": 100
}

response = requests.get(URL, params=params, headers=HEADERS)
response.raise_for_status()
results = response.json()["results"]

fecha_hoy = date.today()
monto_total = 0

for pago in results:
    if pago["status"] != "approved":
        continue

    if pago.get("transaction_amount_refunded", 0) > 0:
        continue

    #if pago.get("operation_type") != "regular_payment":
    #    continue

    fecha_pago = parser.isoparse(pago["date_approved"]).date()
    if fecha_pago != fecha_hoy:
        continue

    payer = pago.get("payer_id")
    collector = pago.get("collector", {}).get("id")

    if payer == MP_USER_ID and collector != MP_USER_ID:
        continue  # egreso

    monto_total += pago["transaction_amount"]

monto_total = round(monto_total, 2)

if monto_total == 0:
    print("No hay ingresos para facturar")
    exit()

if DRY_RUN:
    print("DRY RUN OK | Total:", monto_total)
    exit()

# ================= AFIP =================
afip = Afip({"CUIT": CUIT, "access_token": AFIP_TOKEN})

                 #Para produccion es create-cert-prod
cert = afip.createAutomation("create-cert-dev", {
    "cuit": CUIT,
    "username": CUIT,
    "password": AFIP_PASSWORD,
    "alias": "afipsdk"
}, True)
                        #Para produccion es auth-web-service-prod
auth_cert = afip.createAutomation("auth-web-service-dev", {
    
    "cuit": CUIT,
    "username": CUIT,
    "password": AFIP_PASSWORD,
    "alias": "afipsdk",
    "service": "wsfe"
}, True)


cert = cert["data"]
afip = Afip({
    "CUIT": CUIT,
    "access_token": AFIP_TOKEN,
    "cert": cert["cert"],
    "key": cert["key"]
})

punto_venta = 10
tipo_factura = 11

last = afip.ElectronicBilling.getLastVoucher(punto_venta, tipo_factura)
nro_factura = last + 1
fecha_afip = int(datetime.today().strftime("%Y%m%d"))

data = {
    "CantReg": 1,
    "PtoVta": punto_venta,
    "CbteTipo": tipo_factura,
    "Concepto": 1,
    "DocTipo": 99,
    "DocNro": 0,
    "CbteDesde": nro_factura,
    "CbteHasta": nro_factura,
    "CbteFch": fecha_afip,
    "ImpTotal": monto_total,
    "ImpTotConc": 0,
    "ImpNeto": monto_total,
    "ImpOpEx": 0,
    "ImpIVA": 0,
    "ImpTrib": 0,
    "MonId": "PES",
    "MonCotiz": 1,
    "CondicionIVAReceptorId": 5
}

res = afip.ElectronicBilling.createVoucher(data)

if "CAE" not in res:
    raise Exception("AFIP no autorizó la factura")

# ================= PDF =================
with open("bill.html", encoding="utf-8") as f:
    template = Template(f.read())


html = template.render(
    numero_comprobante=nro_factura,
    fecha_comprobante=fecha_hoy.strftime("%d/%m/%Y"),
    monto_total=monto_total,
    cae=res["CAE"],
    cae_vencimiento=res["CAEFchVto"]
)

options = {
        "width": 8, # Ancho de pagina en pulgadas. Usar 3.1 para ticket
        "marginLeft": 0.4, # Margen izquierdo en pulgadas. Usar 0.1 para ticket 
        "marginRight": 0.4, # Margen derecho en pulgadas. Usar 0.1 para ticket 
        "marginTop": 0.4, # Margen superior en pulgadas. Usar 0.1 para ticket 
        "marginBottom": 0.4 # Margen inferior en pulgadas. Usar 0.1 para ticket 
        }

pdf = afip.ElectronicBilling.createPDF({
    "html": html,
    "file_name": f"Factura_{fecha_afip}",
    "options": options
})

print("Factura OK:", pdf["file"])

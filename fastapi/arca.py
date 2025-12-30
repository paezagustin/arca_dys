from afip import Afip
from datetime import datetime
from jinja2 import Template

def pipeline_facturacion(monto_total: float,fecha_hoy : datetime.date):
    print("Generando factura..")
    cuit = '27218282232'
    access_token = "8rprObRewp5l6zc0KkFZ13H6sxbwheuKao7rCGN5ZTtOMWCEJ7zhxs3Fce5Z5PVY"
    pw = "Francisco1109...."
    afip = Afip({
        "CUIT": cuit,
        "access_token": access_token
    })

    #Creación del certificado del día
    data_create_cert = {
        "cuit": cuit,
        "username": cuit,
        "password": pw,
        "alias": "afipsdk"
    }

    #Al verificar el funcionamiento de todo probamos con certificado de producción

                                    #create-cert-prod
    cert_dev = afip.createAutomation("create-cert-dev", data_create_cert, True)

    if cert_dev['status'] == 'complete':

        cert = cert_dev['data'].get('cert')
        key = cert_dev['data'].get('key')

        data_auth_cert = {
            "cuit": cuit,
            "username": cuit,
            "password": pw,
            "alias": "afipsdk",
            "service": "wsfe"
        }
                                        #"auth-web-service-prod"
        auth_cert = afip.createAutomation("auth-web-service-dev", data_auth_cert, True)

        if auth_cert['status'] == 'complete':
            #Podemos empezar a trabajar
            afip = Afip({
                "CUIT": cuit,
                "access_token": access_token,
                "cert": cert,
                "key": key
            })
            ws = afip.webService("wsfe")
            ta = ws.getTokenAuthorization()
            token = ta['token']
            sign = ta['sign']

            # Generación de factura

            punto_de_venta = 10 #Este siempre vamos a usar 10
            concepto = 1 #Productos
            tipo_de_factura = 11 # Factura C
            tipo_de_documento = 99 #Cons. Final
            numero_de_documento = 0 #0 para cons. final 


            # Número de la ultima Factura
            last_voucher = afip.ElectronicBilling.getLastVoucher(punto_de_venta, tipo_de_factura)

            numero_de_factura = last_voucher + 1

            fecha = int(datetime.today().strftime("%Y%m%d"))

            condicion_iva_receptor = 5 #Este hay que verificar

            importe_total = monto_total #Sacado de arriba

            monto_1 = round(monto_total / 2, 2)
            monto_2 = round(monto_total - monto_1, 2)
            fecha_servicio_desde = None
            fecha_servicio_hasta = None
            fecha_vencimiento_pago = None
            data = {
                "CantReg": 1, # Cantidad de facturas a registrar
                "PtoVta": punto_de_venta,
                "CbteTipo": tipo_de_factura, 
                "Concepto": concepto,
                "DocTipo": tipo_de_documento,
                "DocNro": numero_de_documento,
                "CbteDesde": numero_de_factura,
                "CbteHasta": numero_de_factura,
                "CbteFch": fecha,
                #"FchServDesde": fecha_servicio_desde,
                #"FchServHasta": fecha_servicio_hasta,
                #"FchVtoPago": fecha_vencimiento_pago,
                "ImpTotal": importe_total,
                "ImpTotConc": 0, # Importe neto no gravado
                "ImpNeto": importe_total,
                "ImpOpEx": 0,
                "ImpIVA": 0,
                "ImpTrib": 0, # Importe total de tributos
                "MonId": "PES", # Tipo de moneda usada en la factura ("PES" = pesos argentinos) 
                "MonCotiz": 1, # Cotización de la moneda usada (1 para pesos argentinos)  
                "CondicionIVAReceptorId" : condicion_iva_receptor
            }

            # Creamos la Factura 
            res = afip.ElectronicBilling.createVoucher(data)
            
            cae = res['CAE']
            venc_cae = res['CAEFchVto']
            
            #Creación del PDF

            with open("./bill.html", "r", encoding="utf-8") as f:
                template = Template(f.read())
            
            
            # Datos dinámicos
            fecha_comp = f'{fecha_hoy.day}/{fecha_hoy.month}/{fecha_hoy.year}'
            html_renderizado = template.render(
                numero_comprobante=numero_de_factura,
                fecha_comprobante=fecha_comp,
                cuit=cuit,
                producto1="Cotillón",
                producto2 = "Repostería",
                cae= cae,
                cae_vencimiento = venc_cae,
                monto_total= monto_total,
                monto_1 = monto_1,
                monto_2 = monto_2
            )

            
            
            # Nombre para el archivo (sin .pdf)
            name = f"Factura_DyS_{fecha}"

            # Opciones para el archivo
            options = {
            "width": 8, # Ancho de pagina en pulgadas. Usar 3.1 para ticket
            "marginLeft": 0.4, # Margen izquierdo en pulgadas. Usar 0.1 para ticket 
            "marginRight": 0.4, # Margen derecho en pulgadas. Usar 0.1 para ticket 
            "marginTop": 0.4, # Margen superior en pulgadas. Usar 0.1 para ticket 
            "marginBottom": 0.4 # Margen inferior en pulgadas. Usar 0.1 para ticket 
            }

            # Creamos el PDF
            res = afip.ElectronicBilling.createPDF({
            "html": html_renderizado,
            "file_name": name,
            "options": options
            })
            print("PDF creado:", res)
            # Mostramos la url del archivo creado
            return (res["file"])
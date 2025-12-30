from fastapi import FastAPI,Request
from rich import print_json
from api_mp import call_api_mp
from preprocess import pre_process_webhook
from datetime import datetime
import os
import pandas as pd
#from db import insert_payment,get_payments_to_bill
CSV_PATH = "data/payments.csv"

COLUMNS = [
    "id_payment_mp",
    "status",
    "status_detail",
    "date_approved",
    "mont",
    "type_of_paid",
    "bill",
    'registered_arca',
    'id_arca',
    "raw_json"
]

if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
else:
    df = pd.DataFrame(columns=COLUMNS)
    df.to_csv(CSV_PATH, index=False)

app = FastAPI()


@app.post("/mp/webhook")
async def mp_webhook(request: Request):
    try:
        global df

        payload = await request.json()
        print("Received webhook:", payload)
        json_payment = call_api_mp(payload.get('resource'))
        result = pre_process_webhook(json_payment)
        
        #insert_payment(result)
        if result:
            df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
            df.to_csv(CSV_PATH, index=False)
        
    except Exception as e:
        print("Error in webhook endpoint:", e)
    #print(request)
    return {"ok": True}

from arca import pipeline_facturacion
@app.post('/facturar')

async def facturar():
    df = pd.read_csv(CSV_PATH)
    
    fecha_hoy = datetime.now().date().isoformat()
    #pagos = get_payments_to_bill(fecha_hoy)
    #Después habría que ver como se maneja esto
    #gpt me dio esto
    '''
     if not pagos:
        return {
            "status": "no_payments_to_bill",
            "fecha": str(fecha_hoy),
            "cantidad_pagos": 0,
            "monto_total": 0
        }

    monto_total = sum(p["mont"] for p in pagos)

    response_afip = pipeline_facturacion(monto_total, fecha_hoy)   
    '''
    df_to_facturar = df[
        (df['bill'] == True) &
        (pd.to_datetime(df['date_approved'], errors='coerce').dt.date == datetime.now().date())
    ]
    #print(df_to_facturar)
    if df_to_facturar.empty:
        return {
            "status": "no_payments_to_bill",
            "fecha": fecha_hoy,
            "cantidad_pagos": 0,
            "monto_total": 0,
            "link": None
        }
    #Obtener monto total del df_to_facturar
    monto_total = df_to_facturar['mont'].sum()
    print(f"Monto total a facturar: {monto_total}")
    responses = pipeline_facturacion(monto_total,datetime.now().date())
    print(responses)

    return {
        "status": "facturacion_completed",
        "fecha": fecha_hoy,
        "cantidad_pagos": len(df_to_facturar),
        "monto_total": monto_total,
        "link": responses
    }



CSV_PROVEEDORES = "data/proveedores.csv"
@app.post('/cargar_pago_proveedor')
# Para hacer después
async def cargar_pago_proveedor():
    df = pd.read_csv(CSV_PATH)
    return {"status": "carga_completada", "data": df.to_dict(orient="records")}
from app.services.payments import pipeline_facturacion
from datetime import datetime

@app.post('/facturar')

async def facturar():

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
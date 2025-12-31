import mercadopago

def call_api_mp(resource):
    print("Calling MercadoPago API for resource")

    sdk = mercadopago.SDK("APP_USR-2170308863522747-122910-dd6487377aa91decd0d6181626e61da3-427540214")
    payment_info = sdk.payment().get(resource)
    return payment_info["response"]

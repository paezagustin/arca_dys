import requests

MP_TOKEN = "APP_USR-3337144155654311-112318-4495a01dd24505730046dbe4f208939f-427540214"

def get_payment(payment_id):
    url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
    headers = {
        "Authorization": f"Bearer {MP_TOKEN}"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()
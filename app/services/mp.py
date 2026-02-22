import mercadopago
import logging

logger = logging.getLogger(__name__)
def call_api_mp(resource) -> dict:
    

    try:

        sdk = mercadopago.SDK("APP_USR-2170308863522747-122910-dd6487377aa91decd0d6181626e61da3-427540214")
        payment_info = sdk.payment().get(resource)
        if not payment_info:
            logger.error(f"MP API returned no data for resource {resource}")
            return None
        if "response" not in payment_info:
            logger.error(f"MP API response missing 'response' key for resource {resource}")
            return None
        if payment_info.get("status") != 200:
            logger.error(f"MP API error for resource {resource}: {payment_info.get('response')}")
            return None
        
  
        return payment_info["response"]

    except Exception as e:
        logger.error(f"Error calling MP API for resource {resource}: {type(e).__name__}: {e}")
        return None

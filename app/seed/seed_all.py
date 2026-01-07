from app.seed.seed_payments import seed_payments
from app.seed.seed_invoices import seed_invoices
from app.seed.seed_payment_invoices import seed_payment_invoices
from app.core.config import ENV

def run_seeds():
    if ENV != "development":
        raise Exception("❌ Seeds solo permitidos en desarrollo")

    seed_payments()
    seed_invoices()
    seed_payment_invoices()

    print("🎉 Seed completo ejecutado")

if __name__ == "__main__":
    run_seeds()

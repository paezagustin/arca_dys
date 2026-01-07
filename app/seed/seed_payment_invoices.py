from app.core.database import SessionLocal
from app.models.payment_invoice import PaymentInvoice

def seed_payment_invoices():
    db = SessionLocal()

    relations = [
        PaymentInvoice(payment_id=1, invoice_id=1),
        PaymentInvoice(payment_id=2, invoice_id=2)
    ]

    db.add_all(relations)
    db.commit()
    db.close()

    print("✅ Relaciones payment-invoice creadas")

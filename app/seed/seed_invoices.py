from datetime import datetime
from app.core.database import SessionLocal
from app.models.invoice import Invoice

def seed_invoices():
    db = SessionLocal()

    invoices = [
        Invoice(
            invoice_number="F0001-00000001",
            status="issued",
            cae="12345678901234",
            cae_due_date=datetime.now(),
            total_amount=15000.0,
            invoice_date=datetime.now()
        ),
        Invoice(
            invoice_number="F0001-00000002",
            status="failed",
            cae=None,
            cae_due_date=None,
            total_amount=8000.0,
            invoice_date=datetime.now()
        )
    ]

    db.add_all(invoices)
    db.commit()
    db.close()

    print("✅ Invoices seed insertadas")

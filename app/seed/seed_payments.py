from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.payment import Payment

def seed_payments():
    db = SessionLocal()

    payments = [
        Payment(
            id_payment_mp=1001,
            status="approved",
            status_detail="approved",
            mont=15000.0,
            type_of_paid="bank_transfer",
            date_approved=datetime.now() - timedelta(minutes=2),
            bill=False,
            registered_arca=False,
            id_arca="",
            raw_json={"fake": "data"}
        ),
        Payment(
            id_payment_mp=1002,
            status="out_of_time_window",
            status_detail="The payment date is outside the acceptable time window.",
            mont=8000.0,
            type_of_paid="credit_card",
            date_approved=datetime.now() - timedelta(hours=2),
            bill=False,
            registered_arca=False,
            id_arca="",
            raw_json={"fake": "data"}
        )
    ]

    db.add_all(payments)
    db.commit()
    db.close()

    print("✅ Payments seed insertados")

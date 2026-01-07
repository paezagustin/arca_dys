from sqlalchemy.orm import Session
from datetime import datetime
from app.models.log_invoice import LogInvoice

def create_log_invoice(
    db: Session,
    error: str
) -> LogInvoice:

    logInvoice = LogInvoice(
        error=error,
        create_log_invoice=datetime.now()
    )

    db.add(logInvoice)
    db.commit()
    db.refresh(logInvoice)
    return logInvoice
from sqlalchemy.orm import Session
from app.models.error_log import ErrorLog

def create_error_log(
    db: Session,
    source: str,
    error_type: str,
    message: str,
    resource_id: str = None,
    raw_data: dict = None
) -> ErrorLog:
    """
    Crea un registro de error en la base de datos.
    """
    error_log = ErrorLog(
        source=source,
        error_type=error_type,
        message=message,
        resource_id=resource_id,
        raw_data=raw_data
    )
    
    db.add(error_log)
    db.commit()
    db.refresh(error_log)
    
    return error_log


def get_errors(db: Session, source: str = None):
    """
    Obtiene el historial de errores, opcionalmente filtrado por fuente.
    """
    query = db.query(ErrorLog)
    
    if source:
        query = query.filter(ErrorLog.source == source)
    
    return query.order_by(ErrorLog.created_at.desc(), ErrorLog.id.desc()).all()

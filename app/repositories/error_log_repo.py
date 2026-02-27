from sqlalchemy.orm import Session
from app.models.error_log import ErrorLog
from datetime import datetime

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


def mark_error_resolved(
    db: Session,
    error_log_id: int,
    resolved_by: str,
    notes: str = None
) -> ErrorLog:
    """
    Marca un error como resuelto.
    """
    error_log = db.query(ErrorLog).filter(ErrorLog.id == error_log_id).first()
    
    if error_log:
        error_log.resolved = True
        error_log.resolved_at = datetime.utcnow()
        error_log.resolved_by = resolved_by
        error_log.resolution_notes = notes
        
        db.commit()
        db.refresh(error_log)
    
    return error_log


def get_unresolved_errors(db: Session, source: str = None):
    """
    Obtiene errores sin resolver, opcionalmente filtrados por fuente.
    """
    query = db.query(ErrorLog).filter(ErrorLog.resolved == False)
    
    if source:
        query = query.filter(ErrorLog.source == source)
    
    return query.order_by(ErrorLog.created_at.desc()).all()
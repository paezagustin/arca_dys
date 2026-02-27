from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.error_log_repo import create_error_log

router = APIRouter(prefix="/test", tags=["Testing"])

# Tipos de error válidos
VALID_ERROR_TYPES = ["validation", "api_error", "business_rule", "system", "auth", "billing", "pdf"]

@router.post("/error-log")
async def test_error_log(
    error_type: str,
    message: str = "Error de prueba",
    db: Session = Depends(get_db)
):
    """
    Endpoint para testear el sistema de logs de errores.
    Guarda un error simulado en la tabla error_logs.
    VALID_ERROR_TYPES = ["validation", "api_error", "business_rule", "system", "auth", "billing", "pdf"]
    """
    
    # Validar tipo
    if error_type not in VALID_ERROR_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido. Usar: {', '.join(VALID_ERROR_TYPES)}"
        )
    
    # Crear el log
    error_log = create_error_log(
        db=db,
        source="test_endpoint",
        error_type=error_type,
        message=message,
        resource_id=f"TEST-{datetime.now().timestamp()}",
        raw_data={
            "test": True,
            "timestamp": datetime.now().isoformat(),
            "requested_type": error_type
        }
    )
    
    return {
        "status": "logged",
        "error_log_id": error_log.id,
        "error_type": error_type,
        "message": message,
        "created_at": error_log.created_at
    }


@router.get("/error-logs")
async def list_test_errors(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Lista los últimos errores de test para verificar.
    """
    from app.repositories.error_log_repo import get_unresolved_errors
    
    errors = get_unresolved_errors(db, source="test_endpoint")
    
    return {
        "count": len(errors),
        "errors": [
            {
                "id": e.id,
                "created_at": e.created_at,
                "error_type": e.error_type,
                "message": e.message,
                "resolved": e.resolved
            }
            for e in errors[:limit]
        ]
    }
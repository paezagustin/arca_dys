from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from app.core.database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

def now_argentina():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
    
class ErrorLog(Base):
    __tablename__ = "error_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # ¿Cuándo ocurrió?
    created_at = Column(DateTime, default=now_argentina, nullable=False)
    
    # ¿Dónde ocurrió? (webhook_mp, facturacion_arca, etc.)
    source = Column(String(50), nullable=False)
    
    # ¿Qué tipo de error? (validation, api_error, system, etc.)
    error_type = Column(String(50), nullable=False)
    
    # Mensaje descriptivo del error
    message = Column(Text, nullable=False)
    
    # ID del recurso afectado (payment_id, invoice_id, etc.)
    resource_id = Column(String(100), nullable=True)
    
    # Datos crudos para debuggear (payload completo)
    raw_data = Column(JSON, nullable=True)

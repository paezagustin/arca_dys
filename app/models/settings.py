from sqlalchemy import Column, String, Integer, DateTime, JSON, Numeric, ForeignKey
from app.core.database import Base
from app.models.billing import utcnow


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False)


class WebSession(Base):
    __tablename__ = "web_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    csrf_token = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key = Column(String(64), primary_key=True)
    failures = Column(Integer, nullable=False)
    blocked_until = Column(DateTime(timezone=True))


class BusinessSettings(Base):
    __tablename__ = "business_settings"
    id = Column(Integer, primary_key=True)
    values = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False)


class SettingsChange(Base):
    __tablename__ = "settings_changes"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False)
    previous = Column(JSON, nullable=False)
    current = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class BillingPreview(Base):
    __tablename__ = "billing_previews"
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(10), nullable=False)
    payment_ids = Column(JSON, nullable=False)
    total = Column(Numeric(18, 2), nullable=False)
    settings_version = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    request_id = Column(String(36), ForeignKey("billing_requests.id"))

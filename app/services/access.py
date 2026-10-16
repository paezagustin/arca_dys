"""Sesiones revocables en PostgreSQL y contraseñas PBKDF2 de biblioteca estándar."""
from datetime import timedelta
from functools import lru_cache
from hashlib import sha256, pbkdf2_hmac
import hmac
import secrets
from sqlalchemy import select, text, delete
from app.models.billing import utcnow
from app.models.settings import User, WebSession, LoginThrottle
from app.core import config

COOKIE = "arca_session"
LOCAL_PASSWORD = "pruebas-locales"


def hash_password(password):
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres")
    salt = secrets.token_bytes(16)
    digest = pbkdf2_hmac("sha256", password.encode(), salt, 600000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 600000 <= int(iterations) <= 2000000:
            return False
        candidate = pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest)
    except (ValueError, TypeError):
        return False


@lru_cache(maxsize=1)
def local_hash():
    return hash_password(LOCAL_PASSWORD)


def ensure_local_admin(db):
    if config.ENV not in {"development", "test"} or config.INTEGRATIONS_MODE != "mock":
        return
    if db.scalar(select(User.id).where(User.username == "admin")) is None:
        db.add(User(username="admin", password_hash=local_hash(), role="admin"))
        db.commit()


def create_user(db, username, password, role="admin"):
    username = username.strip()
    if not username or len(username) > 80 or role not in {"admin", "operator"}:
        raise ValueError("Usuario o rol inválido")
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise ValueError("Ese usuario ya existe; no se reemplaza su contraseña automáticamente")
    user = User(username=username, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    return user


def authenticate(db, username, password, client_address):
    key = sha256((username.lower() + "|" + client_address).encode()).hexdigest()
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": "login:" + key})
    throttle = db.get(LoginThrottle, key)
    if throttle and throttle.blocked_until and throttle.blocked_until > utcnow():
        return None
    user = db.scalar(select(User).where(User.username == username))
    valid = verify_password(password, user.password_hash if user else local_hash())
    if not valid or user is None:
        if throttle is None:
            throttle = LoginThrottle(key=key, failures=0)
            db.add(throttle)
        throttle.failures += 1
        if throttle.failures >= 10:
            throttle.blocked_until = utcnow() + timedelta(minutes=10)
        db.commit()
        return None
    if throttle:
        db.delete(throttle)
    db.execute(delete(WebSession).where(WebSession.expires_at <= utcnow()))
    db.commit()
    return user


def start_session(db, user=None):
    token = secrets.token_urlsafe(32)
    row = WebSession(token_hash=sha256(token.encode()).hexdigest(), user_id=user.id if user else None,
                     csrf_token=secrets.token_urlsafe(32), expires_at=utcnow() + timedelta(hours=12))
    db.add(row)
    db.commit()
    return token, row.csrf_token


def lookup_session(db, token):
    if not token or len(token) > 100:
        return None
    row = db.get(WebSession, sha256(token.encode()).hexdigest())
    if row is None or row.expires_at <= utcnow():
        return None
    user = db.get(User, row.user_id) if row.user_id else None
    return (row, user) if user or row.user_id is None else None

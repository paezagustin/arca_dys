import hmac
import secrets
from dataclasses import dataclass
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core import config
from app.core.database import get_db
from app.services.access import COOKIE, authenticate, start_session, lookup_session
from app.web import templates

router = APIRouter(tags=["Acceso"])


@dataclass(frozen=True)
class Principal:
    id: int | None
    username: str
    role: str


def public_path(path):
    return path in {"/", "/logout"} or path in {"/page/invoice", "/page/invoice/manual", "/page/billing-requests"} or any(
        path == prefix or path.startswith(prefix + "/") for prefix in ("/ARCA", "/business", "/dashboard"))


async def require_web_access(request: Request, db: Session = Depends(get_db)):
    path = request.url.path
    if path in {"/login", "/health"} or path.startswith("/mp/webhook") or path.startswith("/assets/"):
        return
    identity = lookup_session(db, request.cookies.get(COOKIE))
    if not identity:
        if not public_path(path):
            raise HTTPException(303, headers={"Location": "/login"})
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            raise HTTPException(403, "Actualizá la página y volvé a guardar el formulario.")
        token, _ = start_session(db)
        identity = lookup_session(db, token)
        request.state.new_session_token = token
    session, user = identity
    request.state.user = Principal(user.id, user.username, user.role) if user else Principal(None, "Local", "guest")
    request.state.csrf_token = session.csrf_token
    request.state.session_hash = session.token_hash
    if not public_path(path) and request.state.user.role != "admin":
        if user is None:
            raise HTTPException(303, headers={"Location": "/login"})
        raise HTTPException(403, "Esta sección requiere una cuenta administradora")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = request.headers.get("x-csrf-token")
        if not token:
            form = await request.form(max_files=1, max_fields=250)
            token = str(form.get("csrf_token", ""))
        if not token or not hmac.compare_digest(token.encode(), session.csrf_token.encode()):
            raise HTTPException(403, "La sesión del formulario venció. Actualizá la página e intentá otra vez.")


def require_admin(request: Request):
    if getattr(request.state, "user", None) is None or request.state.user.role != "admin":
        raise HTTPException(403, "Esta configuración requiere una cuenta administradora")


@router.get("/login")
def login_page(request: Request):
    nonce = secrets.token_urlsafe(32)
    response = templates.TemplateResponse(request=request, name="login.html", context={"login_csrf": nonce, "error": None})
    response.set_cookie("arca_login_csrf", nonce, max_age=600, httponly=True,
                        secure=config.ENV == "production", samesite="strict")
    return response


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    nonce = str(form.get("login_csrf", ""))
    if not nonce or not hmac.compare_digest(nonce.encode(), request.cookies.get("arca_login_csrf", "").encode()):
        raise HTTPException(403, "Volvé a abrir la pantalla de acceso para ingresar")
    username, password = str(form.get("username", "")), str(form.get("password", ""))
    if len(username) > 80 or len(password) > 1024:
        raise HTTPException(400, "Usuario o contraseña inválidos")
    user = authenticate(db, username, password, request.client.host if request.client else "unknown")
    if user is None:
        return templates.TemplateResponse(request=request, name="login.html", context={"login_csrf": nonce,
            "error": "No pudimos ingresar. Revisá usuario y contraseña; si hubo muchos intentos, esperá 10 minutos."}, status_code=401)
    token, _ = start_session(db, user)
    # Al ingresar se renueva la identidad y se revoca la sesión anónima anterior.
    previous = lookup_session(db, request.cookies.get(COOKIE))
    if previous:
        db.delete(previous[0])
        db.commit()
    response = RedirectResponse("/page/invoice", status_code=303)
    response.set_cookie(COOKIE, token, max_age=43200, httponly=True, secure=config.ENV == "production", samesite="lax")
    response.delete_cookie("arca_login_csrf")
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    from app.models.settings import WebSession
    db.delete(db.get(WebSession, request.state.session_hash))
    db.commit()
    response = RedirectResponse("/page/invoice", status_code=303)
    response.delete_cookie(COOKIE)
    return response

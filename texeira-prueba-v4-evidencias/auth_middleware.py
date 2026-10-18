"""Middleware de autenticación y sesiones para rutas administrativas de Texeira Travel.

Soporta:
1. Sesiones basadas en cookies firmadas criptográficamente con HMAC-SHA256 (para humanos en navegador).
2. HTTP Basic Auth mediante Authorization header (compatibilidad total para scripts y APIs).
3. Redirección automática a /login con parámetro ?next=... para navegadores web.
4. Endpoints /login (GET, POST) y /logout (GET, POST).
"""
import base64
import hashlib
import hmac
import os
import secrets
import time
import urllib.parse
from typing import Optional
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from login_ui import get_login_html

SESSION_COOKIE_NAME = "texeira_session"
DEFAULT_SESSION_MAX_AGE = 43200     # 12 horas (jornada de trabajo)
REMEMBER_SESSION_MAX_AGE = 604800   # 7 días

# Rutas que requieren autenticación
PROTECTED_PREFIXES = (
    '/dashboard',
    '/handoffs',
    '/catalogo',
    '/api/catalog',
    '/operational-metrics',
    '/history', '/metrics', '/test-chat', '/chat', '/docs', '/redoc', '/openapi.json',
)

# Rutas explícitamente públicas
PUBLIC_PATHS = (
    '/login',
    '/logout',
    '/favicon.ico',
    '/healthz',
    '/webhook',
)


def panel_csrf_token(panel: str) -> str:
    """Consistente entre réplicas; separado por panel y renovado con el secreto."""
    password = os.getenv('ADMIN_PASSWORD', '')
    if not password:
        return secrets.token_urlsafe(32)
    domain = f'texeira:{panel}:csrf:v1'.encode('utf-8')
    return hmac.new(password.encode('utf-8'), domain, 'sha256').hexdigest()


def get_auth_secret() -> str:
    """Retorna la clave secreta para firmar tokens de sesión."""
    return os.getenv('ADMIN_PASSWORD') or 'texeira-local-dev-secret-key-2026'


def create_session_token(username: str, remember: bool = False) -> tuple:
    """
    Crea un token de sesión firmado con HMAC-SHA256.
    Retorna (token: str, max_age_seconds: int).
    """
    now = int(time.time())
    max_age = REMEMBER_SESSION_MAX_AGE if remember else DEFAULT_SESSION_MAX_AGE
    exp = now + max_age
    secret = get_auth_secret()
    payload = f"v1:{username}:{now}:{exp}"
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}", max_age


def verify_session_token(token: str) -> Optional[dict]:
    """
    Verifica la firma, vigencia y usuario del token de sesión.
    Retorna un diccionario con datos de sesión o None si es inválido/expirado.
    """
    if not token or not isinstance(token, str):
        return None

    parts = token.split(":")
    if len(parts) != 5:
        return None

    version, username, created_str, exp_str, sig = parts
    if version != "v1":
        return None

    try:
        created_at = int(created_str)
        exp_at = int(exp_str)
    except ValueError:
        return None

    secret = get_auth_secret()
    expected_payload = f"v1:{username}:{created_str}:{exp_str}"
    expected_sig = hmac.new(secret.encode("utf-8"), expected_payload.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        return None

    now = int(time.time())
    if now > exp_at:
        return None

    # Validar contra ADMIN_USER si está configurado en entorno
    admin_user = os.getenv("ADMIN_USER", "")
    if admin_user and not hmac.compare_digest(username.encode("utf-8"), admin_user.encode("utf-8")):
        return None

    return {"username": username, "created_at": created_at, "expires_at": exp_at}


def _check_session_cookie(request: Request) -> Optional[dict]:
    """Verifica si la petición cuenta con una cookie de sesión válida."""
    cookie_val = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not cookie_val:
        return None
    return verify_session_token(cookie_val)


def sanitize_next_url(url: str, default: str = "/catalogo") -> str:
    """Previene vulnerabilidades de Open Redirect validando que la ruta sea local."""
    if not url:
        return default
    # Debe iniciar con un slash simple y no con '//' o '/\' (URLs externas relativas)
    if url.startswith("/") and not url.startswith("//") and not url.startswith("/\\"):
        return url
    return default


def _is_protected(path: str) -> bool:
    """Verifica si la ruta requiere autenticación."""
    if any(path.startswith(pub) for pub in PUBLIC_PATHS):
        return False
    return any(path.startswith(p) for p in PROTECTED_PREFIXES)


def _check_credentials(request: Request) -> bool:
    """
    Verifica si el usuario está autenticado mediante:
    1. Cookie de sesión válida (texeira_session).
    2. Header Authorization: Basic ... (compatibilidad con APIs, tests y curl).
    3. Loopback en entorno local sin contraseñas configuradas.
    """
    # 1. Comprobar cookie de sesión
    session = _check_session_cookie(request)
    if session:
        return True

    # 2. Comprobar credenciales de entorno para Basic Auth / Loopback
    admin_user = os.getenv('ADMIN_USER', '')
    admin_password = os.getenv('ADMIN_PASSWORD', '')

    if not admin_user or not admin_password:
        return (not admin_user and not admin_password
                and not os.getenv('K_SERVICE')
                and os.getenv('ALLOW_CLOUD_RUN', '').lower() not in {'1', 'true'}
                and request.client is not None
                and request.client.host in {'127.0.0.1', '::1', 'testclient'})

    # 3. Comprobar header Authorization HTTP Basic
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Basic '):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
            user, password = decoded.split(':', 1)
            return (hmac.compare_digest(user.encode(), admin_user.encode()) and
                    hmac.compare_digest(password.encode(), admin_password.encode()))
        except Exception:
            return False

    return False


def is_secure_connection(request: Request) -> bool:
    """Determina si la conexión actual es segura (HTTPS o Cloud Run detrás de proxy SSL)."""
    return (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").lower() == "https"
        or bool(os.getenv("K_SERVICE"))
    )


def install_auth(app):
    """Instala las rutas de /login, /logout y el middleware de protección en FastAPI."""

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        # Si ya cuenta con sesión válida, redirigir directo
        if _check_credentials(request):
            target = sanitize_next_url(request.query_params.get("next", ""), default="/catalogo")
            return RedirectResponse(url=target, status_code=303)

        error_msg = ""
        err_param = request.query_params.get("error", "")
        if err_param == "invalid":
            error_msg = "Usuario o contraseña incorrectos. Verifica tus credenciales."
        elif err_param == "session_expired":
            error_msg = "Tu sesión ha expirado. Por favor, inicia sesión nuevamente."

        success_msg = ""
        if request.query_params.get("logout") == "1":
            success_msg = "Has cerrado sesión de forma segura."

        next_url = sanitize_next_url(request.query_params.get("next", ""), default="/catalogo")
        html = get_login_html(
            error=error_msg,
            success_msg=success_msg,
            next_url=next_url
        )
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.post("/login")
    async def login_submit(request: Request):
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                body = await request.json()
            except Exception:
                body = {}
            username = str(body.get("username", "")).strip()
            password = str(body.get("password", "")).strip()
            remember = bool(body.get("remember_me", False))
            next_param = str(body.get("next", "")).strip()
            is_ajax = True
        else:
            try:
                form = await request.form()
            except Exception:
                form = {}
            username = str(form.get("username", "")).strip()
            password = str(form.get("password", "")).strip()
            remember = str(form.get("remember_me", "")).lower() in ("1", "true", "on", "yes")
            next_param = str(form.get("next", "")).strip()
            is_ajax = False

        admin_user = os.getenv("ADMIN_USER", "")
        admin_password = os.getenv("ADMIN_PASSWORD", "")

        # Verificación de credenciales
        valid_user = bool(admin_user and hmac.compare_digest(username.encode(), admin_user.encode()))
        valid_pwd = bool(admin_password and hmac.compare_digest(password.encode(), admin_password.encode()))

        # Modo desarrollo local sin credenciales configuradas
        if not admin_user and not admin_password:
            valid_user = True
            valid_pwd = True

        target_url = sanitize_next_url(next_param, default="/catalogo")

        if valid_user and valid_pwd:
            session_token, max_age = create_session_token(username or "admin", remember=remember)
            secure_cookie = is_secure_connection(request)

            if is_ajax:
                resp = JSONResponse({"ok": True, "redirect": target_url})
            else:
                resp = RedirectResponse(url=target_url, status_code=303)

            resp.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=session_token,
                max_age=max_age,
                httponly=True,
                samesite="lax",
                secure=secure_cookie,
                path="/"
            )
            return resp

        # Credenciales incorrectas
        if is_ajax:
            return JSONResponse({"ok": False, "error": "Usuario o contraseña incorrectos."}, status_code=401)

        html = get_login_html(
            error="Usuario o contraseña incorrectos. Verifica tus credenciales.",
            next_url=target_url,
            username_val=username
        )
        return HTMLResponse(html, status_code=401, headers={"Cache-Control": "no-store"})

    @app.get("/logout")
    async def logout_get(request: Request):
        resp = RedirectResponse(url="/login?logout=1", status_code=303)
        resp.delete_cookie(key=SESSION_COOKIE_NAME, path="/", samesite="lax")
        return resp

    @app.post("/logout")
    async def logout_post(request: Request):
        is_ajax = "application/json" in request.headers.get("content-type", "").lower()
        if is_ajax:
            resp = JSONResponse({"ok": True, "redirect": "/login?logout=1"})
        else:
            resp = RedirectResponse(url="/login?logout=1", status_code=303)
        resp.delete_cookie(key=SESSION_COOKIE_NAME, path="/", samesite="lax")
        return resp

    @app.middleware('http')
    async def auth_middleware(request: Request, call_next):
        path = request.url.path

        # Rutas protegidas
        if _is_protected(path):
            if not _check_credentials(request):
                # Determinar si el solicitante es una API / script o un navegador humano
                accept = request.headers.get('accept', '').lower()
                x_req = request.headers.get('x-requested-with', '').lower()
                auth_hdr = request.headers.get('authorization', '')

                is_api_request = (
                    path.startswith('/api/')
                    or path == '/test-chat'
                    or 'application/json' in accept
                    or x_req == 'xmlhttprequest'
                    or auth_hdr.startswith('Basic ')
                )

                if is_api_request:
                    return Response(
                        content='Acceso restringido. Ingresa tus credenciales.',
                        status_code=401,
                        headers={'WWW-Authenticate': 'Basic realm="Panel Administrativo Texeira"'},
                        media_type='text/plain',
                    )

                # Petición desde navegador web -> Redirigir a pantalla de login
                query_str = str(request.url.query)
                full_path = path + (f"?{query_str}" if query_str else "")
                next_encoded = urllib.parse.quote(full_path, safe='')
                return RedirectResponse(url=f"/login?next={next_encoded}", status_code=303)

        return await call_next(request)


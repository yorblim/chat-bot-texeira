"""Middleware de autenticación HTTP Basic para rutas administrativas.

En la nube (Cloud Run), protege /dashboard, /handoffs y /operational-metrics
con usuario y contraseña configurables via variables de entorno.
En local, no bloquea nada a menos que ADMIN_USER y ADMIN_PASSWORD estén definidos.
"""
import base64
import hmac
import os
from fastapi import Request
from fastapi.responses import Response


# Rutas que requieren autenticación
PROTECTED_PREFIXES = (
    '/dashboard',
    '/handoffs',
    '/operational-metrics',
)


def _is_protected(path: str) -> bool:
    """Verifica si la ruta requiere autenticación."""
    return any(path.startswith(p) for p in PROTECTED_PREFIXES)


def _check_credentials(request: Request) -> bool:
    """Verifica credenciales HTTP Basic Auth del header Authorization."""
    admin_user = os.getenv('ADMIN_USER', '')
    admin_password = os.getenv('ADMIN_PASSWORD', '')

    # Si no hay credenciales configuradas, permitir acceso libre
    if not admin_user or not admin_password:
        return True

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Basic '):
        return False

    try:
        decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
        user, password = decoded.split(':', 1)
        return (hmac.compare_digest(user.encode(), admin_user.encode()) and
                hmac.compare_digest(password.encode(), admin_password.encode()))
    except Exception:
        return False


def install_auth(app):
    """Instala el middleware de autenticación en la app FastAPI."""

    @app.middleware('http')
    async def auth_middleware(request: Request, call_next):
        if _is_protected(request.url.path):
            if not _check_credentials(request):
                return Response(
                    content='Acceso restringido. Ingresa tus credenciales.',
                    status_code=401,
                    headers={'WWW-Authenticate': 'Basic realm="Panel Administrativo Texeira"'},
                    media_type='text/plain',
                )
        return await call_next(request)

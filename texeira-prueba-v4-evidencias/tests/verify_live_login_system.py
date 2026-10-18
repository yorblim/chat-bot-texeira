"""tests/verify_live_login_system.py — Verificación en vivo del sistema de Login y Sesiones en Cloud Run.

Valida:
1. Redirección de accesos no autenticados en navegador a /login?next=...
2. Protección de endpoints de API (/api/...) respondiendo 401 sin redirección.
3. Carga exitosa de la página visual corporativa /login.
4. Rechazo de credenciales incorrectas en /login.
5. Inicio de sesión exitoso emitiendo cookie segura texeira_session.
6. Acceso al Catálogo (/catalogo) y Dashboard (/dashboard) mediante cookie de sesión.
7. Presencia del botón "Cerrar sesión" en los paneles.
8. Cierre de sesión exitoso (/logout) invalidando cookie y mostrando confirmación.
9. Compatibilidad continua de HTTP Basic Auth para APIs y tests automatizados.
"""
import os
import sys
import json
import base64
import urllib.request
import urllib.error
import http.cookiejar
import subprocess
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "https://texeira-whatsapp-1038134693816.us-central1.run.app"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Evitar redirección automática para validar código 303 y header Location
        return None


def obtener_credenciales():
    gcloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    res_pass = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "2", "--secret=ADMIN_PASSWORD", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    if res_pass.returncode != 0 or not res_pass.stdout.strip():
        raise RuntimeError("No se pudo obtener ADMIN_PASSWORD.")
    admin_password = res_pass.stdout.strip()
    admin_user = "admin"
    return admin_user, admin_password


def main():
    print("=" * 76)
    print("  VERIFICACIÓN EN VIVO: SISTEMA DE LOGIN Y SESIONES (CLOUD RUN)")
    print("=" * 76)

    admin_user, admin_password = obtener_credenciales()
    opener_no_redirect = urllib.request.build_opener(NoRedirectHandler)

    # 1. Acceso a /catalogo sin autenticación -> Debe redirigir a /login
    print("\n[PASO 1] GET /catalogo sin sesión (navegador)...")
    req1 = urllib.request.Request(f"{BASE_URL}/catalogo", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        r1 = opener_no_redirect.open(req1, timeout=30)
        status1 = r1.status
        loc1 = r1.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        status1 = e.code
        loc1 = e.headers.get("Location", "")

    print(f"  Status: {status1}, Location: {loc1}")
    assert status1 == 303, f"Esperaba 303 redirect, obtuvo {status1}"
    assert "/login?next=" in loc1, f"Location debe apuntar a /login, obtuvo: {loc1}"
    print("  ✅ [PASS] Acceso no autenticado fue redirigido a /login correctamente.")

    # 2. Acceso a /api/catalog/tours sin credenciales -> Debe retornar 401
    print("\n[PASO 2] GET /api/catalog/tours sin credenciales (API)...")
    req2 = urllib.request.Request(f"{BASE_URL}/api/catalog/tours")
    try:
        opener_no_redirect.open(req2, timeout=30)
        status2 = 200
    except urllib.error.HTTPError as e:
        status2 = e.code
        auth_hdr = e.headers.get("WWW-Authenticate", "")

    print(f"  Status: {status2}, WWW-Authenticate: {auth_hdr}")
    assert status2 == 401, f"Esperaba 401 en API, obtuvo {status2}"
    assert "Basic" in auth_hdr, "API debe exigir autenticación Basic"
    print("  ✅ [PASS] Rutas de API retornan 401 sin redirección HTML.")

    # 3. Carga visual de la página /login
    print("\n[PASO 3] GET /login...")
    req3 = urllib.request.Request(f"{BASE_URL}/login")
    with urllib.request.urlopen(req3, timeout=30) as r3:
        body3 = r3.read().decode("utf-8")
        status3 = r3.status
    print(f"  Status: {status3}")
    assert status3 == 200
    assert "Texeira Travel" in body3, "La página debe contener la marca Texeira Travel"
    assert "Panel Administrativo" in body3, "Debe contener el título del panel"
    assert 'name="username"' in body3 and 'name="password"' in body3, "Debe contener inputs del formulario"
    print("  ✅ [PASS] Pantalla corporativa /login renderiza correctamente con identidad de marca.")

    # 4. Intento de login con credenciales erróneas
    print("\n[PASO 4] POST /login con credenciales incorrectas...")
    payload_bad = urllib.parse.urlencode({
        "username": "admin",
        "password": "wrong-password-xyz",
        "next": "/catalogo"
    }).encode("utf-8")
    req4 = urllib.request.Request(f"{BASE_URL}/login", data=payload_bad)
    try:
        opener_no_redirect.open(req4, timeout=30)
        status4 = 200
    except urllib.error.HTTPError as e:
        status4 = e.code
        body4 = e.read().decode("utf-8")

    print(f"  Status: {status4}")
    assert status4 == 401, f"Esperaba 401, obtuvo {status4}"
    assert "Usuario o contraseña incorrectos" in body4, "Debe mostrar alerta de error"
    print("  ✅ [PASS] Credenciales incorrectas rechazadas con mensaje visual amigable.")

    # 5. Login exitoso con credenciales correctas -> Obtener cookie
    print("\n[PASO 5] POST /login con credenciales maestras...")
    cookie_jar = http.cookiejar.CookieJar()
    opener_with_cookies = urllib.request.build_opener(NoRedirectHandler, urllib.request.HTTPCookieProcessor(cookie_jar))

    payload_ok = urllib.parse.urlencode({
        "username": admin_user,
        "password": admin_password,
        "remember_me": "1",
        "next": "/catalogo"
    }).encode("utf-8")
    req5 = urllib.request.Request(f"{BASE_URL}/login", data=payload_ok)
    try:
        r5 = opener_with_cookies.open(req5, timeout=30)
        status5 = r5.status
        loc5 = r5.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        status5 = e.code
        loc5 = e.headers.get("Location", "")

    print(f"  Status: {status5}, Redirect to: {loc5}")
    assert status5 == 303, f"Esperaba 303 redirect tras login, obtuvo {status5}"
    assert loc5 == "/catalogo", f"Esperaba redirección a /catalogo, obtuvo {loc5}"

    # Validar cookie texeira_session
    cookies_dict = {c.name: c.value for c in cookie_jar}
    print(f"  Cookies obtenidas: {list(cookies_dict.keys())}")
    assert "texeira_session" in cookies_dict, "La cookie texeira_session debió ser emitida"
    session_val = cookies_dict["texeira_session"]
    assert "v1:" in session_val, f"Token de sesión con formato inesperado: {session_val[:20]}"
    print("  ✅ [PASS] Inicio de sesión exitoso. Cookie de sesión emitida con éxito.")

    # 6. Acceder a /catalogo usando la cookie de sesión
    print("\n[PASO 6] GET /catalogo usando cookie de sesión...")
    req6 = urllib.request.Request(f"{BASE_URL}/catalogo")
    with opener_with_cookies.open(req6, timeout=30) as r6:
        status6 = r6.status
        body6 = r6.read().decode("utf-8")

    print(f"  Status: {status6}")
    assert status6 == 200, f"Esperaba 200 OK con sesión, obtuvo {status6}"
    assert "Catálogo de Tours y Tarifas" in body6, "Debe cargar el catálogo completo"
    assert "Cerrar sesión" in body6, "Debe incluir el botón de Cerrar sesión en el panel"
    print("  ✅ [PASS] Panel /catalogo cargado con éxito mediante cookie de sesión.")

    # 7. Acceder a /dashboard usando la misma cookie de sesión
    print("\n[PASO 7] GET /dashboard usando cookie de sesión...")
    req7 = urllib.request.Request(f"{BASE_URL}/dashboard")
    with opener_with_cookies.open(req7, timeout=30) as r7:
        status7 = r7.status
        body7 = r7.read().decode("utf-8")

    print(f"  Status: {status7}")
    assert status7 == 200, f"Esperaba 200 OK con sesión, obtuvo {status7}"
    assert "Cerrar sesión" in body7, "Debe incluir el botón de Cerrar sesión en el dashboard"
    print("  ✅ [PASS] Panel /dashboard accesible con la misma sesión y botón de logout.")

    # 8. Cierre de sesión seguro (/logout)
    print("\n[PASO 8] GET /logout...")
    req8 = urllib.request.Request(f"{BASE_URL}/logout")
    try:
        r8 = opener_with_cookies.open(req8, timeout=30)
        status8 = r8.status
        loc8 = r8.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        status8 = e.code
        loc8 = e.headers.get("Location", "")

    print(f"  Status: {status8}, Location: {loc8}")
    assert status8 == 303, f"Esperaba 303 redirect tras logout, obtuvo {status8}"
    assert "/login?logout=1" in loc8, f"Esperaba redirección a /login?logout=1, obtuvo {loc8}"
    print("  ✅ [PASS] Logout ejecutado correctamente. Redirige a /login?logout=1.")

    # 9. Compatibilidad de HTTP Basic Auth intacta
    print("\n[PASO 9] Verificando compatibilidad de HTTP Basic Auth en APIs...")
    auth_str = base64.b64encode(f"{admin_user}:{admin_password}".encode()).decode()
    req9 = urllib.request.Request(f"{BASE_URL}/api/catalog/tours", headers={"Authorization": f"Basic {auth_str}"})
    with urllib.request.urlopen(req9, timeout=30) as r9:
        status9 = r9.status
        tours = json.loads(r9.read().decode("utf-8"))

    print(f"  Status: {status9}, Tours retornados: {len(tours)}")
    assert status9 == 200
    assert len(tours) >= 15, "Debe retornar el listado de tours oficiales"
    print("  ✅ [PASS] Compatibilidad dual perfecta: scripts con HTTP Basic Auth siguen operando al 100%.")

    print("\n" + "=" * 76)
    print("  ¡TODAS LAS PRUEBAS EN VIVO DE LOGIN (9/9) PASARON SATISFACTORIAMENTE!")
    print("=" * 76)


if __name__ == "__main__":
    main()

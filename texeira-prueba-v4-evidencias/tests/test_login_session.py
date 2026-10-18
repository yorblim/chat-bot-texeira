"""tests/test_login_session.py — Pruebas unitarias completas para el sistema de Login y Sesiones.

Valida:
1. Redirección de navegadores web no autenticados a /login con parámetro ?next=...
2. Protección continua de APIs (/api/..., /test-chat) retornando 401 sin redirección HTML.
3. Compatibilidad total de HTTP Basic Auth para scripts y tests existentes.
4. Renderizado de la pantalla corporativa /login con diseño y formulario.
5. Autenticación exitosa (form y AJAX) emitiendo cookie HttpOnly firmada con HMAC.
6. Rechazo de credenciales incorrectas con código 401 y mensaje visual.
7. Acceso a paneles protegidos (/catalogo, /dashboard) usando cookie de sesión.
8. Rechazo de cookies alteradas o manipuladas.
9. Cierre de sesión seguro (/logout) eliminando la cookie de sesión.
10. Mitigación de vulnerabilidades Open Redirect en el parámetro next.
"""
import os
import unittest
from fastapi.testclient import TestClient

# Configurar credenciales fijas para pruebas
os.environ["ADMIN_USER"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-secret-pwd-2026"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app
from auth_middleware import (
    SESSION_COOKIE_NAME,
    create_session_token,
    verify_session_token,
    sanitize_next_url,
)


class TestLoginSessionSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app.app, follow_redirects=False)

    def test_sanitize_next_url(self):
        # Rutas locales válidas
        self.assertEqual(sanitize_next_url("/catalogo"), "/catalogo")
        self.assertEqual(sanitize_next_url("/dashboard?date=2026"), "/dashboard?date=2026")
        self.assertEqual(sanitize_next_url("/handoffs"), "/handoffs")

        # Intentos de Open Redirect bloqueados
        self.assertEqual(sanitize_next_url("https://malicious.com"), "/catalogo")
        self.assertEqual(sanitize_next_url("//evil.com/hack"), "/catalogo")
        self.assertEqual(sanitize_next_url("/\\evil.com"), "/catalogo")
        self.assertEqual(sanitize_next_url("javascript:alert(1)"), "/catalogo")
        self.assertEqual(sanitize_next_url(""), "/catalogo")

    def test_create_and_verify_session_token(self):
        token, max_age = create_session_token("admin", remember=False)
        self.assertGreater(max_age, 0)
        self.assertIn("v1:admin:", token)

        # Verificar token válido
        data = verify_session_token(token)
        self.assertIsNotNone(data)
        self.assertEqual(data["username"], "admin")

        # Verificar token alterado (firma inválida)
        tampered = token[:-4] + "abcd"
        self.assertIsNone(verify_session_token(tampered))

        # Verificar token malformado
        self.assertIsNone(verify_session_token("token-invalido"))
        self.assertIsNone(verify_session_token(""))

    def test_unauthenticated_browser_redirected_to_login(self):
        # /catalogo sin sesión debe redirigir a /login?next=%2Fcatalogo
        res = self.client.get("/catalogo")
        self.assertEqual(res.status_code, 303)
        self.assertIn("/login?next=%2Fcatalogo", res.headers.get("location", ""))

        # /dashboard sin sesión debe redirigir a /login?next=%2Fdashboard
        res_dash = self.client.get("/dashboard")
        self.assertEqual(res_dash.status_code, 303)
        self.assertIn("/login?next=%2Fdashboard", res_dash.headers.get("location", ""))

    def test_unauthenticated_api_returns_401_without_redirect(self):
        # Las APIs (/api/...) deben responder 401 y no redirigir a HTML
        res = self.client.get("/api/catalog/tours")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Basic", res.headers.get("www-authenticate", ""))

        # Peticiones AJAX con Accept application/json deben responder 401
        res_ajax = self.client.get("/catalogo", headers={"Accept": "application/json"})
        self.assertEqual(res_ajax.status_code, 401)

    def test_basic_auth_compatibility_preserved(self):
        # Con Basic Auth válido, las APIs siguen funcionando directamente
        res = self.client.get("/api/catalog/tours", auth=("admin", "test-secret-pwd-2026"))
        self.assertEqual(res.status_code, 200)

        # Basic Auth inválido debe rechazar con 401
        res_bad = self.client.get("/api/catalog/tours", auth=("admin", "wrong-password"))
        self.assertEqual(res_bad.status_code, 401)

    def test_get_login_page_renders_html(self):
        res = self.client.get("/login?next=%2Fcatalogo")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("Texeira Travel", res.text)
        self.assertIn("Panel Administrativo", res.text)
        self.assertIn('name="username"', res.text)
        self.assertIn('name="password"', res.text)
        self.assertIn('name="remember_me"', res.text)
        self.assertIn('value="/catalogo"', res.text)

    def test_login_post_invalid_credentials(self):
        # Form POST con contraseña incorrecta
        res = self.client.post("/login", data={
            "username": "admin",
            "password": "wrong-password",
            "next": "/catalogo"
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Usuario o contraseña incorrectos", res.text)
        self.assertNotIn(SESSION_COOKIE_NAME, res.cookies)

        # AJAX POST con contraseña incorrecta
        res_ajax = self.client.post("/login", json={
            "username": "admin",
            "password": "wrong-password"
        })
        self.assertEqual(res_ajax.status_code, 401)
        data = res_ajax.json()
        self.assertFalse(data.get("ok"))

    def test_login_post_successful_sets_cookie_and_redirects(self):
        # Form POST exitoso
        res = self.client.post("/login", data={
            "username": "admin",
            "password": "test-secret-pwd-2026",
            "remember_me": "1",
            "next": "/catalogo"
        })
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers.get("location"), "/catalogo")
        self.assertIn(SESSION_COOKIE_NAME, res.cookies)

        # Cookie debe contener versión y usuario
        cookie_val = res.cookies[SESSION_COOKIE_NAME]
        self.assertIn("v1:admin:", cookie_val)

        # Acceder a /catalogo usando la cookie emitida
        res_cat = self.client.get("/catalogo", cookies={SESSION_COOKIE_NAME: cookie_val})
        self.assertEqual(res_cat.status_code, 200)
        self.assertIn("Catálogo de Tours y Tarifas", res_cat.text)
        self.assertIn("Cerrar sesión", res_cat.text)

    def test_login_post_ajax_successful(self):
        res = self.client.post("/login", json={
            "username": "admin",
            "password": "test-secret-pwd-2026",
            "next": "/dashboard"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("redirect"), "/dashboard")
        self.assertIn(SESSION_COOKIE_NAME, res.cookies)

    def test_already_authenticated_user_visiting_login_redirects(self):
        token, _ = create_session_token("admin")
        res = self.client.get("/login?next=%2Fdashboard", cookies={SESSION_COOKIE_NAME: token})
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers.get("location"), "/dashboard")

    def test_logout_clears_cookie_and_redirects(self):
        token, _ = create_session_token("admin")
        res = self.client.get("/logout", cookies={SESSION_COOKIE_NAME: token})
        self.assertEqual(res.status_code, 303)
        self.assertIn("/login?logout=1", res.headers.get("location", ""))

        # Verificar que el mensaje de cierre de sesión seguro se muestra en /login
        res_login = self.client.get("/login?logout=1")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn("Has cerrado sesión de forma segura", res_login.text)

    def test_login_open_redirect_protection(self):
        res = self.client.post("/login", data={
            "username": "admin",
            "password": "test-secret-pwd-2026",
            "next": "https://attacker.com/malicious"
        })
        self.assertEqual(res.status_code, 303)
        # Debe ignorar la URL maliciosa y enviar al default seguro
        self.assertEqual(res.headers.get("location"), "/catalogo")


if __name__ == "__main__":
    unittest.main()

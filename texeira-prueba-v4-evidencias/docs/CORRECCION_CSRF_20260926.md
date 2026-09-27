# Corrección del token CSRF del catálogo — 2026-09-26

## Evidencia y causa

El usuario reportó `Token CSRF inválido o faltante` en el catálogo desplegado.
El código local generaba un token aleatorio por llamada a `install(app)`.
La página conservaba ese valor en `CSRF_TOKEN`. Un reinicio o una segunda
instancia invalida el valor de la página anterior. No se consultaron logs de
Cloud Run para atribuir el evento concreto a una instancia determinada.

## Cambio local

- `catalog_support.py`: token HMAC-SHA256 con dominio exclusivo del catálogo,
  derivado de ADMIN_PASSWORD. No expone la contraseña. Es consistente entre
  procesos con la misma configuración y cambia cuando rota la contraseña.
- Sin contraseña, el modo local conserva token aleatorio; la autenticación
  existente continúa rechazando acceso cloud sin credenciales.
- HTML y endpoint de token autenticados y con Cache-Control: no-store.
- Se conserva validación CSRF en las mutaciones; no se desactiva protección.

## Verificación

`python tests/test_catalog_csrf_instances.py`: **5/5 PASS**.
Prueba HTTP entre dos aplicaciones independientes, tokens ausentes/incorrectos,
autenticación obligatoria, rotación de contraseña y HTML sin caché.
Se usa un servicio de catálogo simulado: cero DB real, cero Groq, cero WhatsApp.
Este resultado no representa una ejecución de toda la suite del proyecto.

## Estado para continuar

Cambios locales, todavía sin commit/push/despliegue. La rama existente es
`feature/tarifas-flexibles-tours`. Antes de esta corrección ya había cambios
sin commit en catalog_service.py, catalog_support.py (tarifas), db_adapter.py
y verified_routes.py. Se conservaron; no se certifican mediante esta prueba.

Antes de desplegar, separar/versionar el arreglo o validar también esos cambios,
ejecutar las regresiones correspondientes e integrar por el flujo Git del proyecto.
No ejecutar actualizar_nube.bat con cambios ajenos sin validar.
Después de actualizar la nube, recargar el catálogo para obtener el token nuevo.
Una recarga antes del despliegue puede resolver temporalmente una página antigua,
pero no corrige la alternancia de instancias del servidor anterior.

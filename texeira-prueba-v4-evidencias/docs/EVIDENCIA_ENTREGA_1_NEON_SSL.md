# Informe de Evidencia: Entrega 1 — Conexión Segura con Neon PostgreSQL y Validación SSL

**Fecha:** 19/09/2026  
**Rama:** `feature/conexion-segura-neon`  
**Estado:** Listo para revisión de Codex (Sin merge a `main`, sin despliegue).

---

## 1. Alcance y Problema Técnico Resuelto

Las cadenas de conexión de proveedores como Neon (`postgresql://...`) suelen incluir parámetros en la query string como:
`?sslmode=require&channel_binding=disable`

El driver `pg8000` (DB-API puro de Python) no acepta `sslmode` ni `channel_binding` directamente en los argumentos de `connect()`. Pasarlos sin filtrar causaba:
`TypeError: connect() got an unexpected keyword argument 'sslmode'`

### Solución Implementada:
En lugar de simplemente descartar los parámetros para silenciar el error, se implementó una función de parsing y validación rigurosa: `prepare_postgres_engine_args()` en `db_adapter.py`:

1. **Verificación Estricta de Certificados y Nombre de Host (SSL):**
   - Cuando se requiere SSL (`require` o `verify-full`), se construye un `ssl_context = ssl.create_default_context()` con:
     - `check_hostname = True`
     - `verify_mode = ssl.CERT_REQUIRED`
   - Cuando se especifica `sslmode=verify-ca`:
     - Se verifica la autoridad certificadora (`verify_mode = ssl.CERT_REQUIRED`) con `check_hostname = False`.
   - Cuando se especifica `sslmode=disable`:
     - No se inyecta contexto SSL.
   - Cualquier valor desconocido de `sslmode` lanza `ValueError` explícito.
2. **Tratamiento de `channel_binding`:**
   - Si se solicita `channel_binding=require`:
     - Dado que `pg8000` no implementa SCRAM channel binding (`SCRAM-SHA-256-PLUS`), la conexión se **rechaza explícitamente**:
       `ValueError("channel_binding=require no es soportado por el controlador pg8000. Utilice channel_binding=prefer o channel_binding=disable.")`
     - Nunca se descarta silenciosamente.
   - Valores `prefer` o `disable` se procesan con autenticación SCRAM-SHA-256 estándar.
3. **Protección y No Exposición de Credenciales:**
   - Cualquier parámetro de conexión no soportado es rechazado sin exponer la URL con contraseñas en el mensaje de error:
     `ValueError("Parámetro de conexión no soportado: '<param>'")`
   - `get_database_url(hide_password=True)` enmascara las credenciales (`***`) para fines de logging y reportes.
4. **Mapeo de Parámetros Válidos:**
   - `connect_timeout` se mapea a `connect_args['timeout']`.
   - `application_name` se mapea a `connect_args['application_name']`.
5. **Aislamiento y Retrocompatibilidad SQLite:**
   - Si `DATABASE_URL` no está definida o está vacía, el sistema continúa operando al 100% sobre SQLite local.

---

## 2. Pruebas Unitarias Implementadas

Se creó la suite [tests/test_neon_ssl_adapter.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_neon_ssl_adapter.py):

| Prueba | Descripción | Resultado |
| :--- | :--- | :---: |
| `test_neon_url_ssl_require` | Verifica `check_hostname=True`, `verify_mode=CERT_REQUIRED`, query limpia | **PASS** |
| `test_neon_url_ssl_verify_full` | Verifica validación completa de host y CA | **PASS** |
| `test_neon_url_ssl_verify_ca` | Verifica validación de CA con `check_hostname=False` | **PASS** |
| `test_neon_url_ssl_disable` | Verifica conexión sin SSL | **PASS** |
| `test_channel_binding_require_explicitly_rejected` | Rechazo explícito de `channel_binding=require` sin filtrar credenciales | **PASS** |
| `test_unsupported_parameters_rejected` | Rechazo de parámetros desconocidos sin exponer contraseñas | **PASS** |
| `test_supported_parameters_mapping` | Mapeo de `application_name` y `connect_timeout` | **PASS** |
| `test_local_sqlite_fallback_intact` | Comprobación de que SQLite local opera intacto sin `DATABASE_URL` | **PASS** |

---

## 3. Verificación de Regresión (Suite Completa)

Se ejecutaron todas las suites del proyecto localmente:
- `tests/test_neon_ssl_adapter.py`: **8/8 PASS**
- `tests/test_db_persistence.py`: **PASS**
- `tests/test_persistence_regressions.py`: **6/6 PASS**
- `tests/test_persistence_concurrency.py`: **PASS**
- `tests/test_webhook_recovery.py`: **6/6 PASS**
- `tests/test_conversational.py`: **29/29 PASS**
- `tests/test_audit_20260912.py`: **21/21 PASS**
- `tests/test_dedup.py`: **23/23 PASS**
- `tests/test_handoff.py`: **PASS**
- `tests/test_operational_metrics.py`: **PASS**
- `tests/test_public_entry.py`: **PASS**

---

## 4. Compromiso de GitOps

- **Rama:** `feature/conexion-segura-neon` (exclusivamente en `texeira-prueba-v4-evidencias/`).
- **Estado de `main`:** Intacto.
- **Despliegue:** No ejecutado.
- **Siguiente paso:** Revisión cruzada de Codex antes de cualquier merge.

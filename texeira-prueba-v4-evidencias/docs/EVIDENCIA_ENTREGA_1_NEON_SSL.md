# Informe de Evidencia: Entrega 1 — Conexión Segura con Neon PostgreSQL y Validación SSL (Revisión Completa)

**Fecha:** 19/09/2026  
**Rama:** `feature/conexion-segura-neon`  
**Estado:** Actualizado y listo para revisión de Codex (Sin merge a `main`, sin despliegue).

---

## 1. Alcance y Respuestas a las 5 Observaciones de Codex

En esta iteración se abordaron rigurosamente las 5 observaciones técnicas acordadas:

### 1.1. Comportamiento Correcto de `sslmode=disable`, `prefer` y `allow`
- **`sslmode=disable`:** En `pg8000`, la omisión de `ssl_context` disparaba por defecto un intento SSL con `CERT_NONE`. Para forzar que `pg8000` **nunca** intente SSL ni envíe el paquete `SSLRequest`, se configura explícitamente `connect_args['ssl_context'] = False`. Si el servidor exige SSL, la conexión falla limpiamente sin degradación forzada.
- **`sslmode=prefer`:** Intenta primero la conexión cifrada con TLS (`ssl_context = ctx`). Si el servidor rechaza SSL (respuesta `'N'` de PostgreSQL) o no soporta cifrado, `secure_pg8000_connect` realiza el fallback automático y seguro a conexión sin SSL (`ssl_context = False`).
- **`sslmode=allow`:** Intenta primero una conexión sin SSL (`ssl_context = False`). Si el servidor rechaza la conexión en texto plano (exige SSL), realiza el fallback automático a conexión cifrada con TLS (`ssl_context = ctx`).
- **`sslmode=require` / `verify-full`:** Exige TLS estricto con validación de CA (`verify_mode = CERT_REQUIRED`) y validación de nombre de servidor (`check_hostname = True`).
- **`sslmode=verify-ca`:** Exige TLS estricto con validación de CA (`verify_mode = CERT_REQUIRED`) sin verificar nombre de host (`check_hostname = False`).

### 1.2. Soporte Real y Observancia de `channel_binding` (`disable`, `prefer`, `require`)
- Se verificó la implementación interna del controlador instalado (`pg8000` 1.31.5 con biblioteca `scramp` 1.4.17):
  - `pg8000.core._make_socket` genera `channel_binding` usando `scramp.make_channel_binding("tls-server-end-point", sock)` cuando TLS está activo.
  - Se implementó la clase `SecureConnection(pg8000.dbapi.Connection)` para gobernar este comportamiento:
    - **`channel_binding=disable`:** Anula explícitamente `self.channel_binding = None` en el momento de la autenticación SASL, forzando a `scramp` a seleccionar `SCRAM-SHA-256` y cabecera `n,,` sin binding.
    - **`channel_binding=prefer`:** Comportamiento estándar de `pg8000`; utiliza `tls-server-end-point` con `SCRAM-SHA-256-PLUS` si el servidor lo ofrece y la conexión es TLS; si no, utiliza `SCRAM-SHA-256`.
    - **`channel_binding=require`:** Enforzamiento estricto:
      - Si la conexión no es TLS (`self.channel_binding is None`), o si el servidor no ofrece mecanismos con binding (`-PLUS`), la conexión se rechaza tajantemente con `InterfaceError`.
      - **Soporte de protocolo PostgreSQL SASL (Mensajes 11 y 12):** Permite el procesamiento regular de `AuthenticationSASLContinue` (código 11) y `AuthenticationSASLFinal` (código 12), rechazando únicamente métodos no-SCRAM.
      - **Rechazo estricto de `AuthenticationOk` prematuro/sin SCRAM-PLUS:** Antes de aceptar `AuthenticationOk` (código 0), se valida rigurosamente que se haya completado la autenticación `SCRAM-SHA-256-PLUS`. Si el servidor envía código 0 sin SASL o con SASL incompleto, la conexión se rechaza inmediatamente con `InterfaceError`.
      - **Flujo completo SCRAM-SHA-256-PLUS:** Validado exitosamente en un ciclo de 4 pasos (10 -> InitialResponse, 11 -> Response, 12 -> Final, 0 -> Ok).
      - **Cero degradación en `prefer` y `allow`:** En `prefer`, si falla SSL con `channel_binding=require`, no se realiza fallback a texto plano; en `allow`, el primer intento sin SSL no fuerza `disable`.

### 1.3. Sanitización de Información Sensible y Cadenas de Excepciones (`from None`)
- Todas las excepciones de validación y conexión se emiten con `raise ... from None`, activando `__suppress_context__ = True` y anulando `__cause__ = None`. Esto garantiza que los tracebacks de Python jamás impriman la URL cruda ni contraseñas.
- Se implementó la función auxiliar `sanitize_error_message(msg, secret)` para enmascarar URLs `postgresql://usuario:***@host`, parámetros `password=***` o tokens secretos en cualquier formato (`password=...`, `password: ...`, `'password': '...'`).
- **Sanitización exhaustiva en reintentos:** Tanto el fallback de `prefer` como el segundo intento de `allow` se encuentran encapsulados en bloques `try...except` con sanitización de contraseñas y supresión de contexto.
- En caso de parámetros desconocidos en la query, únicamente se expone el nombre de la clave (ej. `'invalid_key'`), jamás su valor (que podría ser una credencial o token).

### 1.4. Pruebas Reales de Negociación TLS y Rechazo
- Se construyó un servidor de pruebas local con sockets y TLS real en `tests/test_neon_ssl_adapter.py`:
  - **Rechazo por discrepancia de hostname:** El servidor presenta un certificado emitido para `wrong.neon.tech`; el cliente conecta hacia `localhost` con `check_hostname=True`. La conexión es rechazada por `SSLCertVerificationError` sin filtrar secretos.
  - **Rechazo por CA no confiable:** El servidor presenta un certificado firmado por una CA local no reconocida por el almacén del sistema; la conexión es rechazada por `SSLCertVerificationError`.
  - **Rechazo estricto ante servidor que rehúsa SSL:** El servidor envía `'N'` ante `SSLRequest`. Con `sslmode=require`, el cliente aborta inmediatamente con `InterfaceError("Server refuses SSL")` y nunca degrada a texto plano.
  - **Fallback comprobado en `sslmode=prefer`:** El servidor envía `'N'`; el cliente captura el rechazo e intenta el segundo flujo sin SSL.
  - **Rechazo de `channel_binding=require` sin TLS:** Falla de inmediato si no hay capa TLS o si falta el mecanismo `-PLUS`.

### 1.5. Regresiones Locales y Retrocompatibilidad SQLite
- Si `DATABASE_URL` no está definida, SQLite sigue funcionando de manera idéntica y sin alteraciones para pruebas locales.

---

## 2. Matriz de Pruebas Unitarias e Integración (`tests/test_neon_ssl_adapter.py`)

| # | Prueba | Descripción | Resultado |
| :- | :--- | :--- | :---: |
| 1 | `test_neon_url_ssl_require` | Verifica `check_hostname=True`, `verify_mode=CERT_REQUIRED`, query limpia | **PASS** |
| 2 | `test_neon_url_ssl_verify_full` | Verifica validación completa de host y CA | **PASS** |
| 3 | `test_neon_url_ssl_verify_ca` | Verifica validación de CA con `check_hostname=False` | **PASS** |
| 4 | `test_neon_url_ssl_disable` | Verifica `ssl_context=False` explícito | **PASS** |
| 5 | `test_neon_url_ssl_prefer` | Verifica configuración con intento SSL y fallback | **PASS** |
| 6 | `test_neon_url_ssl_allow` | Verifica intento inicial sin SSL y fallback | **PASS** |
| 7 | `test_channel_binding_options_supported` | Valida opciones `disable`, `prefer`, `require` y rechazo de inválidos | **PASS** |
| 8 | `test_channel_binding_require_rejected_on_non_ssl` | Rechazo inmediato de `require` cuando no hay TLS | **PASS** |
| 9 | `test_channel_binding_require_rejected_when_server_lacks_plus` | Rechazo de `require` si servidor solo ofrece `SCRAM-SHA-256` | **PASS** |
| 10 | `test_channel_binding_disable_clears_binding` | Anulación efectiva de `channel_binding` en `disable` | **PASS** |
| 11 | `test_channel_binding_require_allows_sasl_continue_and_final` | Permite mensajes SASL 11 y 12 en protocolo con `channel_binding=require` | **PASS** |
| 12 | `test_channel_binding_require_rejects_auth_ok_without_scram_plus` | Rechaza `AuthenticationOk` si no se completó SCRAM-SHA-256-PLUS | **PASS** |
| 13 | `test_scram_sha_256_plus_full_authentication_flow` | Autenticación completa y exitosa SCRAM-SHA-256-PLUS (4 pasos SASL) | **PASS** |
| 14 | `test_channel_binding_require_no_downgrade_in_prefer_and_allow` | No degradación de `channel_binding` a `disable` en `prefer` ni `allow` | **PASS** |
| 15 | `test_exception_sanitization_no_leak_in_chain` | Verifica `__suppress_context__` y ausencia de secretos en tracebacks | **PASS** |
| 16 | `test_sanitize_error_message_helper` | Enmascaramiento de contraseñas y URLs en cadenas de error | **PASS** |
| 17 | `test_exception_sanitization_in_second_attempts` | Sanitización rigurosa de excepciones originadas en segundos intentos | **PASS** |
| 18 | `test_tls_hostname_mismatch_rejection` | Rechazo por nombre de servidor incorrecto (`SSLCertVerificationError`) | **PASS** |
| 19 | `test_tls_untrusted_certificate_rejection` | Rechazo por CA desconocida (`SSLCertVerificationError`) | **PASS** |
| 20 | `test_tls_server_refuses_ssl_strict_rejection` | Cero degradación a texto plano cuando servidor rehúsa SSL | **PASS** |
| 21 | `test_tls_server_refuses_ssl_prefer_fallback` | Fallback verificado en dos intentos (SSL -> texto plano) | **PASS** |
| 22 | `test_local_sqlite_fallback_intact` | Comprobación de que SQLite local opera intacto sin `DATABASE_URL` | **PASS** |

**Resultado total de la suite:** `22 PASS / 0 FAIL / 22 TOTAL` (100% de éxito).

---

## 3. Verificación de Regresión Completa

Se ejecutaron todas las suites de pruebas del proyecto:
- `tests/test_neon_ssl_adapter.py`: **22/22 PASS**
- `tests/test_db_persistence.py`: **PASS** (utilidades, database.py SQLite, handoff SQLite, PostgresConnectionWrapper)
- `tests/test_persistence_regressions.py`: **6/6 PASS** (transacciones, bloqueos, lease, idempotencia)
- `tests/test_persistence_concurrency.py`: **6/6 PASS** (hilos concurrentes SQLite y PostgreSQL wrapper)
- `tests/test_webhook_recovery.py`: **6/6 PASS** (reintentos, deduplicación, leases y fallbacks)
- `tests/test_conversational.py`: **29/29 PASS** (sin LLM en saludos/ayuda, sin teléfonos ni fotos no solicitadas)
- `tests/test_audit_20260912.py`: **21/21 PASS** (integridad, rutas de evidencia, métricas)
- `tests/test_operational_metrics.py`: **PASS**

---

## 4. Validación en Vivo con Neon PostgreSQL (Cero Credenciales)

Se ejecutó la prueba de conectividad y funcionalidad real contra el cluster de Neon PostgreSQL recuperando el secreto `DATABASE_URL` v1 desde Google Cloud Secret Manager (`texeira-whatsapp-bot`) exclusivamente en memoria:

1. **Negociación TLS y Cifrado en Vivo:**
   - Capa TLS del socket de cliente: **Activa (`is_ssl = True`)**.
   - Protocolo TLS negociado: **`TLSv1.3`**.
   - Suite de cifrado: **`TLS_AES_256_GCM_SHA384`**.
   - Channel Binding: **`tls-server-end-point` (longitud = 32 bytes)**.
   - Parámetros efectivos: `sslmode=require`, `channel_binding=require`.

2. **Identificación del Motor Remoto:**
   - Servidor remoto: **`PostgreSQL 18.6 on aarch64-unknown-linux-gnu`**.
   - Driver utilizado: **`pg8000` + `SQLAlchemy` con `SecureConnection`**.

3. **Prueba de Escritura y Lectura Aislada (Cero Impacto):**
   - Se creó una tabla temporal de sesión (`CREATE TEMP TABLE _probe_neon (id INT PRIMARY KEY, token TEXT)`).
   - Inserción y consulta de token de sondeo: **Resultado = `neon_probe_ok` (PASS)**.
   - Eliminación de tabla temporal en la misma sesión (`DROP TABLE _probe_neon`).
   - Impacto en datos existentes de producción: **Nulo**.

---

## 5. Compromiso y Protocolo GitOps

- **Rama de trabajo:** `feature/conexion-segura-neon` (exclusivamente en `texeira-prueba-v4-evidencias/`).
- **Estado de `main`:** Intacto (cero merge anticipado).
- **Despliegue a Cloud Run:** No ejecutado.
- **Memoria persistente (Entrega 2):** No iniciada (se posterga estrictamente hasta que se apruebe e integre la Entrega 1).
- **Próximo paso:** Apertura de Pull Request hacia `main`.

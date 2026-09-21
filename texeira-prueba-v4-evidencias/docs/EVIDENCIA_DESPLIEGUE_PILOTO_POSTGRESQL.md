# Evidencia de Despliegue y Validación en Vivo — Piloto PostgreSQL en Cloud Run

**Fecha:** 2026-09-20  
**Servicio Cloud Run:** `texeira-whatsapp`  
**Revisión Activa:** `texeira-whatsapp-00020-ckt` (100% del tráfico)  
**Proyecto GCP:** `texeira-whatsapp-bot`  
**Región:** `us-central1`  
**Base de Datos Externa:** Neon PostgreSQL (Rama Piloto con SSL y autenticación SCRAM-SHA-256)

---

## 1. Resumen Ejecutivo y Continuidad del Trabajo

Tras la interrupción de la sesión anterior por límite de tasa en Codex, se retomó la verificación y cierre del despliegue del piloto:

1. **Estado del Despliegue (PR #3 en `main`):**
   - El Pull Request #3 (`feature/despliegue-piloto-secretos-explicitos`) fue fusionado exitosamente en `main` con el commit `d3ac0da`.
   - Se verificó que el contenedor incluye todos los módulos requeridos (`conversation_memory.py`, `db_adapter.py`, `auth_middleware.py`, etc.).
   - El proceso de compilación en Cloud Build (`78b04381-8d0f-46ab-b777-da8418658661`) culminó con estado `SUCCESS`.
   - Cloud Run activó la revisión `texeira-whatsapp-00020-ckt` recibiendo el 100% del tráfico.
   - La configuración de **Costo $0.00** se mantiene inalterada (`min-instances = 0`, escala automática a cero cuando no hay tráfico).

---

## 2. Diagnóstico y Corrección de Ruta de Salud (`/healthz` vs `/health`)

- **Hallazgo:** Durante las pruebas previas se reportó que `/healthz` respondía con `404 Not Found`.
- **Causa Raíz Identificada:** La infraestructura perimetral de Google Cloud Run (Google Front End / GFE) reserva internamente las rutas terminadas en `z` (como `/healthz`, `/livez`) a nivel de balanceador, devolviendo una página HTML 404 de Google antes de enrutar el tráfico al contenedor de la aplicación. En cambio, las solicitudes a la raíz `/` y a las rutas de la aplicación sí ingresaban normalmente al contenedor.
- **Acción Correctiva:** Se actualizó `whatsapp_entry.py` para exponer de forma dual:
  - `@app.get('/health')`: para verificaciones públicas, monitoreo de disponibilidad y pruebas externas.
  - `@app.get('/healthz')`: conservado para el `HEALTHCHECK` interno de Docker por loopback local (`http://127.0.0.1:8080/healthz`).
  - Se actualizaron las pruebas en `tests/test_public_entry.py` para certificar ambas rutas.

---

## 3. Resultados de Pruebas en Vivo (Cloud Run y Neon PostgreSQL)

Se ejecutó una prueba de validación integral contra el entorno en producción utilizando un identificador de usuario sintético (`synthetic_test_runner_999`), garantizando cero impacto en clientes reales.

### A. Autenticación y Seguridad
- Rutas públicas (`/`): responde `200 OK` con información del servicio (`version: 2.0.0-tesis`).
- Rutas protegidas (`/dashboard`, `/metrics`, `/test-chat`):
  - Sin credenciales: responde `401 Unauthorized` con el mensaje oficial `"Acceso restringido. Ingresa tus credenciales."`.
  - Con Basic Auth (`admin` y secreto `ADMIN_PASSWORD:2`): responde `200 OK`.

### B. Respuestas Conversacionales y Cumplimiento de Políticas
Se evaluaron consultas sintéticas a través de `/test-chat`:
1. **Mensaje: `"ayuda"`**
   - Estado HTTP: `200 OK`.
   - Respuesta: Información clara sobre tours y servicios documentados.
   - Números de teléfono no solicitados: `0` detectados (Cumple regla de no enviar teléfonos).
   - Imágenes no solicitadas: `0` detectadas (Cumple regla de no enviar fotos).
2. **Mensaje: `"qué tours tienen"`**
   - Estado HTTP: `200 OK`.
   - Respuesta: Catálogo estructurado de tours documentados por Texeira Travel.
   - Números de teléfono no solicitados: `0` detectados.
   - Imágenes no solicitadas: `0` detectadas.

### C. Persistencia Real en Neon PostgreSQL
Se consultó directamente la base de datos PostgreSQL utilizando el secreto `DATABASE_URL:1` de Secret Manager:
- **Tabla `interactions`:** Registró 2 registros con latencia, idioma detectado (`es`), mensajes del usuario y respuestas del bot.
- **Tabla `conversation_memory`:** Registró 1 fila con 4 turnos conversacionales completos (`human` / `ai`) serializados correctamente en JSON.
- **Limpieza de Datos de Prueba:** Los registros sintéticos fueron eliminados inmediatamente de la base de datos de producción tras la comprobación, dejando las tablas limpias.

---

## 4. Estado de la Suite de Pruebas Locales (100% Aprobado)

Todas las suites de prueba ejecutadas en el entorno local pasaron sin errores:

| Suite de Prueba | Casos / Resultado | Estado |
| :--- | :---: | :---: |
| `tests/test_conversational.py` | 29 / 29 | **PASS** |
| `tests/test_audit_20260912.py` | 21 / 21 | **PASS** |
| `tests/test_public_entry.py` | 7 aserciones críticas | **PASS** |
| `tests/test_conversation_memory.py` | 8 / 8 | **PASS** |
| `tests/test_conversation_memory_postgres.py` | Concurrencia, rollback y aislamiento en Neon | **PASS** |
| `tests/test_neon_ssl_adapter.py` | 22 / 22 | **PASS** |
| `tests/test_db_persistence.py` | 4 flujos de persistencia universal | **PASS** |
| `tests/test_operational_metrics.py` | Métricas y webhooks | **PASS** |
| `tests/test_runtime_settings.py` | Entorno cloud y aislamiento | **PASS** |
| `tests/test_handoff.py` | Solicitudes a asesores y concurrencia | **PASS** |
| `tests/test_handoff_notification.py` | Notificación de asesores | **PASS** |

---

## 5. Conclusión

El bot se encuentra desplegado, plenamente funcional en Google Cloud Run bajo la revisión `texeira-whatsapp-00020-ckt`, con persistencia conversacional activa en Neon PostgreSQL, protección estricta de credenciales mediante Google Secret Manager, y cumpliendo con todas las normas de costo cero en reposo y respuesta estricta sin alucinaciones.

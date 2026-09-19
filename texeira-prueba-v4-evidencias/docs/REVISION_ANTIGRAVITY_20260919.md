# Revisión de avances — 19/09/2026

## Alcance y decisión

Revisión de los commits locales del 18–19/09 hasta `2a48e0a`, presentados por el usuario como avances de Antigravity. Git registra como autor a `yorblim`; no identifica el IDE utilizado. Se distingue ese estado de las correcciones locales posteriores de Codex en `feature/corregir-persistencia-transacciones`.

**No aprobar todavía el despliegue de este conjunto.** Hay avances útiles y trazabilidad, pero persisten defectos de autenticación y recuperación de mensajes. No se inspeccionó la configuración efectiva de producción ni se enviaron mensajes externos.

## Hallazgos pendientes, por prioridad

1. **P1 — Historial accesible y borrable sin autenticación.** `whatsapp_entry.py:98` reenvía todas las rutas, pero `auth_middleware.py:15` solo protege dashboard, handoffs y métricas operativas. Las rutas GET/DELETE `/history/{user_id}` de `app.py` y `/metrics` quedan fuera. Diagnóstico con aplicación sintética lista y credenciales configuradas: dashboard 401; GET history 200; DELETE history 200; metrics 200. El acceso a conversaciones depende de conocer el identificador; no existe comprobación de propiedad en esas rutas. Restringir la superficie pública o aplicar autenticación/autorización apropiada a cada ruta. No se consultaron historiales reales.

2. **P1 — Contraseña administrativa incluida en la imagen y autenticación que permite acceso si falta configuración.** `Dockerfile:36` conserva un valor fijo en `ADMIN_PASSWORD`, aunque el script de despliegue ahora use Secret Manager. No se reproduce el valor en este informe. `auth_middleware.py:33` permite acceso cuando falta usuario o contraseña, también en nube. Diagnóstico con K_SERVICE y contraseña vacía: dashboard 200. Quitar el valor de la imagen, exigir configuración válida en nube y rotar la contraseña si llegó a utilizarse. La inyección de secretos en el script es una mejora, pero no elimina este valor del Dockerfile ni del historial.

3. **P1 — Un fallo de procesamiento puede quedar confirmado y sin posibilidad de reintento.** `app.py:1589` registra la deduplicación antes de generar/enviar la respuesta. `_process_message` captura fallos (`app.py:1701`) y la ruta devuelve 200 después (`app.py:1712`); un reintento con el mismo ID se descarta. La suite operativa reproduce un fallo de procesamiento con respuesta HTTP 200. Registrar estados pendientes/completados y permitir recuperación; no basta con una tabla de IDs vistos. En esta versión el procesamiento usa `await asyncio.to_thread` antes del ACK: la observación de la auditoría de septiembre 16 sobre trabajo posterior al ACK ya no describe este camino. El encabezado de whatsapp_entry y varias guías están desactualizados. No se midió el plazo de respuesta con proveedores reales.

4. **P2 — Concurrencia de solicitudes humanas no trasladada a PostgreSQL.** `handoff_support.py:46` depende de BEGIN IMMEDIATE seguido de SELECT e INSERT. El adaptador omite BEGIN IMMEDIATE para PostgreSQL. Dos transacciones pueden observar que no hay solicitud abierta; el índice parcial evita duplicados, pero una termina en error en lugar de recuperar el ticket creado por la otra. Es un hallazgo por inspección, pendiente de reproducción con PostgreSQL real y dos conexiones. Usar inserción atómica con conflicto y recuperación de la solicitud existente.

5. **P2 — Pruebas con cobertura insuficiente para las garantías anunciadas.** `tests/test_public_entry.py:25` comprueba rutas privadas mientras `_state.ready` es falso: un 503 no demuestra protección en funcionamiento. La prueba original de persistencia usa SQLite, incluso detrás del wrapper SQLAlchemy; no ejecuta PostgreSQL. Los scripts conversacional y deduplicación imprimían FAIL sin devolver un código de salida distinto de cero. El diagnóstico de seguridad nuevo reproduce vulnerabilidades; su exit=0 indica que las observaciones se reprodujeron, no una aprobación de seguridad.

## Persistencia: problemas reproducidos y corregidos localmente por Codex

Sobre el código inicial, las cinco regresiones nuevas fallaron. Las correcciones aún locales cubren:

- CursorProxy sin iteración, incompatible con la agregación de solicitudes en métricas.
- Commit que ocultaba errores y cierre omitido si fallaba la salida de un contexto.
- ON CONFLICT sin el predicado del índice único parcial de interacciones.
- Conexión SQLite global que mezclaba rutas distintas y permanecía abierta; conexiones PostgreSQL obtenidas por database.py sin cierre explícito.
- Cualquier excepción de deduplicación interpretada como mensaje duplicado.

Se reemplazaron las conexiones por sesiones delimitadas, se hizo explícita la deduplicación por conflicto y se propagaron fallos de almacenamiento. Una sexta regresión verifica inserción/reintento, métricas, deduplicación, rollback y devolución al pool con SQLAlchemy sobre SQLite. **Esto no certifica integración con PostgreSQL real.**

## Cumplimiento de buenas prácticas

- Hay ramas locales y referencias remotas `feature/persistencia-datos-cloud`, `feature/fiabilidad-webhook-cpu`, `feature/pulido-respuestas-chatbot` y `feature/seguridad-y-optimizacion-despliegue`. El merge `caa38d5` integra persistencia. Las referencias locales no prueban por sí solas el estado actual remoto ni la revisión desplegada.
- Convenciones de commits presentes. Los últimos filtros incluyen db_adapter.py tanto en Docker como en gcloud.
- Extracción de servicios/visualización y organización de tests/docs son avances reales.
- Las pruebas ahora revisadas pasan, pero no prueban que se ejecutaran antes de los commits de Antigravity. No hay evidencia suficiente para afirmar cumplimiento total del ciclo local → Git → despliegue → verificación en vivo.
- Varias pruebas seguían generando informes en la carpeta principal activa; se ajustaron tres para escribirlos en docs/. Los logs de esta revisión están en logs/.
- El script fija min-instances=0. Esta revisión no certifica costo cero, facturación, persistencia remota efectiva ni disponibilidad continua.
- No se verificaron procedencia de las imágenes nuevas, construcción Linux, contenido efectivo del paquete gcloud ni configuración en producción. No se modificaron los datos oficiales F1/F2/F3.

## Evidencia local

Python 3.11 instalado del proyecto. Nueve suites terminaron con exit=0:

| Suite | Resultado |
|---|---|
| test_persistence_regressions | 6 regresiones, OK |
| test_db_persistence | Flujo SQLite y wrapper SQLAlchemy, OK |
| test_conversational | 29 PASS / 0 FAIL |
| test_audit_20260912 | 21 casos y comprobaciones adicionales, OK |
| test_dedup | 23 PASS / 0 FAIL |
| test_handoff | Persistencia, estados y concurrencia SQLite, OK |
| test_operational_metrics | Casos simulados, OK |
| test_public_entry | Pasa con las limitaciones descritas |
| test_runtime_settings | OK |

Logs: `logs/*_20260919.log`. Diagnóstico adicional: `tests/review_antigravity_20260919.py` y `docs/DIAGNOSTICO_ANTIGRAVITY_20260919.json`. `git diff --check` sin errores de espacios. No hubo llamadas al LLM ni mensajes externos en estas verificaciones.

Los cambios de Codex permanecen locales y sin commit al cerrar esta revisión. No se hizo push, merge ni despliegue. Prioridad siguiente: cerrar exposición pública y credenciales, después recuperar mensajes fallidos y validar transacciones/concurrencia con PostgreSQL real.

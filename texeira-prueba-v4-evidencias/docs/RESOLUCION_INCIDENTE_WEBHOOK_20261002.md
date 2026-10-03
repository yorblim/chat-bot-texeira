# Resolución Técnica del Incidente: Procesamiento de Lotes, Anti-Eco y Fallbacks en Webhook WhatsApp

Fecha: 2026-10-02  
Carpeta activa: `texeira-prueba-v4-evidencias`  
Rama de trabajo: `feature/fix-anti-eco-whatsapp`  

---

## 1. Diagnóstico y Causa Raíz con Evidencia en Registros

### A. Análisis del reporte inicial del usuario
El usuario presentó el siguiente extracto de conversación en WhatsApp:
```text
[9:34 p. m., 2/10/2026] yorblim: Hola
[9:34 p. m., 2/10/2026] +1 (555) 205-3249: ¡Hola! 👋 Soy el asistente virtual de Texeira Travel... 🗺️ Ver Tours
[9:34 p. m., 2/10/2026] yorblim: ¡Hola! Soy el asistente virtual de Texeira Travel... 🗺️ Ver Tours
[9:34 p. m., 2/10/2026] +1 (555) 205-3249: 🗺️ Catálogo de Experiencias — Texeira Travel...
[9:34 p. m., 2/10/2026] yorblim: Catálogo de Experiencias — Texeira Travel... 🌄 Clásicos Cusco
```

### B. Evidencia directa en registros de Cloud Run
Al inspeccionar los registros de Cloud Run (`gcloud logging read`) para el remitente `51921484423` durante ese intervalo exacto:
1. Las llamadas entrantes llegaron como eventos interactivos legítimos:
   `[WA INBOUND] message_id=... type=interactive text="ver categorias de tours" selected_phone=51921484423 user_id=51921484423`
2. El bot despachó un único mensaje interactivo por turno:
   `[WA INTERACTIVE OUTBOUND] mode=phone destination=51921484423 buttons=['...']`
3. Meta Graph API aceptó la petición con HTTP 200:
   `[WA INTERACTIVE RESPONSE] status_code=200 body={"messaging_product":"whatsapp", ... messages:[{"id": "wamid.HBgL..."}]}`
4. Los eventos de estado subsiguientes confirmaron la entrega y lectura normales:
   `[WA DELIVERY STATUS] status=sent` -> `status=delivered` -> `status=read`

**Conclusión del comportamiento en WhatsApp:**  
En el cliente de WhatsApp (especialmente WhatsApp Web/Desktop o exportación de historial), al pulsar un botón de respuesta rápida (`quick_reply`), la interfaz genera una cita/respuesta del usuario que antepone el texto del mensaje previo y añade al final el texto del botón pulsado. Por lo tanto, el texto atribuido a `yorblim` no era un mensaje saliente del bot duplicado por Meta, sino la representación del cliente de WhatsApp de la pulsación del botón.

### C. Vulnerabilidades críticas detectadas en el código
A pesar de lo anterior, la revisión técnica reveló dos vulnerabilidades reales en la arquitectura:
1. **Fallback ciego tras timeouts de red en `src/services/whatsapp.py`:**
   Ante excepciones de red o timeout (`httpx.ReadTimeout`, `httpx.TimeoutException`), el bloque `except` ejecutaba incondicionalmente un reenvío en texto plano. En un timeout de lectura HTTP, el mensaje interactivo original ya fue enviado a Meta y posiblemente despachado al cliente; el reintento a ciegas provocaba un segundo mensaje duplicado en el teléfono.
2. **Pérdida de mensajes en lotes en `app.py`:**
   El webhook solo procesaba `messages[0]`. Si Meta entregaba un lote donde el primer elemento era un evento `system` (ej. cambio de número del cliente) o un mensaje ignorado, el servidor devolvía HTTP 200 inmediatamente descartando cualquier mensaje de texto válido posterior en la misma entrega.
3. **Comparación errónea de identificadores:**
   La comprobación `msg_from == phone_number_id` comparaba el número de teléfono del usuario con el ID de recurso de Meta Graph API, lo cual no constituye una prueba válida de eco.

---

## 2. Correcciones Implementadas

### 1. Control estricto de Fallbacks en `src/services/whatsapp.py`
Se reescribió `send_whatsapp_interactive_buttons` para diferenciar estados confirmados de resultados inciertos:
- **Éxito (HTTP 200/201):** Retorna `True` sin ejecutar fallback.
- **Rechazo explícito del cliente (HTTP 4xx):** Meta rechazó el formato de los botones (ej. título mayor a 20 caracteres o ventana de 24h caducada). En este caso controlado, se ejecuta el fallback a texto plano (`send_whatsapp_message(buttons=None)`) para no perder la comunicación.
- **Error de servidor Meta (HTTP 5xx):** Estado incierto; se registra el error y retorna `False` sin fallback duplicador.
- **Excepciones de transporte y timeouts (`httpx.TimeoutException`, `httpx.RequestError`):** Estado de entrega incierto. Se registra la incidencia con `[WA INTERACTIVE TIMEOUT/NETWORK ERROR]` y se retorna `False` sin despachar texto adicional para evitar mensajes duplicados.

### 2. Procesamiento robusto de lotes en `app.py`
Se refactorizó el manejador del webhook de WhatsApp y Messenger:
- **Iteración completa de lotes:** Se recorren todas las combinaciones de `entry -> changes -> messages`.
- **Filtros no bloqueantes:**
  - Eventos `system`: se ignoran individualmente y se continúa con el resto del lote.
  - Eventos salientes oficiales (`msg.get("from_me") is True`): se ignoran individualmente.
  - Mensajes multimedia sin soporte ni texto: se ignoran individualmente sin tumbar mensajes válidos.
- **Deduplicación transaccional por mensaje:** Cada mensaje válido en el lote se reclama de forma independiente mediante `database.claim_webhook(msg_id, user_id)` y se finaliza con `database.finish_webhook`. Si un mensaje es reentregado, se marca como `dedup: True` sin repetir la inferencia RAG ni el envío.
- **Respuestas HTTP acordes:**
  - Si el lote contiene únicamente eventos de sistema: `HTTP 200 {"status": "ok", "ignored": "system_message"}`.
  - Si todos los mensajes ya estaban completados: `HTTP 200 {"status": "ok", "dedup": True}`.
  - Si algún mensaje procesable falla o está ocupado: `HTTP 503` con cabecera `Retry-After: 10`.

---

## 3. Matriz de Pruebas y Evidencias Locales (100% PASS)

Todas las suites se ejecutaron mediante el harness aislado `tests/run_isolated.py` con SQLite temporal y mocks de red:

| Caso de Prueba | Suite | Resultado | Qué Demuestra |
|---|---|---|---|
| Estados sin respuesta | `tests/test_review_anti_echo_20261002.py` | **PASS** | Los reportes de entrega (`statuses`) no generan llamadas a RAG ni respuestas |
| Sistema seguido de texto válido | `tests/test_review_anti_echo_20261002.py` | **PASS** | Evento `system` no descarta el mensaje de texto `Hola` en el mismo lote |
| Varios textos en un lote | `tests/test_review_anti_echo_20261002.py` | **PASS** | Se procesan todos los mensajes del lote individualmente (2 llamadas RAG, 2 envíos) |
| Reentrega del mismo ID | `tests/test_review_anti_echo_20261002.py` | **PASS** | Segundo envío del mismo ID retorna 200 OK con `dedup: True` sin reejecutar RAG |
| Envío interactivo aceptado | `tests/test_review_anti_echo_20261002.py` | **PASS** | Respuesta 200 de Meta entrega interactivo sin ejecutar fallback a texto |
| Rechazo explícito 400 | `tests/test_review_anti_echo_20261002.py` | **PASS** | Error 400 de Meta dispara fallback controlado a texto plano |
| Timeout de lectura | `tests/test_review_anti_echo_20261002.py` | **PASS** | `httpx.ReadTimeout` no dispara envío duplicado a ciegas (retorna `False`) |
| Suite de recuperación y concurrencia | `tests/test_webhook_recovery.py` | **PASS (6/6)** | Manejo de reintentos, deduplicación y protección de CPU en webhook |
| Botones interactivos | `tests/test_interactive_whatsapp_buttons.py` | **PASS (11/11)** | Formato, límite 20 caracteres y flujo de navegación interactiva |
| Regresiones conversacionales | `tests/test_conversational.py` | **PASS (36/36)** | Rutas sociales, listados, evidencias de catálogo y políticas |
| Auditoría de integridad | `tests/test_audit_20260912.py` | **PASS (21/21)** | Endpoints, resolución de conflictos y métricas |
| Deduplicación en SQLite | `tests/test_dedup.py` | **PASS (23/23)** | Concurrencia y persistencia de deduplicación tras reinicio |

---

## 4. Estado Git y Cumplimiento de `AGENTS.md`
- Rama de funcionalidad: `feature/fix-anti-eco-whatsapp`
- 100% pruebas unitarias e integradas pasando en local antes de Git.
- Cero código fantasma: trazabilidad completa respaldada.

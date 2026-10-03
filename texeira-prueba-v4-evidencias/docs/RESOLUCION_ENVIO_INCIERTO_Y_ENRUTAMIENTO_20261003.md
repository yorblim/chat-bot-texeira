# Resolución de Envíos Inciertos, Enrutamiento Multiusuario y Fallback Acotado

Fecha: 2026-10-03 (Lima)
Carpeta activa: `texeira-prueba-v4-evidencias`
Rama de trabajo: `feature/fix-uncertain-delivery-batch-routing`
Referencia de revisión previa: `docs/VERIFICACION_2a6d01d_20261003.md`

---

## 1. Resumen Ejecutivo de la Corrección

En atención a la revisión independiente documentada en `docs/VERIFICACION_2a6d01d_20261003.md`, se identificaron y solucionaron formalmente las tres causas raíz observadas:

1. **Tratamiento formal del resultado de envío incierto (`uncertain`)**:
   - **Problema previo**: Ante un timeout de red (`httpx.ReadTimeout` o `httpx.RequestError`) en el envío saliente, el webhook devolvía 503 pero marcaba el recibo en la base de datos como `failed`. En la reentrega de Meta, el recibo en estado `failed` era vuelto a reclamar y se disparaba un segundo envío interactivo idéntico hacia el cliente.
   - **Solución implementada**:
     - Se introdujo la clase `WhatsAppSendResult` en `src/services/whatsapp.py` que clasifica de manera formal y tipada el estado de entrega en:
       - `accepted`: HTTP 200/201 confirmado por Meta Graph API.
       - `rejected`: HTTP 4xx definitivo de Graph API.
       - `uncertain`: Pérdida de socket / timeout (`httpx.TimeoutException`, `httpx.RequestError`) o HTTP 5xx de Meta.
     - `database.py`: Se actualizó `finish_webhook` y `claim_webhook` para persistir el estado `uncertain` en la tabla `webhook_receipts`.
     - `app.py`: Si un mensaje tuvo un envío previo con resultado `uncertain`, en la reentrega el webhook detecta dicho estado, registra el evento para conciliación, **no vuelve a enviar un segundo mensaje al usuario** y devuelve HTTP 200 `{"status": "ok", "dedup": True, "uncertain": True}` para detener el ciclo de reintentos ciegos de Meta.
     - `operational_metrics.py`: Se incorporó el estado `send_uncertain` en los eventos operativos, impidiendo que una entrega desconocida se contabilice como éxito (`api_accepted`) ni como consulta resuelta.
     - Se mantiene 100% intacta la recuperación ante fallos legítimos previos al envío (e.g. errores de base de datos o excepciones antes del despacho de red), los cuales siguen registrándose como `failed` y recuperándose de forma segura.

2. **Asociación estricta de remitente y contacto por mensaje en lotes multiusuario**:
   - **Problema previo**: `app.py` extraía `contacts[0]` a nivel de lote y lo asociaba a todos los mensajes, priorizando `contact.wa_id` sobre `msg.from`. En lotes con múltiples usuarios (`cliente A` y `cliente B`), ambos mensajes se atribuían al primer contacto.
   - **Solución implementada**:
     - `app.py`: Se indexan los contactos de cada `change` por `wa_id` y `user_id`. Para cada mensaje, se asocia exclusivamente el contacto que coincida con `msg.from` o `msg.from_user_id`.
     - Se prioriza de forma estricta el identificador del propio mensaje (`msg.from` numérico para `phone_number` y `msg.from_user_id` para `bsuid`), evitando que un contacto ajeno contamine el destino o el historial de conversación en RAG.
     - La extracción de contactos está acotada al `change`/`value` correspondiente, garantizando aislamiento total entre distintas entradas (`entry`/`changes`).

3. **Restricción estricta del fallback a texto plano en errores HTTP 4xx**:
   - **Problema previo**: Se intentaba fallback a texto plano ante cualquier código HTTP 4xx, aun cuando se tratase de tokens caducados, permisos insuficientes o ventanas de atención de 24 horas cerradas.
   - **Solución implementada**:
     - Se añadió la función de guardia `is_interactive_format_error(status_code, resp_body)` en `src/services/whatsapp.py`.
     - Solo se permite fallback a texto plano si `status_code == 400` y el error confirma explícitamente problemas de formato/parámetros de botones (`button`, `interactive`, `parameter`, `payload length`, etc.).
     - Errores de credenciales (OAuth), cuotas/límites o expiración de ventana de 24 horas (código 131047) son marcados directamente como `rejected` sin fallback, preservando la causa original del fallo.

---

## 2. Evidencia de Pruebas Locales Automatizadas (100% PASS)

Todas las suites se ejecutaron mediante el ejecutor aislado `tests/run_isolated.py` con SQLite temporal y sin conexiones a proveedores externos:

| Suite de pruebas | Pruebas | Resultado | Descripción |
| :--- | :---: | :---: | :--- |
| `test_review_webhook_2a6d01d.py` | 2 | **PASS** | Regresiones independientes: deduplicación ante envío incierto y enrutamiento multiusuario. |
| `test_review_anti_echo_20261002.py` | 13 | **PASS** | Filtros anti-eco, eventos system, fallback interactivo controlado y deduplicación. |
| `test_webhook_recovery.py` | 6 | **PASS** | Recuperación ante fallos de procesamiento, idempotencia y reintentos legítimos. |
| `test_interactive_whatsapp_buttons.py` | 11 | **PASS** | Botones interactivos, validación de longitudes, parsing y fallback de formato. |
| `test_dedup.py` | 23 | **PASS** | Idempotencia atómica de webhooks, concurrencia y persistencia tras reinicio. |
| `test_conversational.py` | 36 | **PASS** | Respuestas conversacionales, enrutamiento RAG, listing de catálogo y asistencia. |
| `test_operational_metrics.py` | - | **PASS** | Registro y resumen de métricas operativas con distinción de envíos inciertos. |
| `test_persistence_concurrency.py` | - | **PASS** | Adquisición concurrente de leases, expiración y control transaccional de webhooks. |
| `test_messenger_adapter.py` | - | **PASS** | Adaptador de Messenger con firmas, deduplicación y aislamiento de canales. |

---

## 3. Estado de Archivos Modificados

- `src/services/whatsapp.py`: Clase `WhatsAppSendResult`, función `is_interactive_format_error`, retorno tipado de `send_whatsapp_message` y `send_whatsapp_interactive_buttons`.
- `database.py`: Persistencia y reconocimiento de estado `uncertain` en `claim_webhook` y `finish_webhook`.
- `operational_metrics.py`: Soporte de estado `send_uncertain` en `finish()` y `summary()`.
- `app.py`: Extracción y mapeo de contactos por mensaje y por `change`, retención de envíos inciertos sin repetición ciega, y respuesta HTTP 200 en reentregas de mensajes con resultado incierto.

# Verificación independiente del supuesto eco de WhatsApp

Fecha: 2026-10-02. Carpeta activa: `texeira-prueba-v4-evidencias`.
HEAD revisado: `5e86abc`. El parche de tres filtros en `app.py` sigue sin commit.

## Dictamen

No está demostrada la causa indicada por Antigravity. Ignorar eventos de sistema es una protección razonable, pero no prueba que Meta esté devolviendo las respuestas normales del bot como mensajes entrantes. La comparación `msg_from == phone_number_id` compara identificadores de distinta naturaleza y no constituye un detector fiable de eco.

Además, se reprodujo una pérdida de texto válido en un lote que empieza con un evento de sistema. El uso de `messages[0]` es una limitación preexistente del webhook; el parche la conserva y responde 200 antes de procesar el siguiente mensaje. Esta prueba no demuestra que ese lote concreto haya ocurrido en producción.

No se modificó la aplicación, no se enviaron mensajes reales y no se desplegó esta revisión. Se añadieron dos pruebas aisladas para dejar el hallazgo reproducible.

## Hallazgos

### 1. Diagnóstico de eco no acreditado

En la documentación oficial de Meta, `messages[].from` identifica al remitente; `metadata.phone_number_id` es el identificador del recurso del número del negocio. No son intercambiables. El tipo `system` documentado incluye cambios de número del usuario, no equivale a una respuesta saliente del bot.

Las notificaciones normales de envío, entrega y lectura llegan en `statuses`. `app.py` ya devuelve 200 para los eventos que contienen únicamente estados, antes de ejecutar el modelo o el envío. La nueva prueba confirma esta protección existente.

Referencias primarias:

- [Meta: Messages Object](https://www.postman.com/meta/whatsapp-business-platform/folder/1dtuocp/messages-object).
- [Meta: Message Status Update Notifications](https://www.postman.com/meta/whatsapp-business-platform/request/rgtfq23/message-status-update-notifications).

Ubicaciones revisadas: `app.py`, alrededor de 2312–2368.

### 2. Pérdida de un mensaje válido en un lote

Reproducción sintética firmada: `messages = [evento system, texto Hola]`.

Resultado: HTTP 200 con `ignored: system_message`; llamadas a RAG: 0; llamadas al envío: 0. El texto válido queda sin procesar. El servidor reconoce el lote como recibido, por lo que no debe depender de una nueva entrega para recuperar ese texto.

El parser también toma únicamente `entry[0]` y `changes[0]`. Una corrección del procesamiento por lotes debe conservar la firma, la identidad de cada remitente y la deduplicación por ID de cada mensaje. Ignorar un evento no debe descartar los demás.

### 3. Posible origen alternativo de dos respuestas, todavía no confirmado

`src/services/whatsapp.py` envía una respuesta con botones mediante una única llamada interactiva. Sin embargo, ante cualquier excepción de esa llamada ejecuta un segundo envío de texto como fallback.

Si Meta aceptó la primera petición pero la respuesta HTTP se perdió o el cliente agotó su tiempo de espera al leerla, el fallback puede producir un segundo mensaje. Esto es una hipótesis respaldada por el recorrido del código, no la causa demostrada del incidente. Una excepción de transporte con resultado incierto no equivale a un rechazo explícito de Meta.

Se necesita correlacionar el ID del mensaje entrante, los intentos de salida, sus `wamid`, estados HTTP y errores de transporte en la revisión que presentó el problema. No registrar tokens, cabeceras de autorización ni conversaciones completas innecesarias.

### 4. Tipos no soportados

El filtro de audio, imagen y documento descarta mensajes reales del cliente que el bot no procesa. Esto delimita el soporte del canal, pero no demuestra ni soluciona un eco. El comportamiento debe quedar explícito y no debe provocar que se pierda otro texto del mismo lote.

## Evidencia local

Todas las pruebas siguientes usaron SQLite temporal y envíos/modelo simulados. No consumieron Groq ni enviaron mensajes por Meta.

| Suite | Resultado | Qué demuestra |
| --- | --- | --- |
| `tests/test_review_anti_echo_20261002.py` | 1 PASS / 1 FAIL | Los estados no generan respuesta; se pierde el texto después del evento system |
| `tests/test_webhook_recovery.py` | 6 PASS / 0 FAIL | Se mantienen las garantías cubiertas de recuperación y deduplicación |

Comandos reproducibles desde la carpeta activa:

```powershell
python tests/run_isolated.py test_review_anti_echo_20261002.py
python tests/run_isolated.py test_webhook_recovery.py
```

Logs: `logs/review_anti_echo_20261002.log` y `logs/review_anti_echo_recovery_20261002.log`.

## Encargo consolidado para Antigravity

Antes de versionar o desplegar, revisa esta evidencia y corrige el fallo reproducible. No presentes el eco como causa confirmada sin una traza real anonimizada. Distingue estados, eventos de sistema, mensajes del cliente y cualquier evento de eco que realmente llegue; no compares `from` con el ID Graph del número del negocio para deducir el origen. Procesa los eventos válidos de cada lote sin descartarlos por un primer evento ignorado, conservando la deduplicación por mensaje y la recuperación existentes. Revisa el fallback de interactivo a texto ante timeouts: diferencia rechazo confirmado de resultado de envío incierto y evita segundos envíos a ciegas.

Prueba al menos: estados sin respuesta; system seguido de texto válido; varios textos del lote; reentrega del mismo ID; botones válidos; envío interactivo aceptado sin fallback; rechazo explícito con fallback controlado; timeout de lectura sin duplicación automática. Usa proveedores simulados para las regresiones y una traza real para atribuir la causa del incidente. Mantén intactas las reglas del catálogo, los idiomas, las recomendaciones y las reservas. Documenta qué quedó probado y qué sigue sin evidencia.

Sigue el protocolo de `AGENTS.md`: pruebas locales antes de Git, rama `feature/...`, commit probado, integración y respaldo antes del despliegue. La rama sugerida `fix/anti-eco-whatsapp` no sigue la convención del proyecto; usa por ejemplo `feature/fix-anti-eco-whatsapp`.

No cerrar el incidente solo porque `/health` responde 200. El criterio de cierre es que una entrada válida produzca la respuesta prevista una sola vez, salvo multimedia adicional solicitada expresamente, sin pérdida de mensajes ni respuestas originadas por estados o eventos de sistema.

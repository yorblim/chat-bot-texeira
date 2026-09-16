# Revisión de avances y pendientes — 15/09/2026

No está terminada la implementación completa ni validada la tesis. Se revisaron los archivos actuales tras los cambios de Antigravity y se corrigieron problemas concretos. Copia previa de archivos intervenidos: `audit_revision_final_20260915/`. No se desplegó, cambió Meta, envió mensajes ni modificaron credenciales en esta revisión.

## Evaluación real autorizada

`EVALUACION_REAL_EXPLORATORIA_20260915.json`: cuatro llamadas completadas a Groq, modelo `qwen/qwen3.8-27b`, 4617 tokens reportados, sin errores de proveedor. Este resultado corresponde al código ANTERIOR a las correcciones de esta revisión. No hubo nuevas llamadas después de corregirlo.

| Caso | Revisión técnica del resultado observado |
|---|---|
| Comparación Humantay / 7 Colores ES | Servicios respaldados por el contexto recuperado F1/F2/F3, pero mezcló fuentes aunque se pidió folleto y reprodujo el conflicto antiguo del índice. No aprobar como prueba de sincronización del catálogo. |
| Machu Picchu en tren EN | Inclusiones respaldadas, idioma correcto; no promete comidas ni noche de hotel. |
| Hotel para dormir ES | No inventa nombre, pero presupone alojamiento al decir «donde se alojará» y no distingue suficientemente recojo de hospedaje. Necesitaba corrección. |
| Accesibilidad Humantay EN | Reconoce ausencia de datos y solicita confirmación, sin garantizar accesibilidad. Sin embargo, el indicador de confirmación era falso. |

Los indicadores de hotel/accesibilidad no reflejaban la incertidumbre expresada. Se corrigió el marcado de respuestas que declaran explícitamente ausencia de información, con pruebas locales que reutilizan respuestas guardadas. Se añadió una respuesta documentada de incertidumbre para pernocte en Machu Picchu en tren. Esta protección por patrones no es una medición semántica universal de resolución. No afirmar 4/4 aprobados ni ausencia universal de alucinaciones. Primera consulta: 31.39 s incluyendo inicialización; siguientes 1.06, 0.73 y 0.64 s. No son tiempos de entrega por WhatsApp.

## Hallazgos corregidos

1. Messenger aceptaba payloads sin firma si faltaba FB_APP_SECRET. Ahora rechaza configuración ausente con 503 y firma ausente/incorrecta con 403. Reconoce `message.is_echo`. El modo exclusivo Messenger ahora carga el token de verificación compartido.
2. La prueba Messenger anterior ejecutaba trabajo en segundo plano sin aislar RAG/envío/logs. Reemplazada por pruebas firmadas con RAG, salida y persistencia simulados.
3. Las notificaciones al asesor podían activarse desde pruebas locales. Ahora solo canales WhatsApp/Messenger y activación explícita `TEXEIRA_ENABLE_ADVISOR_NOTIFICATIONS=true`; no se activó aquí. Pruebas verifican duplicados, canal test y modo deshabilitado.
4. El banco «académico» usaba MockLLM, ignoraba inclusiones requeridas y daba por fiel cualquier respuesta sin unas palabras prohibidas. Además creaba solicitudes en la base humana real. Ahora recolecta en base temporal, sin avisos externos, sin métricas de tesis y con revisión humana pendiente. Los antiguos resultados están respaldados, no son evidencia académica válida.
5. `help` y `bye` respondían en español; corregidos y probados.

## Verificación ejecutada

- `test_revision_final_local.py`: incertidumbre y ayuda/despedida EN, aprobado.
- `test_messenger_adapter.py`: configuración, firma, recepción, salida simulada, duplicado y eco, aprobado.
- `test_handoff_notification.py` y `test_handoff.py`: aprobados.
- `test_operational_metrics.py`: aprobado con webhook y envíos simulados, base temporal.
- `test_audit_20260912.py`: 21/21; `evaluate_language_local.py`: 16/16. Sus expectativas de horarios fueron modificadas por Antigravity; aprobar estas pruebas no valida la confirmación de la agencia.
- `evaluate_academic_benchmark.py`: 30 casos recolectados en simulación; calificación pendiente, cero llamadas LLM reales.
- Logs en `audit_revision_final_20260915/*.log`. Se reinició únicamente el chat local 8021; logs `review_final_20260915.out.log` y `.err.log`. No se comprobaron los canales externos en esta revisión.

## Bloqueos y orden de cierre

1. **Catálogo e índice — corregido:** el usuario confirmó expresamente que la agencia prioriza los horarios F1. Se conservan los datos. El índice anterior contenía tres conflictos antiguos pese a READY actualizado. Se construyó y activó `chroma_f1_confirmado_20260915_db`: 20 documentos y metadatos exactos, sin conflictos antiguos. Evidencia: `VERIFICACION_INDICE_F1_20260915.json`; cuatro búsquedas locales aprobadas RRF60/top5/cap2. Índice anterior conservado. Chat local reiniciado con PID 21376; no se reiniciaron ni probaron canales externos.
2. **Messenger:** completar procesamiento de todos los eventos de un lote (actualmente toma el primero), configuración real de página/token/suscripción y prueba de conversación firmada. El adaptador local no equivale a canal conectado. Métricas operativas actualmente cubren WhatsApp, no Messenger.
3. **Asesor:** confirmar destinatario y autorización, configurar notificación y comprobar recepción real. El vínculo 127.0.0.1 enviado al asesor apunta a su propio dispositivo, no al PC de la agencia; definir acceso privado al panel. Probar atención y cierre, no solo creación del ticket.
4. **Nube:** corregir Docker/Compose antes de usarlos. Variables WHATSAPP_* no corresponden a META_* del código; faltan activación y proveedor/modelo, caché de embeddings offline, persistencia de trial_logs.db y montaje correcto de human_requests.db. Healthcheck único en 8021 no corresponde a otros servicios. Publicar solo entrada restringida y definir acceso privado del asesor. Construcción, HTTPS, reinicio y persistencia no probados; ningún uptime demostrado.
5. **Evaluación:** revisar criterios con fuentes y asesor académico; el banco usado para corregir código ya no es independiente. Separar pilotos/simulación de métricas reales. Revisar registros sintéticos anteriores antes de un estudio; no se borraron datos del piloto. Aplicar pretest/postest y encuestas reales.

La documentación previa que dice «30/30 académico», «100% precisión» o «24/7 completado» queda corregida por este informe. Archivos de despliegue y rúbrica llevan avisos de borrador. No se debe dar por resuelta la parte de campo ni el despliegue a partir de archivos creados.

# Continuidad del proyecto Texeira — 16/09/2026

## Objetivo vigente

El usuario quiere WhatsApp para sus tres números de prueba con el PC apagado, sin pagar nada. Messenger está aplazado por falta de acceso a Facebook. No autoriza facturación, compras ni servicios de pago.

## Estado actual

- Trabajar en C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias. Respetar instrucciones locales, conservar texeira-chatbot y credenciales. No publicar registros ni secretos.
- Proyecto Northflank texeira-bot creado en US Central. Alojamiento compatible y persistencia gratuita aún no verificados. No hay despliegue remoto comprobado.
- Antigravity propuso Cloud Run, pero guía y entrada tenían defectos. Se auditaron y corrigieron localmente. Cloud Run bloqueado por K_SERVICE; arquitectura requiere CPU continua y no tiene cola durable. No seguir recetas antiguas Cloud Run.
- Entrada corregida: arranque falla si falla RAG/configuración; salud y POST no listos retornan 503; token vacío rechazado; ACK pasa directamente sin esperar tareas; no expone errores internos.
- Compose establece PORT=8022 coherente con salud/publicación. Volumen state-data sirve en Docker local/VPS, no implica persistencia en hosting efímero. Docker usa exec para recibir señales.
- .dockerignore y .gcloudignore usan lista permitida. Construcción e inventario real de subida deben verificarse antes de enviar archivos a un hosting. Docker/gcloud no estaban disponibles en la auditoría.
- runtime_settings.py prioriza entorno remoto y permite TEXEIRA_STATE_DIR para bases. Conserva fallback local. No exponer paneles de asesor.
- Índice activo chroma_f1_confirmado_20260915_db: 20 documentos/metadatos verificados, cuatro búsquedas locales aprobadas. Usuario confirmó horarios F1 sobre PDF.
- Groq: cuatro consultas autorizadas ya consumidas, 4617 tokens. No repetir sin nuevo alcance; no fueron prueba de precisión universal. Evaluador académico ahora simulado y requiere calificación humana.

## Verificación de la corrección actual

Pruebas test_public_entry.py, test_runtime_settings.py, test_operational_metrics.py, test_handoff.py y test_audit_20260912.py (21 casos) terminaron exit=0. Sin llamadas a Groq ni Meta. Logs y respaldos en audit_fixes_20260916. No se probó imagen Docker ni despliegue real. No se reiniciaron servidores durante esta corrección; no asumir que procesos anteriores cargan los archivos nuevos.

## Pendientes reales

1. Encontrar recursos gratuitos comprobados con RAM suficiente (referencia local previa ~771 MB, no pico Linux), CPU continua y persistencia; o explicar/rediseñar alternativa antes de afirmar compatibilidad.
2. Construir y probar imagen, firma/ACK, memoria, recuperación y persistencia. BackgroundTasks es memoria: caída después del ACK puede perder trabajo; falta cola durable para resiliencia a cierres.
3. Revisar token Meta y conectar callback HTTPS remoto, luego probar con los tres números y PC apagado. No enviar mensajes a terceros sin autorización explícita.
4. Asesor y Messenger después. Avisos externos al asesor siguen deshabilitados por defecto.
5. Evaluación académica independiente y campo reales; no usar porcentajes simulados como precisión ni etiquetas del bot como resolución validada.

## Para otro agente

Leer DESPLIEGUE_NORTHFLANK_PENDIENTE.md (guía nueva sin comandos Cloud Run), BITACORA_AVANCES.md y los informes REVISION_ANTIGRAVITY_20260916.md / CORRECCIONES_DESPLIEGUE_20260916.md en v4. Continuar solo dentro del presupuesto cero. Registrar cambios, pruebas realmente ejecutadas, límites y siguiente paso. No confundir corrección local con despliegue ni garantizar 24/7.

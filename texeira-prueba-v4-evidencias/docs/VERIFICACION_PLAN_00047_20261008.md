# Corrección del plan de validación 00047

Fecha: 08/10/2026. Solicitud: el usuario pidió que Codex aplicara las correcciones señaladas al plan de Antigravity. Base revisada: b4c6236. Rama: feature/fix-whatsapp-validation-methodology.

## Cambios

- El plan acepta incertidumbre justificada sobre inclusiones de Camino Inca y verifica el estado vigente de Choquequirao, sin inventar causas. Corrige la referencia de este producto a F2 página 18.
- Diferencia fuentes documentales, constantes del código, perfiles de actividad y datos administrativos vigentes. Paginación y recursos no dependen de una lista o archivo fijo.
- Separa aislada, api_chat, api_webhook y whatsapp_real. Precisa qué acredita cada modalidad, incluidos canal test, parsing de botones y recepción multimedia.
- Define preparación de historial y tickets, recorridos enlazados y fixtures exactos para memoria/tarifa. Limpiar historial no equivale a cerrar una solicitud.
- Separa motor esperado de observado. El registro inicial conserva reglas, recuperación y LLM en null. RAG y generación pueden intervenir juntos.
- Corrige la evidencia de salud: timeout de 25 segundos seguido de reintento 200, sin atribuir causa ni un máximo de cold start.
- Añade plantilla JSON de ejecuciones y criterios de calificación/cobertura. Todos los casos permanecen sin ejecutar y la evaluación actual sin porcentaje.

## Validación local de documentación

Se comprobaron los 42 IDs en matriz, resumen y JSON: únicos, ordenados y coincidentes. Los 42 resultados iniciales son No ejecutado; todas las ejecuciones y observaciones están vacías. JSON válido, enlaces locales comprobados y git diff --check sin errores.

Se contrastaron con Git, byte a byte, los resultados e informe históricos originales de 21/09 y el JSON recalificado de 04/10: no fueron modificados.

Dos revisiones independientes de lectura contrastaron criterios y metodología con la aplicación. Se atendieron también sus ajustes de consistencia entre matriz y resumen.

Estas comprobaciones validan la preparación documental. No representan 42 respuestas aprobadas ni una evaluación nueva del LLM. No se reejecutaron suites de aplicación porque no se cambió código.

## Alcance y continuidad

Archivos:

- [Plan corregido](PLAN_VALIDACION_WHATSAPP_REVISION_00047.md).
- [Registro vacío del piloto](REGISTRO_VALIDACION_WHATSAPP_00047.json).

No hubo nuevas llamadas a Groq, envíos WhatsApp, cambios de catálogo, eliminación de datos de producción o despliegues. La configuración del bot permanece fuera de esta corrección documental.

El siguiente paso es ejecutar la matriz con sesiones preparadas y registrar evidencias por caso y modalidad. Messenger sigue pendiente.

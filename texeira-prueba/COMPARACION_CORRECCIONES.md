# Comparación de la prueba piloto — 11 de septiembre de 2026

Alcance: copia texeira-prueba, servidor local 8020. Código y catálogo originales conservan sus hashes anteriores. No se modificaron índices ni configuración de WhatsApp.

Evidencia anterior: live-five-20260911-024456.json.
Evidencia posterior: live-five-20260911-105504.json. Ambas se conservan sin editar.

| Consulta | Resultado posterior |
| --- | --- |
| Precio Valle Sagrado | USD 40–60 referenciales; respuesta centrada en precio |
| ¿Y qué incluye? | Conserva Valle Sagrado y muestra condiciones simuladas |
| ¿Las entradas están incluidas? | Conserva contexto; muestra boleto y accesos como excluidos |
| Cancelar gratis mañana | No promete condiciones; resolved_autonomously=false y needs_agency_confirmation=true |
| Inclusiones de Machu Picchu en inglés | detected_language=en; respuesta en inglés, coherente con el escenario simulado |

Cinco respuestas HTTP 200; cuatro rutas deterministas y una ruta RAG con proveedor real. La petición RAG tardó 38,204 segundos, incluyendo la carga inicial de recursos; esta medición no permite atribuir toda la demora al proveedor.

Se corrigió el detector para usar palabras completas y excluir nombres de destinos como evidencia de idioma. Se acortaron las respuestas estructuradas por intención. Las consultas españolas de cancelación/reembolso tienen una ruta explícita de información no confirmada. No se crea ni se afirma una derivación efectiva a un asesor.

test_trial.py pasó con proveedor simulado y recuperación local: precios, contexto, detección ES/EN/PT/FR en ejemplos, prudencia y aislamiento de Meta. Las advertencias de deprecación y telemetría de Chroma no bloquearon las pruebas.

Después de la prueba HTTP se añadió la etiqueta PROTOTIPO a la respuesta de cancelación; esta variante pasó las pruebas locales. No cambia las condiciones ni los indicadores.

Limitaciones: es una regresión de cinco casos conocidos, no una medición de exactitud general ni una evaluación académica final. La detección por reglas puede fallar en mensajes ambiguos. La ruta explícita de políticas cubre español; otras consultas y lenguas todavía requieren evaluación. resolved_autonomously no demuestra corrección factual de una respuesta. Pendiente ampliar casos independientes, revisar latencia y validar precios y condiciones con la agencia.

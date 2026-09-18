# Revisión de cambios de Antigravity — 15 de septiembre

Comparación con audit_language_backup: cambios detectados en verified_routes.py y handoff_support.py. No hay historial Git que permita atribuir con certeza cada cambio a una herramienta; se revisaron las diferencias disponibles.

La versión recibida aprobó los 12 casos existentes ES/EN. Mejoró las plantillas inglesas de precios, disponibilidad, conflictos, Machu Picchu y el aviso para solicitar asesor. Era una mejora válida pero incompleta.

## Correcciones realizadas

1. La traducción de duración reemplazaba cualquier texto con «itinerario publicado» por 4 días. Ahora traduce el texto conservando la cantidad recibida y la advertencia sobre noches. Pruebas con 3, 4, 5 y 8 días y con horas.
2. Las inclusiones de tours distintos de Machu Picchu mantenían conceptos españoles después de «Includes». Se agregaron traducciones de conceptos del catálogo; los topónimos se conservan.
3. «speak to an agent» registraba correctamente la solicitud pero confirmaba en español. Ahora los estados y el error de registro tienen respuesta en inglés cuando la solicitud se hizo en ese idioma; se conserva el texto final en el historial.

## Evidencia

- Antes: audit_antigravity_20260915/baseline.json, 12/12 del banco original.
- Después: EVALUACION_IDIOMAS_LOCAL.json, 16/16 casos conocidos. Se añadieron Humantay, cuatrimoto, boleto excluido y seguro no documentado.
- test_duration_translation.py: PASS; conserva cantidades.
- test_handoff.py: PASS; incluye confirmación inglesa e historial, además de estados, persistencia y protección.
- test_audit_20260912.py: 21/21 PASS.
- Hashes de catálogo, hechos, conflictos y registro de fuentes coinciden con el marcador del índice activo. No se reindexó ni alteraron las fuentes.
- Sin llamadas a Groq y sin mensajes externos en esta revisión. Bases temporales o registros sustituidos para las pruebas.

Respaldo previo a correcciones: audit_antigravity_20260915. El banco de evaluación no se agrega al contexto del bot ni al índice.

## Límites y siguiente etapa

16/16 representa aprobación de estos casos de regresión. No es precisión estadística ni demuestra comprensión general o calidad del LLM. No se evaluaron generación real, francés, portugués, todos los giros lingüísticos o casos de alta carga.

Siguiente: evaluar un conjunto separado de preguntas no usadas para corregir estas plantillas, registrar la ruta real y puntuar la respuesta contra las fuentes con una rúbrica. Reportar por separado interpretación, exactitud, idioma y reconocimiento de incertidumbre. Las rutas deterministas no se deben presentar como consultas al LLM. Cualquier error de proveedor debe conservarse como fallo operativo, sin contarlo como respuesta correcta.

La conexión WhatsApp de ayer no se certifica como activa hoy por estas pruebas locales. No se renovaron tokens, túneles ni suscripciones.

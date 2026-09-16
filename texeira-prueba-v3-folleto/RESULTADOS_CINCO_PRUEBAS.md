# Cinco pruebas en el servidor local

Fecha: 11 de septiembre de 2026. Evidencia: live-five-20260911-024456.json.

Se enviaron las cinco preguntas autorizadas al endpoint /test-chat de 127.0.0.1:8020, el mismo backend del chat web. Se usó un identificador nuevo y el mismo historial durante toda la secuencia. No se envió nada a WhatsApp. No se modificó el comportamiento del bot durante las pruebas.

| Pregunta | Hallazgo | Evaluación manual |
|---|---|---|
| ¿Cuánto cuesta Valle Sagrado? | USD 40–60, identificado como estimación, no tarifa oficial | Cumple el escenario provisional |
| ¿Y qué incluye? | Mantiene Valle Sagrado y enumera transporte, guía y almuerzo | Seguimiento correcto, pero repite toda la ficha |
| ¿Las entradas están incluidas? | Mantiene Valle Sagrado; indica boleto turístico excluido | Dato correcto dentro del escenario, respuesta poco directa |
| ¿Puedo cancelar gratis mañana? | No confirma gratuidad; explica que falta la política y remite a la agencia | Manejo prudente de información ausente; no resuelve la condición comercial |
| What does the Machu Picchu tour include? | Respuesta completa en español y detected_language=es | Falla el requisito de idioma |

## Alcance del resultado

Las cinco solicitudes devolvieron HTTP 200, sin errores de transporte observados. La cuarta pasó por generación del servidor real; las otras cuatro tomaron la ruta estructurada según las condiciones del código y sus respuestas. No se sustituyó el modelo por un mock en esta ejecución. No se capturaron tokens ni facturación del proveedor, por lo que no se cuantifica el consumo.

Cuatro casos cumplen su comprobación principal de contenido/seguimiento/prudencia y uno falla idioma. Esta es una comprobación dirigida de cinco turnos de una conversación, no una tasa de precisión general ni cinco usuarios independientes. Los precios siguen siendo estimaciones: no se validó exactitud comercial de Texeira.

Latencias comunicadas por el servidor: 0, 0, 330.83, 837.62 y 0 ms. Los ceros no significan respuesta instantánea real: el cliente midió aproximadamente 109 ms en el primer turno. No usar estas cinco muestras para conclusiones estadísticas de velocidad.

## Problemas comprobados y siguiente corrección propuesta

1. Idioma: el quinto turno se clasifica como es y activa la ficha española. Corregir la detección/ruta y volver a probar ES/EN/PT/FR con preguntas equivalentes y nuevas variantes.
2. Presentación: los tres primeros turnos reciben la misma ficha completa. Dar primero la respuesta específica solicitada y mantener el aviso referencial de forma breve.
3. Métricas: todos los turnos se marcan resolved_autonomously=true, incluso la consulta de cancelación sin información y la respuesta en idioma incorrecto. Ese indicador no demuestra resolución correcta; distinguir remisión por información pendiente y evaluación de calidad.

No se aplicaron estas correcciones todavía. El original de WhatsApp permanece fuera de esta prueba. Mantener esta evidencia sin sobrescribirla para comparar después.

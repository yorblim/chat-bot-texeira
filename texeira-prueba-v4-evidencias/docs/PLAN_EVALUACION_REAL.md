# Muestra exploratoria de generación real

Ejecutada el 15 de septiembre tras nueva autorización explícita: cuatro llamadas completadas a Groq, 4617 tokens reportados. Resultado crudo: EVALUACION_REAL_EXPLORATORIA_20260915.json. Revisión y límites: REVISION_AVANCES_20260915.md. Las correcciones posteriores se probaron localmente, sin repetir llamadas reales.

Evaluador: evaluate_live_sample.py. Hasta cuatro llamadas, sin reintentos, timeout 45 s por llamada. Conserva proveedor/modelo configurado, temperatura 0.1 y máximo de salida 900 tokens. Se detiene ante fallo del proveedor. Captura ruta efectiva, documentos recuperados, entrada y respuesta del LLM, respuesta final y uso de tokens cuando esté disponible. No escribe interacciones del piloto ni envía mensajes por WhatsApp.

| Caso nuevo | Criterio previo |
|---|---|
| Comparar servicios de Humantay y Montaña de 7 Colores (ES) | Transporte, guía, desayuno y almuerzo según F1; no inventar precios, cupos ni igualdad de horarios. |
| Resumir servicios de Machu Picchu en tren (EN) | Responder en inglés y respetar los servicios de F1/F3; no prometer comidas ni alojamiento. |
| Nombre exacto del hotel para dormir en Machu Picchu en tren (ES) | Reconocer que no está documentado. Recojo del hotel no significa alojamiento incluido. |
| Accesibilidad para silla de ruedas durante todo Humantay (EN) | No garantizar accesibilidad no documentada; solicitar confirmación. |

Revisar cada respuesta en cuatro dimensiones separadas: pertinencia a la intención; fidelidad a fuentes; idioma; manejo de información ausente. Marcar aprobado/fallido y justificar con el texto concreto. La evaluación del asistente es una revisión técnica, no validación independiente por expertos o turistas.

Si una ruta no llama al LLM, documentarla como determinista y no contabilizarla como prueba generativa. Conservar los errores operativos; no sustituirlos por simulación. Un resultado positivo en cuatro casos no permite afirmar precisión general ni ausencia universal de alucinaciones.

Las preguntas y criterios no se añaden al índice ni al prompt del bot. Mantener esta muestra separada de la batería de regresión utilizada para corregir plantillas.

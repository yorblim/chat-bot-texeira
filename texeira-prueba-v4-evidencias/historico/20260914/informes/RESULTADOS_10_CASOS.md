# Resultado exploratorio de diez casos — 11 de septiembre de 2026

Evidencia: evaluation-ten-local-20260911-111211.json y evaluation-ten-live-20260911-111304.json. Expectativas conservadas en EVALUACION_10_CASOS.md; no se ajustaron después de observar respuestas.

Se comprobaron diez rutas con proveedor simulado. Cuatro produjeron respuestas deterministas reales evaluables (C01, C02, C05, C10). Las otras seis respuestas simuladas se excluyeron del juicio de contenido y se sustituyeron por una ejecución HTTP con proveedor real. Se realizaron seis solicitudes al servidor, sin reintentos; todas devolvieron HTTP 200 y ruta RAG, sin errores reportados. No se midieron tokens ni reintentos internos del SDK.

| Caso | Contenido observado | Dictamen |
| --- | --- | --- |
| C01 | City Tour USD 15–25, explícitamente referencial | Cumple |
| C02 | Conserva City Tour; 4–6 horas estimadas | Cumple |
| C03 | Inglés; Rainbow Mountain USD 25–45 por adulto, estimación | Cumple |
| C04 | Inglés y seguimiento correctos; caballo/ATV excluidos del escenario | Cumple; la disponibilidad de alquiler separado no está comprobada |
| C05 | Caballo excluido en Humantay; condiciones simuladas | Cumple |
| C06 | Paquete hipotético, no oferta confirmada; contacto publicado correcto | Cumple contenido; indicador de derivación incorrecto |
| C07 | No inventa Yape ni adelanto; consulta con agencia | Cumple contenido; pendiente mal registrado |
| C08 | Rechaza confirmar cupos/reserva, pero ofrece fuentes de precios para contactar con la agencia | Parcial: confunde referencias de otros operadores con contacto de Texeira |
| C09 | No inventa soles ni cambio; da USD referenciales | Cumple contenido; pendiente mal registrado; expone reglas internas innecesarias |
| C10 | Política sin confirmar, contacto y flags prudentes | Cumple; frase sobre gratuidad poco directa para una pregunta de devolución |

No se declara el sistema totalmente validado ni una tasa general de exactitud a partir de esta muestra mixta. Hay nueve respuestas que cumplen los criterios de contenido, una parcial y problemas adicionales de métricas/calidad editorial.

## Problemas comprobados

- C06 devolvió escalated_to_human=true aunque no existe una derivación efectiva. La respuesta incluso niega prometer contacto automático: la detección por frases genera un falso positivo.
- C07, C08 y C09 devolvieron resolved_autonomously=true y needs_agency_confirmation=false, aunque la condición comercial solicitada queda pendiente. La respuesta prudente no equivale a resolver la operación solicitada.
- C08 ofrece enlaces de fuentes de precios como vía de contacto de la agencia; esas fuentes incluyen otros operadores. Debe orientar al contacto de Texeira identificado en el catálogo.
- C09 presenta una «prohibición de conversiones» como explicación al usuario, cuando bastaría informar que falta una cotización o tipo de cambio confirmado.

Las seis solicitudes HTTP duraron 2,832; 1,004; 1,243; 0,920; 1,034 y 5,339 segundos. El servidor tenía el buscador precargado. Son tiempos de estas solicitudes, no un benchmark comparable controlado ni tiempos aislados del proveedor.

Siguiente corrección acotada: separar información pendiente de derivación efectiva en los indicadores y corregir la orientación de contacto. Después repetir únicamente casos afectados. No modificar precios ni arquitectura a partir de esta corrida. No se cambió el comportamiento del bot durante la evaluación ni se modificó el proyecto original.

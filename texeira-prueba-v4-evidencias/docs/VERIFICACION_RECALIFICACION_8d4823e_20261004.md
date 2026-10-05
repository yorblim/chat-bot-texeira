# Verificación independiente de 8d4823e

Fecha: 04/10/2026. Carpeta activa: `texeira-prueba-v4-evidencias/`.
Encargo: contrastar el último informe de Antigravity con código y pruebas.

## Dictamen

Las correcciones del horario desconocido, el fixture de horario confirmado y la eliminación de importes ficticios del mock están implementadas. La recalificación automática de las 30 respuestas históricas se reproduce: 22 aprobadas, 8 rechazadas (73,3%). Los archivos originales del 21/09 permanecen intactos.

No está cerrado el calificador: todavía aprueba tres controles negativos que contradicen los criterios del banco. Además, el JSON recalificado pierde metadatos operativos originales y el informe conserva conclusiones que exceden la evidencia.

Estos hallazgos se refieren al evaluador y su informe. Los controles sintéticos siguientes no son respuestas observadas del bot actual. El 73,3% corresponde a respuestas del 21/09, revisión histórica 00021, y no mide la precisión de la revisión actualmente desplegada.

## Verificación ejecutada

Todas las ejecuciones usaron `tests/run_isolated.py`, que bloquea red externa, y bases temporales. No se importó el flujo principal de posprueba ni se ejecutó su acceso a Cloud Run, Secret Manager o Neon. Solo se extrajo la función `evaluate_case()` mediante AST.

| Comprobación | Resultado | Evidencia en logs/ |
| --- | --- | --- |
| Regresión original del calificador (tour equivocado, duración ausente, control correcto) | 3/3 PASS | `review_8d4823e_grader.log` |
| Recorridos WhatsApp con transporte simulado | 13/13 PASS | `review_8d4823e_flow.log` |
| Recomputar los 30 casos, verificar originales intactos y ejecutar calidad con mock y reportes temporales | 3/3 PASS; incluye 13 consultas simuladas | `review_8d4823e_recalibration_quality.log` |
| Controles negativos de factualidad y conservación de metadatos | 4/4 pruebas FALLAN, mostrando defectos restantes | `review_8d4823e_polarity.log` |

La prueba de calidad sigue siendo validación simulada de rutas con aserciones básicas; no mide precisión generativa, entrega real WhatsApp ni toda la coherencia lingüística. Los reportes de esa ejecución fueron redirigidos al directorio temporal para preservar los históricos. Se utilizó una copia temporal del índice para la ejecución de calidad. Las suites de recomendaciones no cambiaron en este commit; no fue necesario repetirlas en esta revisión.

## Correcciones verificadas

- `tests/test_whatsapp_flow_polish.py:208`: Machu Picchu en Tren omite horario fijo y `04:00`, coherente con `schedule_status: unknown`. El fixture explícito de las líneas 219–232 usa `08:00 - 13:00` y `5 horas`; no se introdujo como dato oficial.
- `tests/test_calidad_whatsapp.py:73`: se retiraron los importes $120/$85/$65/$35 del mock. Su metadata distingue validación simulada de precisión generativa real.
- `tests/evaluate_thesis_postest.py:44`: el calificador ya rechaza la respuesta histórica sobre otro tour y la ausencia de los cuatro días requeridos. Conserva aprobado el control correcto.
- Recomputación: IP 29/30; FF 22/30; CI 30/30; MI 30/30; aprobado simultáneo 22/30. Coinciden todos los criterios y motivos calculados de los 30 casos con el JSON nuevo; ES 12/15 y EN 10/15.

## Defectos reproducidos del calificador

| Caso del banco | Control incorrecto que recibió `passed=1` | Causa y corrección requerida |
| --- | --- | --- |
| ACAD-EN-02 | `Sacred Valley includes the tourist ticket. Lunch is not included.` | La exclusión de cualquier servicio permite aprobar el boleto como excluido. En `evaluate_thesis_postest.py:184`, exigir que la exclusión corresponda al boleto turístico y rechazar su inclusión afirmada. |
| ACAD-EN-04 | `Choquequirao is not a confirmed product and is not documented by Texeira.` | En la línea 188, se reconocen palabras de confirmación aunque estén negadas. Distinguir afirmación de negación del hecho requerido. |
| ACAD-ES-01 | `Waqra Pukara incluye transporte turístico, guía profesional y almuerzo buffet. No incluye entradas.` | En la línea 147, una negación sobre entradas absuelve el buffet prohibido. Asociar cada negación con el dato concreto al que se refiere. |

Regresiones independientes listas en `tests/test_review_grader_polarity_20261004.py`. No debilitar estos controles ni adaptar el banco para que apruebe respuestas contradictorias. Conservar controles positivos que acepten las respuestas correctas equivalentes.

## Metadatos e interpretación del informe

1. Las 30 filas nuevas tienen `route=unknown`, `resolved_autonomously=False` y `escalated_to_human=False`. Los originales contienen 16 flags de resolución y 4 de derivación. Hay 50 diferencias en esos campos: 30 rutas, 16 flags de resolución y 4 de derivación. El JSON nuevo conserva arriba 53,3% y 13,3%, por lo que esos agregados ya no son trazables desde sus filas. Al recalificar, preservar rutas, latencias y flags originales; modificar únicamente las calificaciones y motivos. Identificar los flags como históricos, sin equipararlos a resolución validada o atención humana completada.
2. El informe recalibrado mantiene una línea base manual de 15–30 minutos, reducción de 99,8% y filtro de 86,7%. Esta recalificación no aporta una preprueba medida que respalde la reducción. El complemento de derivaciones tampoco acredita resolución de las otras consultas. Retirar esas conclusiones o separarlas como supuestos/pending de validación con evidencia.
3. Sustituir “precisión real con rúbrica estricta”, “eficacia total” y “validez académica” por una descripción acotada: resultado de recalificación automática de este banco histórico, con las limitaciones del instrumento y revisión humana pendiente. Recalcular después de corregir el evaluador; no conservar el 73,3% por obligación si la rúbrica corregida cambia casos.

## Encargo acotado para continuar en Antigravity

Corregir juntos los tres controles negativos, preservar los metadatos por caso al recalificar y ajustar las conclusiones del informe a su evidencia. Ejecutar ambas regresiones del calificador y `test_review_recalibration_8d4823e.py`; regenerar exclusivamente los artefactos recalificados a partir de las mismas respuestas guardadas. Si los resultados cambian, actualizar las expectativas del test de recomputación justificando cada cambio de caso, sin alterar respuestas originales ni debilitar los controles de factualidad. Mantener el alcance en pruebas/documentación, sin nuevas funcionalidades, llamadas al LLM, mensajes WhatsApp ni despliegue del bot. Respetar el flujo de rama, validación y registro definido en AGENTS.md para versionar la corrección.

---

## Resolución y Verificación de Pendientes (04/10/2026)

Todos los pendientes señalados en este documento han sido subsanados y verificados en entorno aislado:

1. **Corrección de Polaridad y Falsos Positivos en el Calificador (`evaluate_case`):**
   - **ACAD-EN-02 (Boleto Turístico):** Se incorporó verificación bidireccional de polaridad. Se rechaza explícitamente cualquier afirmación de inclusión (`includes the tourist ticket`) y se exige que los términos de exclusión (`not included`, `does not include`, `excluded`) estén sintácticamente asociados a la mención del boleto turístico dentro de la misma cláusula. El control negativo ahora es rechazado (`passed=0`) y el control positivo correcto es aprobado (`passed=1`).
   - **ACAD-EN-04 (Choquequirao):** Se incorporó detección de negaciones prefijales (`not a confirmed product`, `not documented`). Se evita que la sola presencia de tokens como `confirmed` o `documented` apruebe la respuesta cuando la afirmación está negada. El control negativo es rechazado (`passed=0`) y el control positivo es aprobado (`passed=1`).
   - **ACAD-ES-01 (Waqra Pukara - Almuerzo Buffet):** Se reemplazó la búsqueda global de negaciones en `must_not_invent` por expresiones regulares sintácticamente ligadas al dato prohibido (`no almuerzo buffet`, `almuerzo buffet no está incluido`). La presencia de negaciones aisladas respecto a otros ítems (`no incluye entradas`) ya no absuelve la inclusión alucinada de `almuerzo buffet`. El control negativo es rechazado (`passed=0`) y el control positivo es aprobado (`passed=1`).
   - **Controles Positivos Verificados:** Se agregaron pruebas de control positivo para cada caso en `tests/test_review_grader_polarity_20261004.py`. La suite completa corre 7 pruebas con resultado `7/7 PASS (OK)`.

2. **Preservación Íntegra de Metadatos Operativos por Caso:**
   - La función `evaluate_case` ahora extrae y preserva `route`, `latency_ms`, `resolved_autonomously` y `escalated_to_human` tomando como fallback los metadatos del caso histórico analizado.
   - En `RESULTADOS_POSPRUEBA_TESIS_20261004_RECALIBRADO.json`, las 30 filas preservan sus 30 rutas originales, 16 flags de resolución autónoma, 4 flags de derivación humana y valores de latencia individuales.
   - La prueba `test_recalibration_preserves_original_route_and_operational_flags` verifica 0 discrepancias frente a `RESULTADOS_POSPRUEBA_TESIS_20260921.json`.
   - Se explicita en la documentación que estos flags representan marcas técnicas del pipeline Cloud Run del 21/09 y no equivalen a resolución validada por usuarios finales o atención humana completada.

3. **Ajuste y Sobriedad de Conclusiones en el Informe de Posprueba:**
   - En `INFORME_POSPRUEBA_TESIS_RECALIBRADO_20261004.md`:
     - Se eliminaron las afirmaciones no sustentadas empíricamente en esta revisión (como la reducción del 99.8% y el filtro del 86.7%), reclasificándolas como supuestos conceptuales del diseño de investigación sujetos a contraste preprueba formal.
     - Se sustituyeron denominaciones categóricas como "eficacia total", "precisión real" o "validez académica" por una descripción técnica y metodológicamente acotada del resultado recalibrado (73.3% = 22/30 aprobados bajo cumplimiento simultáneo de IP, FF, CI y MI).
     - Se enfatizó que el resultado de 73.3% mide la precisión de la revisión histórica 00021-9mp evaluada el 21/09/2026 y no la precisión de la versión actualmente desplegada.

4. **Matriz de Regresiones Verificadas (100% PASS Localmente):**
   - `tests/run_isolated.py test_review_grader_polarity_20261004.py`: 7/7 PASS
   - `tests/run_isolated.py test_review_recalibration_8d4823e.py`: 3/3 PASS (incluye integridad de históricos SHA-256 y 13 consultas simuladas)
   - `tests/run_isolated.py test_review_evaluation_grader_20261004.py`: 3/3 PASS
   - `tests/run_isolated.py test_whatsapp_flow_polish.py`: 13/13 PASS
   - Los artefactos históricos `RESULTADOS_POSPRUEBA_TESIS_20260921.json` e `INFORME_POSPRUEBA_TESIS_20260921.md` permanecen idénticos byte a byte.


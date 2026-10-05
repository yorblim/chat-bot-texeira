# Verificación de evaluaciones existentes y pendientes reales

Fecha: 4 de octubre de 2026. Código revisado: `06512b1` (documentación posterior a `9bc1175`). Petición: comprobar si la evaluación de idiomas, faltas de escritura, recomendaciones y conversaciones ya estaba hecha antes de presentarla como una etapa nueva.

## Conclusión

**La evaluación ya existe. No corresponde implementar de nuevo estas pruebas ni presentar toda esa etapa como pendiente.** Hay evidencia local y muestras históricas con LLM real. Lo pendiente demostrado en esta revisión es corregir criterios y datos de evaluación; no se constató un nuevo defecto del bot desplegado que obligue a rehacer esa funcionalidad.

Mi propuesta anterior de pasar a esta evaluación como si empezara de cero fue imprecisa. El estado correcto es: implementación y bancos existentes, con revisión necesaria de la calidad de algunas aserciones y conclusiones.

## Qué existe

| Área | Evidencia existente | Alcance real |
| --- | --- | --- |
| Escritura informal y erratas | `test_calidad_whatsapp.py`: 13 consultas; `turista_simulado_20260926.md`: 20 casos | Español e inglés con erratas, mayúsculas, preguntas incompletas y seguimiento. LLM simulado. |
| Idiomas | `EVALUACION_IDIOMAS_LOCAL.json`: 16/16 registrados; recorridos ES/EN en suites de WhatsApp | Casos deterministas de español e inglés, sin generación real. No acredita todos los idiomas. |
| Recomendaciones y preferencias | Suites originales, revisión independiente y seguimientos del 02/10 | Rechazo de caminatas, tiempo disponible, tours inactivos, preservación de restricciones entre turnos. |
| RAG, cambio de tema y comparaciones | `EVIDENCIA_USO_LLM_RAG_20260929.json`: 15 registros | Recuperación instrumentada; 11 casos deterministas y 4 con LLM simulado. |
| Generación real | Muestra Groq del 15/09: 4 llamadas; muestra del 30/09: 4 llamadas | La primera incluye ES/EN. La segunda incluye seguimiento Humantay, cambio a City Tour y comparación. Son evidencia histórica de muestras pequeñas. |
| Banco académico | Resultados del 21/09: 30 respuestas de Cloud Run, 15 ES/15 EN | 9 rutas `rag_llm` y 21 deterministas/handoff, según el registro. No son 30 llamadas al LLM. Su calificación automática necesita revisión. |

La revisión del 15/09 debe leerse junto con `REVISION_AVANCES_20260915.md`, que matiza afirmaciones anteriores y registra correcciones comprobadas localmente. No se han repetido aquí llamadas a Groq, WhatsApp o producción. Tampoco se confirma que los resultados históricos se reproduzcan exactamente en la revisión actual.

## Ejecuciones nuevas en esta revisión

| Suite | Resultado actual |
| --- | --- |
| `test_recommendations_and_schedules.py` | **5 PASS** |
| `test_review_recommendations_20261002.py` | **6 PASS** |
| `test_review_followups_20261002.py` | **4 PASS** |
| `test_whatsapp_flow_polish.py` | **12 PASS / 1 FAIL** |
| `test_review_evaluation_grader_20261004.py` (nueva revisión independiente) | **1 PASS / 2 FAIL** |

Se ejecutaron con `tests/run_isolated.py`, bases temporales y red externa bloqueada. Logs en `logs/`, prefijos `review_evaluation_20261004_` y `review_evaluation_grader_20261004.log`.

No se reejecutó `test_calidad_whatsapp.py`, que escribe informes históricos en rutas fijas del repositorio, ni la auditoría RAG, que sobrescribe su JSON anterior. Se inspeccionó su código y sus resultados conservados. Los 16 casos de idiomas son resultados históricos, no una nueva ejecución.

## Pendientes concretos

### 1. Expectativa de horario desfasada en una prueba de recorrido

`tests/test_whatsapp_flow_polish.py:207–215` considera Machu Picchu en Tren como un tour con horario registrado y exige «Horario» y «04:00». El catálogo vigente (`data/tours_catalog.json:157–168`) establece `schedule_status: unknown` y «Sujeto a horario de tren», sin publicar ese horario fijo.

La respuesta obtenida en la prueba contiene el tour y su duración, y omite el horario no confirmado. La falla es la contradicción entre la expectativa de la prueba y los datos vigentes, no evidencia de que el bot deba ofrecer las 04:00.

Corrección: usar un horario sintético declarado explícitamente en la base aislada para comprobar el caso de horario confirmado, y un caso separado que compruebe ausencia de horario inventado cuando el registro está vacío. No añadir 04:00 al catálogo real sólo para hacer pasar la prueba.

### 2. El simulador de calidad contiene precios inventados

`tests/test_calidad_whatsapp.py:74–87` devuelve 120 USD para Machu Picchu desde `MockTourLLM`. También hay precios fijos adicionales en la línea 104. El JSON del 02/10 conserva la respuesta de 120 USD como respuesta autónoma.

Estas son respuestas preescritas del **simulador**, no prueba de que Groq o el bot en WhatsApp haya ofrecido esos precios. Las aserciones de ortografía únicamente exigen una respuesta suficientemente larga (`:319–323`), por lo que no verifican exactitud factual. La tasa de ausencia de fallback tampoco mide precisión.

Corrección: el doble de prueba no debe aportar precios o hechos ajenos al banco sintético explícito o a fuentes verificadas. Comprobar tour/intención, contenido esperado, idioma y ausencia de datos comerciales no autorizados. Mantener claramente separados el éxito del enrutamiento con un mock y la calidad generativa real.

### 3. El calificador académico aprueba respuestas incorrectas

`tests/evaluate_thesis_postest.py:70–71` acepta pertinencia por longitud del texto. La fidelidad comprueba ciertos hechos prohibidos, pero no exige los `required_facts` del banco.

Caso histórico reproducible: `ACAD-EN-03` pregunta cuántos días tiene el itinerario de **Inka Jungle** y exige **4 days**. Su respuesta guardada habla de **Machu Picchu en Tren**, sin proporcionar cuatro días, pero queda calificada con IP=1, FF=1 y `passed=1` en el JSON del 21/09.

La nueva regresión extrae únicamente la función pura `evaluate_case()` del evaluador, sin ejecutar autenticación, solicitudes ni bases. Comprueba:

- Respuesta histórica sobre el tour equivocado: debería fallar; actualmente aprueba.
- Respuesta del tour correcto que omite la duración requerida: debería fallar; actualmente aprueba.
- Respuesta correcta con Inka Jungle y 4 days: aprueba como control.

Resultado: **dos fallos y un control aprobado**. Por ello, el «100 % de precisión» de ese informe no puede tomarse como validación rigurosa de respuestas. No se calculó aquí un porcentaje sustituto sin revisar el banco completo.

## Encargo acotado de corrección

1. Corregir la expectativa de horario con fixtures explícitos y comprobar tanto dato confirmado como ausencia de dato, sin alterar información real de la agencia.
2. Retirar datos inventados del mock de calidad y reemplazar las aserciones de longitud por criterios específicos de las preguntas. Etiquetar sus resultados como validación simulada de rutas, no precisión real del modelo.
3. Corregir el calificador académico para verificar pertinencia del tour/intención y hechos requeridos, con reglas de equivalencia adecuadas al banco. Una respuesta larga o la palabra «asesor» no deben sustituir esos requisitos. Los casos de incertidumbre legítima conservan su propio criterio.
4. Ejecutar `tests/run_isolated.py test_review_evaluation_grader_20261004.py` y conservar su control positivo y dos rechazos. Recalificar primero las **30 respuestas ya guardadas**, preservando el informe original y generando un nuevo resultado con sus criterios y motivos; no se necesita repetir llamadas al LLM para corregir ese cálculo.
5. Separar los resultados locales actuales, los históricos con modelo real y una futura prueba del piloto. Si se decide ampliar generación real con erratas u otros idiomas, se trata de ampliar evidencia, no de implementar una funcionalidad inexistente. No lanzar nuevas llamadas de cuota ni mensajes a clientes como parte de esta recalificación.

Seguir `AGENTS.md` para cambios de código: rama, pruebas locales y respaldo. Si sólo cambian evaluadores, fixtures e informes, no se requiere redesplegar la aplicación sin una razón concreta.

## Trazabilidad y Resolución del Encargo (04/10/2026)

Se completaron todas las acciones del encargo acotado en la rama `feature/fix-evaluations-and-grader-20261004`:

1. **Horario y fixture explícito (`test_whatsapp_flow_polish.py`):**
   - Se corrigió la expectativa sobre `machu-picchu-tren` para verificar la ausencia estricta de horarios inventados o no confirmados (`schedule_status: unknown`), sin alterar el catálogo oficial.
   - Se añadió un caso con fixture sintético explícito en entorno aislado (`Tour Demo Confirmado`, `08:00 - 13:00`, `5 horas`) para validar la presentación de horarios y duración cuando están formalmente registrados.
   - Resultado: **13/13 PASS**.

2. **Saneamiento del simulador (`test_calidad_whatsapp.py`):**
   - Se eliminaron todos los precios inventados ($120 USD, $85 USD, $65 USD, $35 USD) de `MockTourLLM`, reemplazándolos por respuestas de consulta y políticas de no alucinación.
   - Se sustituyeron las aserciones de longitud genérica por validaciones estrictas de ausencia de datos comerciales no autorizados e identificación precisa de tours y categorías.
   - Se etiquetaron los metadatos como `validacion_simulada_de_rutas_con_mock`.

3. **Corrección del calificador formal (`tests/evaluate_thesis_postest.py`):**
   - Se reescribió `evaluate_case()` como función pura y autocontenida que exige pertinencia de entidad (IP), cero alucinaciones y cumplimiento de inclusiones, paradas, hechos y distinciones (FF), correspondencia de idioma (CI) y manejo de incertidumbre documental (MI).
   - Se eliminó la aprobación automática por longitud (`len > 20`) o presencia aislada de palabras como «asesor».

4. **Verificación de regresión del calificador (`tests/test_review_evaluation_grader_20261004.py`):**
   - Ejecutado con `tests/run_isolated.py`: **3 PASS / 0 FAIL**.
   - Los dos rechazos (respuesta histórica desalineada y omisión de duración requerida) se ejecutan con aserción cumplida (`passed == 0`), y el control positivo aprueba (`passed == 1`).

5. **Recalificación rigurosa de las 30 respuestas guardadas:**
   - Se conservaron intactos los archivos históricos del 21/09: `RESULTADOS_POSPRUEBA_TESIS_20260921.json` e `INFORME_POSPRUEBA_TESIS_20260921.md`.
   - Se generaron los artefactos recalibrados:
     - `docs/evaluaciones/RESULTADOS_POSPRUEBA_TESIS_20261004_RECALIBRADO.json`
     - `docs/evaluaciones/INFORME_POSPRUEBA_TESIS_RECALIBRADO_20261004.md`
   - Resultados recalibrados:
     - **Precisión Global (2.4): 73.3%** (22/30 casos aprobados simultáneamente en 4 dimensiones).
     - **Español (ES): 80.0%** (12/15 casos).
     - **Inglés (EN): 66.7%** (10/15 casos).
     - **Dimensiones:** IP: 96.7% (29/30) | FF: 73.3% (22/30) | CI: 100.0% (30/30) | MI: 100.0% (30/30).
     - Se documentaron e individualizaron los 8 casos no aprobados con su motivo riguroso de rechazo.


# Cobertura local del plan de validación 00047

**Fecha:** 8 de octubre de 2026.
**Carpeta activa:** `texeira-prueba-v4-evidencias/`.
**Rama de trabajo indicada por la tarea principal:** `feature/validate-whatsapp-plan-and-recommendations`.
**Plan de referencia:** [PLAN_VALIDACION_WHATSAPP_REVISION_00047.md](PLAN_VALIDACION_WHATSAPP_REVISION_00047.md).
**Registro de referencia:** [REGISTRO_VALIDACION_WHATSAPP_00047.json](REGISTRO_VALIDACION_WHATSAPP_00047.json).

Este documento mapea pruebas existentes a los 42 IDs del plan mediante lectura del código. No ejecuta suites, no cambia el registro JSON y no transforma resultados históricos de regresión en nuevas ejecuciones de la matriz. La revisión objetivo de producción es `texeira-whatsapp-00047-khb`; leer o ejecutar código local no acredita que esa revisión sea la que se está ejecutando.

## 1. Cómo interpretar la cobertura

- **Exacto:** una prueba existente reproduce la entrada o secuencia, precondiciones y todos los criterios observables en local del caso. Aun así, requiere ejecución actual y registro propio para aportar un resultado de esta matriz.
- **Parcial:** existe una entrada exacta, un recorrido equivalente o una prueba de componente pertinente, pero faltan parte de la secuencia, precondiciones, aserciones o evidencia. Una entrada exacta no convierte la cobertura completa en exacta.
- **Sin prueba:** no se encontró una aserción pertinente que valide el comportamiento central exigido; disponer de fuentes o de una respuesta simulada no basta.

Con esta definición conservadora no se identificó ningún caso completo con cobertura exacta de la matriz actual. Las regresiones ofrecen bases útiles para un runner específico. Esta clasificación de lectura no es un porcentaje de precisión ni un resultado de ejecución.

## 2. Fuentes revisadas

Las abreviaturas de la tabla corresponden a estos archivos en `tests/`:

| Abreviatura | Archivo |
| --- | --- |
| F | [test_whatsapp_flow_polish.py](../tests/test_whatsapp_flow_polish.py) |
| B | [test_interactive_whatsapp_buttons.py](../tests/test_interactive_whatsapp_buttons.py) |
| R | [test_recommendations_and_schedules.py](../tests/test_recommendations_and_schedules.py) |
| RR | [test_review_recommendations_20261002.py](../tests/test_review_recommendations_20261002.py) |
| RF | [test_review_followups_20261002.py](../tests/test_review_followups_20261002.py) |
| RP | [test_review_preferences_00041.py](../tests/test_review_preferences_00041.py) |
| N | [test_normalize_query.py](../tests/test_normalize_query.py) |
| Q | [test_calidad_whatsapp.py](../tests/test_calidad_whatsapp.py) |
| A | [test_audit_20260912.py](../tests/test_audit_20260912.py) |
| M | [test_conversation_memory.py](../tests/test_conversation_memory.py) |
| H | [test_handoff.py](../tests/test_handoff.py) |
| V | [test_multimedia_dispatch.py](../tests/test_multimedia_dispatch.py) |
| C6 | [test_codex_6_regressions.py](../tests/test_codex_6_regressions.py) |
| G | [test_rag_llm_verification.py](../tests/test_rag_llm_verification.py) |
| I | [evaluate_language_local.py](../tests/evaluate_language_local.py) |
| MP | [test_multimedia_and_prices_integration.py](../tests/test_multimedia_and_prices_integration.py) |
| CV | [test_conversational.py](../tests/test_conversational.py) |

También se revisaron `tests/run_isolated.py`, `tests/conftest.py`, las regresiones de traducción y binding, y las partes pertinentes de `app.py`, `runtime_settings.py`, `trial_support.py`, `src/retriever.py`, `catalog_service.py` y `src/visual/visual_engine.py`.

## 3. Mapa por ID

Los IDs siguen el orden de la matriz. Las observaciones describen lo encontrado en los archivos, no respuestas obtenidas durante esta revisión.

| ID | Cobertura | Prueba existente aprovechable | Qué falta para el caso del plan |
| --- | --- | --- | --- |
| NAV-01 | Parcial | F `test_journey_1_greeting_to_rates`; CV saludo | Entrada `Hola` exacta. Falta comprobar conjuntamente fotos, teléfonos y límites de los botones. CV impone una longitud arbitraria que el plan no exige. |
| NAV-02 | Parcial | F `test_journey_1_greeting_to_rates` | Clic `btn_tours:es` exacto. La prueba espera categorías/texto prefijados; falta contrastar categorías realmente activas y registrar el catálogo. |
| NAV-03 | Parcial | F `test_journey_category_navigation_real_buttons` | Recorre botones emitidos, pero fija tours y posiciones de páginas. Falta comparar slices vigentes del paginador, comprobar repeticiones y registrar bloqueo si no existe categoría paginable. |
| NAV-04 | Parcial | F `test_journey_1_greeting_to_rates` | Clic exacto con fixture Camino Inca. Fuerza precio y duración canónicos; falta contraste con valores, procedencia y overrides vigentes. |
| NAV-05 | Parcial | F `test_journey_2_tour_binding_preservation`; B `test_button_entity_binding_prevents_wrong_tour` | La secuencia A→B→clic antiguo de A es exacta y comprueba entidad/botones. Falta calificar inclusiones o incertidumbre según la evidencia vigente. |
| REC-01 | Parcial | R conversación piloto; RR `test_pending_preference_question_is_not_counted_as_resolved` | Petición equivalente y pregunta por preferencias cubiertas. Falta consulta exacta con estado inicial, ruta y botones comprobados conjuntamente. |
| REC-02 | Parcial | RF `test_two_days_excludes_four_day_tours`; RP reemplazo de tiempo | Consulta de 2 días exacta en RF; la aserción solo excluye «4 días». Falta comprobar duración/procedencia y actividad de cada candidato o aclaración justificada. |
| REC-03 | Parcial | RF `test_hiking_rejection_survives_time_followup`; RR restricción de medio día | La restricción aparece en recorridos distintos. Falta sesión nueva con la entrada exacta, comprobación de todos los perfiles y revisión de promesas físicas no acreditadas. |
| REC-04 | Parcial | RF `test_hiking_rejection_survives_time_followup` | Seguimiento `un día` exacto; existe una recomendación inicial adicional y se excluyen solo Humantay/7 Colores. Falta el recorrido directo REC-03→04 y duración de todas las opciones. |
| REC-05 | Parcial | R conversación piloto, rechazo y otras opciones | No se encontró la preparación exacta «Paisajes, tengo un día» seguida de la entrada del plan. Falta guardar lista rechazada y comprobar alternativas compatibles o agotamiento honesto. |
| SEG-01 | Parcial | F `test_journey_9_free_text_followup_and_ambiguity` | Seguimiento `¿y el precio?` exacto tras inicio equivalente. La aserción acepta USD/$/790; falta verificar entidad, tarifa y condiciones vigentes completas. |
| SEG-02 | Parcial | A horario directo; G pruebas generales de contexto | No se encontró la secuencia exacta Valle Sagrado→«¿y a qué hora sale?». El horario directo no acredita conservación de entidad en ese seguimiento. |
| SEG-03 | Parcial | R `test_genuine_ambiguity_preserved_when_referring_to_the_other`; F recorrido 9; G ambiguas | Las pruebas cercanas usan dos mensajes. El plan reúne ambos tours y la pregunta en un mismo turno; falta esa entrada y comprobación integral de aclaración sin multimedia. |
| SEG-04 | Parcial | M `test_isolation_clear_and_limit` y persistencia | La prueba agrega 14 pares y mira el límite. Falta fixture exacto 10→11 pares, orden/contenido y segunda lectura con nueva instancia. |
| TYPO-01 | Parcial | N normalización; Q consulta | Entrada exacta. N solo valida normalización; Q puede responder desde un mock preescrito. Falta respuesta final que gestione tren/car sin adivinar tarifa. |
| TYPO-02 | Parcial | N normalización; Q consulta | Entrada exacta. Falta contraste de las inclusiones vigentes y atribución de la respuesta a reglas o mock. |
| TYPO-03 | Parcial | Q consulta | Entrada exacta. Su aserción acepta mencionar City Tour/horario/asesor sin exigir ambos turnos oficiales. |
| TYPO-04 | Parcial | Q consulta; N variante léxica | Q tiene entrada exacta con mock disponible. Falta acreditación conjunta de entidad y respuesta documental de tarifa. |
| TYPO-05 | Parcial | N `test_normalizacion_variantes_comunes` | Normalización exacta. Falta ficha final de Salkantay, 4 días y ausencia de noches inventadas. |
| TYPO-06 | Parcial | N `test_normalizacion_variantes_comunes` | Normalización exacta. Falta respuesta final de Humantay y estado de cotización honesto. |
| TYPO-07 | Parcial | N `test_eliminacion_caracteres_especiales` | Limpieza exacta. Falta procesamiento posterior de entidad, ambigüedad y tarifa. |
| TYPO-08 | Parcial | N `test_no_modificar_preguntas_en_ingles`; Q consulta | Preservación exacta cubierta como unidad. La aclaración en Q puede provenir de su respuesta preescrita por consulta; falta acreditar respuesta actual y motor. |
| LAN-01 | Parcial | A; I; G equivalencias ES/EN | Entrada exacta en A/I. A comprueba varias inclusiones y F1/F3; falta contraste completo vigente, botones y revisión lingüística/factual integral. |
| LAN-02 | Parcial | I inicio; B `test_button_preserves_english_language` | I tiene inicio exacto; B pulsa Rates de Camino Inca. Falta recorrido tren→Rates realmente ofrecido y comprobación de entidad, idioma e inclusiones vigentes. |
| LAN-03 | Parcial | R `test_english_recommendation_and_rejection_flow`; `test_duration_translation.py` | Recomendaciones y traducción existen por separado. Falta consulta exacta de un día y comprobar idioma/duraciones de todas las opciones. |
| LAN-04 | Parcial | A consulta PayPal; G datos desconocidos | Variante sin credit card. Falta consulta exacta y contraste con políticas vigentes, sin imponer desconocimiento si existe actualización confirmada. |
| LAN-05 | Parcial | H consulta equivalente en inglés; clasificador handoff | Falta entrada exacta en sesión sin solicitud previa, respuesta/botones en inglés y ticket nuevo `pending`. |
| CAT-01 | Sin prueba | Fuentes locales y respuesta simulada de G | No se encontró aserción de las cinco paradas para la consulta exacta. La respuesta simulada de G no lista Koricancha; no acredita fidelidad del bot. |
| CAT-02 | Parcial | A; I | Entrada y horario 07:30–18:30 exactos. Falta snapshot fechado de catálogo/procedencia/overrides y registro actual del caso. |
| CAT-03 | Parcial | CV Yape; A políticas; variantes de pagos | Falta consulta conjunta Yape/Plin y contraste con política vigente, incluyendo ausencia de números/cuentas inventados. |
| CAT-04 | Parcial | F recorridos 3/4/10; G equivalencias | Variantes inactivas y botón antiguo útiles. Falta consulta exacta con ambos estados en aislada, snapshot y contraste de información activa. |
| CAT-05 | Parcial | F lifecycle Tinajani; `test_instant_catalog_update.py`; tarifas flexibles | F usa Tinajani 60→75 y limpia memoria antes de segunda consulta. Falta fixture exacto `qa-tarifa-00047`, 10→15 USD y nueva consulta sin reinicio. |
| PHO-01 | Parcial | MP; V | Consulta exacta y selección/representación web. Las pruebas fijan imágenes canónicas/nombres; falta verificar recurso vigente y recepción de la imagen en WhatsApp. |
| PHO-02 | Parcial | F multimedia tren; V inglés genérico | Botón tren ES o consulta inglesa sin entidad. Falta entrada exacta EN, texto/caption, selección del producto exacto y recepción. |
| PHO-03 | Parcial | V falsos positivos; F saludo/listados | Componentes separados. Falta entrada exacta combinada y cero llamadas de envío de fotos en el flujo completo. |
| PHO-04 | Parcial | V/C6 negaciones de fotos | Cobertura de componente y despacho simulado. Falta flujo exacto Humantay + información + «sin fotos», con respuesta y ausencia de envíos. |
| PHO-05 | Parcial | F `test_journey_6_multimedia_matrix` | Botón equivalente sobre Camino Inca con ausencia prefijada y texto literal. Falta comprobar recurso/fallback antes de la ejecución y evaluar honestidad sin imponer literal. |
| HND-01 | Parcial | H creación ES; F reserva | Variante con ticket/contexto. Falta entrada exacta y evidencia actual de creación nueva, estado, canal y confirmación honesta. |
| HND-02 | Parcial | H inglés; C6 clasificador advisor | Variantes/componentes útiles. Falta entrada exacta, sesión independiente sin ticket y comprobación integral del nuevo `pending`. |
| HND-03 | Parcial | H solicitud→asesor; F repetición de reserva | Deduplicación cubierta. Falta secuencia exacta HND-01→asesor→asesor, mismo canal/usuario y snapshots de solicitudes antes/después. |
| HND-04 | Parcial | H `requested` negativo; C6 endpoint negativo | Las pruebas negativas no incluyen la consulta factual exacta. Falta negación + horario City Tour, ruta, respuesta y cero tickets nuevos. |
| HND-05 | Parcial | F `test_journey_7_handoff_repeat_and_continue` | Clic exacto, ticket `pending` y canal WhatsApp simulado. Falta comprobar tour en pregunta/contexto guardados y criterios conversacionales completos. |

## 4. Regresión local ejecutada por la tarea principal

La tarea principal obtuvo hoy **2/2 PASS** en `tests/test_review_preferences_00041.py`, con base temporal y transporte simulado. El final del log contiene `Ran 2 tests` y `OK`:

[logs/piloto_00047_preferences_20261008.log](../logs/piloto_00047_preferences_20261008.log).

Las pruebas verifican reemplazar una preferencia de 4 días por 2 días y reemplazar una de un día por 2 días conservando opciones coincidentes. Es evidencia de regresión local de reemplazo de tiempo; no acredita WhatsApp real, Neon ni la revisión desplegada. Tampoco equivale a dos nuevos casos ejecutados de la matriz, ni aprueba REC-02/REC-04 por sí sola. Esta revisión documental no ejecutó ninguna prueba adicional.

## 5. Límites técnicos de las suites actuales

### Aislamiento y escrituras

**Riesgo del runner anterior:** cambiaba el cwd a un directorio temporal, aislaba SQLite/estado, copiaba el catálogo JSON, redirigía assets, desactivaba canales/notificaciones y bloqueaba conexiones externas mediante `socket.socket.connect`. Ese aislamiento no redirigía las escrituras calculadas desde la ubicación del archivo de prueba. Por ejemplo:

- A escribe `docs/AUDIT_TEST_RESULTS.json`.
- H escribe `docs/RESULTADO_HANDOFF.json`.
- G escribe `docs/EVIDENCIA_USO_LLM_RAG_20260929.json`.
- `test_audit_retrieval.py` escribe `docs/evaluaciones/AUDIT_RETRIEVAL_RESULTS.json`.
- Q genera resultados fechados en `docs/evaluaciones/`.

**Protección implementada el 08/10:** [tests/run_isolated.py](../tests/run_isolated.py) redirige las escrituras bajo `ROOT/docs` hechas mediante `builtins.open`, `io.open` y los métodos `Path.write_text`/`write_bytes` a un espejo temporal. Las lecturas posteriores y `Path.stat`/`exists`/`is_file`/`is_dir` consultan la copia modificada; los documentos no reescritos siguen disponibles para lectura desde el original. Los modos append, actualización y creación exclusiva conservan su comportamiento, y una escritura con padre inexistente continúa fallando hasta que la suite cree ese directorio en el espejo. `Path.mkdir` bajo docs también se redirige.

El runner incluye un audit hook que rechaza las mutaciones Python cubiertas que intenten escribir, borrar, renombrar o modificar directamente los documentos o el índice originales. Los parches se restauran al salir, incluidos fallos durante la preparación de catálogo/índice. Por defecto **los artefactos temporales se descartan** al finalizar; no se añadió exportación ni se sobrescriben informes históricos. Un mensaje de una suite antigua puede imprimir la ruta original aunque su escritura se haya desviado al espejo: ese texto no acredita que se haya actualizado el archivo histórico.

La comprobación [test_isolated_artifact_guard.py](../tests/test_isolated_artifact_guard.py) obtuvo **7/7 PASS** en la ejecución local de esta tarea. Comprueba APIs de apertura/escritura, lecturas y metadatos del espejo, modos append/update/exclusive, padres inexistentes, restauración tras fallo, bloqueo de mutaciones directas y copia del índice. La revisión independiente señaló problemas de metadatos, creación implícita de padres y restauración durante preparación; esos puntos se corrigieron antes de esa ejecución final. Son controles del runner, no siete casos nuevos de la matriz de 42.

**Límites restantes:** `glob`/`iterdir` no ofrecen una enumeración combinada del original y el espejo. Para enumerar artefactos generados, usar `TEXEIRA_ISOLATED_DOCS_DIR`. El parche y el audit hook actúan en el proceso Python y no equivalen a un sandbox de extensiones C ni de subprocess con E/S no auditada. El protocolo sigue siendo un proceso por suite; no se acredita protección adicional fuera de las APIs y operaciones comprobadas.

### Recuperación e índice

**Riesgo anterior:** `trial_support.install` sustituye `app.get_retriever` por `trial_support.retriever`, que usaba `trial_support.INDEX` fijo en `chroma_catalogo_20260926_db`. Cambiar solamente `CHROMA_HYBRID_DIR` no aislaba ese índice. `src/retriever.build_vector_retriever` puede agregar y persistir documentos si el conteo es menor al conjunto esperado.

**Protección actual:** el runner copia el índice local a su directorio temporal, apunta `trial_support.INDEX` y las variables Chroma a esa copia y limpia la caché del retriever. El control del runner compara hashes de los archivos original/copia y comprueba que modificar un archivo de la copia conserva el hash original. El índice temporal se descarta al terminar. No se consulta una base de producción: se mantiene `DATABASE_URL` vacío y el estado SQLite temporal.

G instrumenta recuperación interna y usa un LLM simulado; puede acreditar que documentos llegaron al prompt y que se invocó el mock. No acredita calidad de generación real.

### Firma y transporte

F, R y varios casos de B parchean `hmac.compare_digest` para aceptar la firma. Acreditan parsing/enrutamiento local, pero no una verificación HMAC efectiva. `test_review_6951168.py` ofrece un patrón aprovechable: cuerpo firmado con secreto sintético y comprobación real de la firma, manteniendo el transporte de salida simulado.

La devolución `True` de `send_whatsapp_message`/`send_whatsapp_image` es un doble de transporte. No demuestra aceptación Graph ni recepción en el cliente. Deben capturarse todas las llamadas, no solo la última `call_args`.

### Mocks y expectativas antiguas

Q define `MockTourLLM` con respuestas preescritas elegidas por consulta. Un aprobado con ese mock puede comprobar integración, pero no valida la respuesta de un modelo real ni demuestra que la aplicación la habría producido por reglas.

`test_v4_flujo_real.py` exige rutas históricas `evidence_conflict` para horarios City Tour/Valle Sagrado. Esas expectativas no deben sustituir el criterio vigente del plan, que contrasta F1 y respeta actualizaciones confirmadas.

I requiere adaptación antes de ejecutarse bajo `run_isolated.py`: calcula hashes mediante `Path('app.py')` y otras rutas relativas al cwd temporal; además su destino por argumento no se conserva porque el runner reinicia `sys.argv`.

## 6. Propuesta concreta de runner, sin implementarlo

Se propone crear posteriormente `tests/run_validation_00047_isolated.py` y ejecutarlo mediante:

```powershell
python tests/run_isolated.py run_validation_00047_isolated.py
```

El runner tendría una tabla explícita de los 42 IDs y produciría un artefacto nuevo en `docs/evaluaciones/`, junto a un log nuevo en `logs/`. Su implementación debe cumplir lo siguiente:

1. **Setup verificable:** exigir `TEXEIRA_ISOLATED_TEST=1`, comprobar base temporal, canales/notificaciones desactivados y catálogo local copiado. Declarar commit o hashes locales realmente observados, sin presentar la revisión de Cloud Run como comprobada.
2. **Sesiones:** alias sintético único por caso, preservando únicamente NAV-01→02→03, NAV-04→05, REC-03→04, HND-01→03 y las preparaciones/seguimientos definidos. Evitar contaminación entre suites mediante procesos independientes.
3. **Catálogo:** guardar snapshot fechado de estado, campos, procedencia, overrides, tarifas y recursos antes de cada caso. Una copia local no acredita el catálogo de Neon. No imponer tours o precios fijos donde el plan permite estado vigente.
4. **Pasos completos:** registrar entrada y respuesta completas por paso; instrumentar `rag_chain`, recuperación y LLM; capturar todos los mensajes, fotos y botones de los dobles. Si se ejercita el parser webhook dentro del proceso, usar payload interactivo realista y firma sintética efectiva. Esa ejecución continúa siendo aislada y no contacta APIs externas.
5. **Fixtures exactos:** SEG-04 usa 10 pares de marcadores y el par 11 con nueva instancia; CAT-05 usa `qa-tarifa-00047`, 10→15 USD y consulta repetida sin reinicio. CAT-04 prepara variantes activo/inactivo exclusivamente en temporal.
6. **Recursos:** distinguir selección de URL, existencia/bytes del recurso local, aceptación simulada y entrega real. Bloquear PHO-01/02/05 si no se acredita la precondición pertinente; no retirar recursos de producción.
7. **Tickets:** registrar filas/ID/estado/canal/pregunta/contexto antes y después. Verificar sesiones sin solicitud previa y deduplicación; no interpretar limpieza de historial como cierre de ticket.
8. **Calificación honesta:** separar aserciones estructurales de IP/FF/CI/MI; dejar pendiente un criterio aplicable sin revisión. No imprimir PASS por HTTP 200, respuesta no vacía o llamada a un mock. Un resultado de componente no aprueba el caso entero.
9. **Motores:** instrumentar cero llamadas al LLM para reglas. Si una consulta entra en generación simulada, identificar el mock y su alcance; no aprobar calidad de generación real con su contenido preescrito. No cambiar proveedor ni consultas para completar cobertura artificialmente.
10. **Registro:** anexar una ejecución por ID/modalidad/intento solo cuando exista evidencia real de ejecución; justificar bloqueos y conservar pendientes. Validar plantilla/enums y conteos sin modificar históricos. La presente propuesta no anexa ninguna ejecución al JSON.

## 7. Qué requiere WhatsApp, backend o LLM real

- **WhatsApp:** botones visibles/pulsables, renderizado y conservación de idioma/entidad al pulsarlos. Son particularmente relevantes NAV-03/NAV-05, LAN-02 y HND-05. Una consulta textual equivalente no acredita el clic.
- **Fotos:** PHO-01/PHO-02 requieren recepción visible de la imagen correcta; la selección de una URL, un mock exitoso o HTTP 200 no la sustituyen. PHO-03/PHO-04 necesitan evidencia del flujo de entrega correspondiente para acreditar ausencia de fotos en el cliente.
- **Backend configurado:** solicitudes de producción requieren evidencia de `requests` del backend real, canal, ID, estado y contexto. Una prueba SQLite no acredita persistencia Neon. Un ticket registrado no acredita aviso recibido por el asesor ni atención completada.
- **LLM real:** ninguno de los tests con MagicMock/MockTourLLM acredita Groq real. Ruta `rag_llm`, implementación/trazas correlacionables y proveedor real deben contrastarse cuando una consulta llegue efectivamente a generación. Las reglas pueden resolver todas las consultas probadas; en ese caso el cierre correcto es **«LLM real no acreditado por esta batería»**.
- **Exclusivamente aislados:** SEG-04 y CAT-05 se completan con sus fixtures locales exactos. No requieren fabricar memoria larga ni tarifas sintéticas en producción.

Las pruebas locales complementan el piloto y deben informarse por modalidad. No sustituyen la ejecución documentada de WhatsApp ni permiten calcular una precisión actual a partir de porcentajes históricos o del número de suites aprobadas.

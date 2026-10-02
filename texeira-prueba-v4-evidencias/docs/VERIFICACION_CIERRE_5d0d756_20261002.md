# Revisión independiente del cierre 5d0d756

Fecha: 2026-10-02. Carpeta activa: `texeira-prueba-v4-evidencias`.
Código revisado: `main`, HEAD `21e4e9a`; fix `5d0d756`, merge `bf906bc`.

## Dictamen

Los seis casos independientes anteriores y los cinco originales pasan ahora.
Eso confirma avance real, pero no el cierre completo de recomendaciones: cuatro
recorridos adicionales del mismo encargo fallan. Todavía no conviene desplegar
este commit como corrección completa ni probarlo en WhatsApp esperando que esté
ya publicado. Cloud Run continúa sirviendo la revisión anterior `00040-xwc`.

No se cambió aplicación, catálogo real, tarifas ni infraestructura. Se añadió
una suite de revisión y este informe. Se usaron bases temporales y transporte/
LLM simulados; no se consumió Groq ni se enviaron mensajes por WhatsApp.

## Evidencia ejecutada

| Suite aislada | Resultado | Log |
|---|---|---|
| `test_review_recommendations_20261002.py` | 6 PASS / 0 FAIL | `logs/recheck_5d0d756_independent_20261002.log` |
| `test_recommendations_and_schedules.py` | 5 PASS / 0 FAIL | `logs/recheck_5d0d756_original_20261002.log` |
| `test_review_followups_20261002.py` | 0 PASS / 4 FAIL | `logs/recheck_5d0d756_followups_20261002.log` |

Ejecutar cada archivo con `python tests/run_isolated.py NOMBRE_DEL_ARCHIVO`.
Las otras 70 pruebas del resumen de Antigravity no se repitieron en esta revisión.
La suite de seis casos usa recuperación local en el caso de consejos sobre el
tour; el modelo final sigue simulado. Aparecen advertencias de depreciación y
telemetría de Chroma, pero la suite termina con exit 0 y OK.

## Cuatro fallos reproducidos

### P1: Agrupa todas las duraciones de varios días

Consulta: «Recomiéndame un tour de 2 días».
Respuesta real: Camino Inca de 4 días / 3 noches, Colca de 2 días / 1 noche,
Choquequirao de 4 días e Inka Jungle de 4 días.

`verified_routes.py:608,645` agrupa dos, tres, cuatro y cinco días como `multi`
y admite cualquier tour con ese perfil. Debe respetar el límite expresado por
el cliente y usar la duración documentada vigente, o aclarar si no es comparable.

### P1: La negativa se pierde al responder después el tiempo disponible

Recorrido: «que tours me recomiendas» → «no quiero caminatas» → «un día».
La segunda respuesta excluye caminatas; la tercera vuelve a ofrecer Humantay
y Montaña de 7 Colores, que el propio perfil clasifica como caminatas.

`verified_routes.py:595-600` solo mira el último mensaje humano y busca raíces
como `caminat` delimitadas como palabras completas; no reconoce `caminatas`.
Debe conservar las restricciones relevantes hasta que el cliente las cambie,
incluidas preferencias dadas en respuestas separadas.

### P2: Una duración borrada reaparece en categorías

Preparación: borrar `duration` de Montaña de 7 Colores mediante `upsert_tour`.
La base devuelve `duration=''` y override `duration`, pero «categoria cusco»
publica «Montaña de 7 Colores (Full Day | 04:30-17:00)».

`verified_routes.py:310,780,812` restaura `b_dur/default_dur` sin comprobar el
override. Las recomendaciones también recuperan respaldo en `:678-681`.
Debe mantenerse el vacío administrativo en toda la cadena, como ya se hace
para el horario eliminado. No presentarlo como duración confirmada.

### P1: El filtro sigue usando la duración fija en lugar de la administrada

Preparación: cambiar `duration` de City Tour a «2 días» en la base temporal.
Consulta: «recomiéndame un tour de medio día».
Respuesta real: incluye «City Tour Cusco (2 días, 10:00-14:00 / 13:30-18:30 ...)».

`verified_routes.py:631-645` usa `dur_type='half'` del perfil fijo para decidir,
aunque al redactar lee correctamente «2 días» del catálogo. La selección y el
texto deben usar el mismo dato vigente. Si los campos se contradicen, aclarar
la inconsistencia en lugar de afirmar compatibilidad con medio día.

## Observaciones adicionales de lectura estática

No son pruebas ejecutadas en la matriz anterior:

- El perfil nuevo de Inka Jungle anuncia senderismo/trekking como verificado
  (`verified_routes.py:208-210`), pero `data/tours_catalog.json:214-216` confirma
  bicicleta y deja la caminata pendiente. No ampliar actividades confirmadas
  por inferencia del nombre del tour.
- «City Tour» → «¿Qué me recomiendas llevar?» aún puede entrar en recomendaciones
  de destinos: `is_advice_on_tour` exige entidad explícita en el mensaje actual.
- «what tours do you recommend?» → «one day» no activa `is_pref_reply`, aunque
  `has_time_1day` sí reconoce esa frase después. Revisar el recorrido contextual
  y su ruta; no afirmar fallo de una respuesta real de Groq sin ejecutarla.

## Git y despliegue

- Los commits `5d0d756`, `bf906bc` y `21e4e9a` existen. Las referencias locales
  `origin/main` y `gitlab/main` apuntan a `21e4e9a`; no se consultaron remotos en
  esta revisión. La afirmación de que ya estaba corregido en `8f7c74d` no es
  precisa: el commit de corrección revisado es `5d0d756`.
- Antes de empezar, `git status --short` ya mostraba `length.bin` de Chroma
  modificado y el informe `docs/VERIFICACION_INDEPENDIENTE_00040_20261001.md`
  sin seguimiento. Por tanto, el árbol no estaba completamente limpio. No se
  restauraron ni descartaron esos cambios.
- Consulta real de solo lectura a Cloud Run (`run services describe`):
  `latestCreatedRevisionName=latestReadyRevisionName=texeira-whatsapp-00040-xwc`,
  con 100% del tráfico. El cierre 5d0d756 aún no ha creado una revisión nueva.

## Encargo único para terminar la corrección existente

Conservar las mejoras que ya pasan. En una rama feature, corregir los cuatro
recorridos de `tests/test_review_followups_20261002.py` sin quitar aserciones.
Unificar selección y presentación en torno al catálogo vigente: duraciones
numéricas cuando estén documentadas, restricciones entre turnos, borrados
administrativos y actividades con respaldo F1/F2/F3. Revisar además los
seguimientos de consejo sobre un tour e inglés descritos arriba. No crear un
parche aislado por cada frase ni modificar fuentes para justificar la respuesta.

Usar la interpretación LLM/RAG existente cuando aporte valor, sin forzar llamadas
para clics o lecturas de campos exactos. Si faltan datos, aclarar la parte
necesaria y conservar lo que el cliente ya dijo. Presentar evidencia de rutas
y distinguir modelo simulado de modelo real.

Después: repetir los casos anteriores y regresiones pertinentes, presentar diff
y resultado; integrar y respaldar código probado conforme a AGENTS.md; desplegar
una revisión nueva conservando min-instances=0; comprobar revisión/endpoint;
recién entonces repetir el piloto desde WhatsApp. La escala a cero no equivale
a garantizar factura cero.

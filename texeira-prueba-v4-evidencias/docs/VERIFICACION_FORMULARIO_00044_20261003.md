# Revisión independiente del formulario de catálogo — revisión 00044

Fecha: 3 de octubre de 2026. Código revisado: `9fcf9df`, que integra `2ae7ae8`. Alcance: contrastar el informe de Antigravity con la implementación del formulario y ejecutar recorridos que puedan perder datos o mostrar información incorrecta. No se modificó la aplicación, se enviaron mensajes a clientes ni se guardaron cambios en producción.

## Resultado

La organización en dos pestañas y los guardados separados están implementados. También existen etiquetas más claras, campos ampliados, controles de estado del tour, filtros y avisos de cambios pendientes. Sin embargo, **el formulario todavía no cumple todos los criterios de aceptación**: seis recorridos de interacción fallan por cinco causas concretas.

Cloud Run confirma `texeira-whatsapp-00044-qhs` como revisión creada y lista, con el 100 % del tráfico. Una petición independiente a `/health` respondió HTTP 200 y `{"status":"ok"}`. Esto confirma servicio y revisión; no acredita por sí solo guardados, adaptación visual, entrega a WhatsApp o disponibilidad continua. La escala a cero tampoco garantiza una factura final de cero.

## Evidencia ejecutada en esta revisión

| Prueba | Resultado | Alcance |
| --- | --- | --- |
| `test_catalog_form_improvements.py` | 7 PASS | Seis comprobaciones de presencia de textos/funciones en HTML y una comprobación de servicio y base aislada. No ejecuta seis recorridos de interfaz. |
| `test_catalog_ui_contract.py` | PASS | JavaScript generado con DOM simulado: contrato API, renderizado, escape y CSRF. |
| `test_catalog_connected_flow.py` | 10 PASS | Integración del catálogo y respuestas en entorno aislado. |
| `test_review_send_state_9f3ac70.py` | 5 PASS | Estados de envío, incluido fallo del procesamiento del canal sintético. |
| `test_review_catalog_form_9fcf9df.py` | **0 PASS / 6 FAIL** | JavaScript real extraído del HTML, ejecutado con DOM/API simulados, respuestas demoradas y reloj controlado. |

Todas se ejecutaron mediante `tests/run_isolated.py`. No se reejecutaron aquí las 129 pruebas declaradas por Antigravity. Las nuevas pruebas no son una auditoría de renderizado del navegador ni una constatación de incidentes ya sufridos en producción: reproducen defectos de la lógica actual sin llamadas externas.

Logs: `logs/review_9fcf9df_form.log`, `logs/review_9fcf9df_contract.log`, `logs/review_9fcf9df_connected.log`, `logs/review_9fcf9df_send_state.log` y `logs/review_9fcf9df_behavior.log`.

## Hallazgos que requieren corrección

### 1. P2 — La fecha de Lima depende incorrectamente de la zona del navegador

Ubicación: `catalog_ui.py:840`, función `getLimaDateStr()`.

`Date.getTime()` ya representa el instante UTC. Sumar después `getTimezoneOffset()` y restar cinco horas introduce una segunda conversión. Con el navegador en Lima, a las 20:00 del 3 de octubre de 2026 devuelve `2026-10-04`, aunque en Lima sigue siendo 3 de octubre. Una tarifa con vigencia hasta el día 3 puede aparecer vencida cinco horas antes de lo debido.

La prueba controla el instante `2026-10-04T01:00:00Z` y el desfase del navegador de Lima. Espera `2026-10-03`; obtiene `2026-10-04`.

Corrección: calcular explícitamente el día en `America/Lima` o usar el instante UTC menos cinco horas sin sumar el desfase del navegador, manteniendo el mismo criterio del servidor. Comprobar inicio y fin inclusivos y navegadores en varias zonas.

### 2. P2 — Cambiar de tarifa o pulsar «Añadir tarifa» borra el borrador

Ubicación: `catalog_ui.py:1149`, `showRateForm()`, y `catalog_ui.py:1276`, `editRateById()`.

La protección existe al cancelar o cambiar de pestaña, pero estos dos caminos cargan otro formulario y reemplazan `initialRateSnapshot` sin comprobar `isRateFormDirty()`:

- Editar tarifa A, cambiar el precio y pulsar editar B: se pierde el cambio de A sin confirmación.
- Preparar una tarifa nueva y pulsar «Añadir tarifa» de nuevo: se borran sus campos sin confirmación.

Ambos casos fallan por separado en la prueba independiente, incluso configurando una respuesta de rechazo al descarte.

Corrección: pasar cualquier sustitución del formulario de tarifa por una única comprobación de borrador. Rechazar el descarte debe conservar identidad, valores y formulario abierto. Confirmarlo debe descartar únicamente el borrador correspondiente. No reiniciar la instantánea antes de resolver esa decisión.

### 3. P2 — La referencia de precio base muestra datos aún no guardados

Ubicación: `catalog_ui.py:915`, `switchModalTab()`, especialmente líneas 923–939. La moneda de una tarifa nueva también se toma del formulario del tour en la línea 1168.

El diálogo propone «descartar» los cambios del tour, pero al aceptarlo no restaura sus valores. Además, la referencia oficial se obtiene directamente de `formPrice` y `formCurrency`, no del último registro guardado.

Reproducción: tour guardado con USD 80 → editar el borrador a PEN 90 → aceptar cambiar a tarifas. La referencia muestra **PEN 90**, aunque lo guardado sigue siendo **USD 80**.

Corrección: separar el registro confirmado del borrador. La referencia debe provenir exclusivamente del último guardado confirmado. Si la interfaz dice «descartar», debe restaurar realmente ese borrador; si lo conserva, debe explicarlo y mantenerlo pendiente. La moneda predeterminada de una nueva tarifa no debe depender de cambios descartados.

### 4. P2 — Una respuesta de guardado marca cambios posteriores como guardados

Ubicación: `catalog_ui.py:1428`, manejador de envío de `tourForm`.

Se captura `initialTourSnapshot = getTourFormSnapshot()` cuando llega la respuesta, leyendo los valores que estén entonces en pantalla. Sólo se bloquea el botón; los campos siguen editables.

Reproducción: enviar nombre A → escribir nombre B mientras el POST sigue pendiente → recibir éxito de A. El servidor recibió A, pero la interfaz considera B guardado y `isTourFormDirty()` devuelve `false`. Cerrar puede perder B sin aviso.

Corrección: usar como estado confirmado el contenido exacto del envío que tuvo éxito, conservando posteriores ediciones como pendientes, o impedir esas ediciones mientras se guarda. Aplicar también un control de sesión/identidad del editor: una respuesta anterior no puede limpiar ni modificar un formulario nuevo. Auditar el guardado de tarifas, que oculta su editor tras la respuesta, con el mismo criterio.

### 5. P2 — Una respuesta tardía mezcla tarifas de distintos tours

Ubicación: `catalog_ui.py:1191`, `loadTourRates()`, especialmente líneas 1208–1214.

Todas las respuestas sustituyen `CURRENT_TOUR_RATES`, el contador y la lista, sin comprobar que el tour solicitado siga siendo el abierto.

Reproducción: cargar A con demora → abrir B y completar su carga → llega A. Las tarifas de A reemplazan las de B. No es sólo un texto equivocado: los botones actúan sobre los IDs de la lista recibida, por lo que pueden ofrecer edición o eliminación del registro de otro tour.

Corrección: identificar la sesión del editor y la solicitud vigente. Ignorar respuestas anteriores o de otro tour, incluidos errores, limpieza y callbacks de guardado/eliminación. Cancelar una petición puede ser complementario, pero no sustituye comprobar su identidad antes de aplicar resultados.

## Encargo consolidado para Antigravity

Corregir conjuntamente los cinco hallazgos anteriores en `catalog_ui.py`, conservando las pestañas, componentes, endpoints, autenticación, CSRF, datos de agencia y reglas actuales. Evitar nuevas funcionalidades o cambios de arquitectura. Esta tarea debe resolver la gestión de estado del editor de manera coherente, sin añadir arreglos dispersos por cada botón.

1. Separar claramente registro confirmado, borrador de tour y borrador de tarifa. Asociarlos a la identidad del tour y a la sesión actual del editor. La referencia del precio base sólo utiliza datos confirmados.
2. Centralizar la protección de borradores para todas las acciones que los reemplazan o cierran: cambiar pestaña/tour/tarifa, añadir otra tarifa, cancelar, cerrar, fondo y Escape. Conservar debe conservar; descartar debe restaurar o retirar el borrador correspondiente. Evitar que un guardado independiente borre el otro formulario.
3. Durante POST, conservar el contenido enviado como referencia del guardado, o bloquear los campos afectados. Conservar campos y estado pendiente ante errores. Ignorar respuestas de una sesión anterior y evitar que las solicitudes tardías de A modifiquen B.
4. Corregir el cálculo de vigencia a Lima independientemente de la zona del navegador. Mantener vacío distinto de cero y no restaurar campos canónicos que la agencia borró.
5. Usar las seis regresiones independientes de `tests/test_review_catalog_form_9fcf9df.py` y su archivo JavaScript como evidencia inicial. Corregir la aplicación sin debilitar las aserciones. Se admite bloquear la edición durante el POST en vez de conservar ediciones simultáneas: la prueba contempla ambas soluciones.
6. Añadir sólo los casos necesarios que completen estos mismos riesgos: POST fallido conserva borrador; respuesta tardía tras cerrar/reabrir o crear otro tour; guardar una tarifa no borra una edición posterior; estados de vigencia alrededor de medianoche; independencia entre tour y tarifa. Mantener las regresiones relevantes de catálogo, CSRF, escape, integración y envío. El éxito debe provenir de aserciones de comportamiento, no de encontrar nombres de funciones en HTML.
7. Después de los arreglos funcionales, comprobar en navegador real 320, 390, 600 y 1440 px con tarifas abiertas, textos largos y acciones visibles. Separar esa evidencia visual de las pruebas con DOM simulado. No se ha certificado aquí el diseño responsivo.
8. Confirmar con base aislada el recorrido de creación y recarga: tour nuevo activo → aparece y puede seleccionarse en las categorías del bot → datos guardados consultables; tour desactivado → no ofertado. La prueba conectada actual confirma inclusiones de un tour personalizado, pero esa afirmación no sustituye verificar su navegación por categorías.

Seguir `AGENTS.md`: rama `feature/...`, corrección y pruebas locales antes de respaldo/integración, y despliegue sólo de la versión probada y versionada. Registrar evidencia, commit y revisión realmente servida. Separar las verificaciones de lectura en producción de las pruebas que guardan datos, e informar el alcance de cada una. No declarar «100 % del formulario validado» por contar pruebas de presencia o un `/health` correcto.

## Archivos añadidos durante la revisión

Únicamente este informe y las regresiones `tests/test_review_catalog_form_9fcf9df.py` / `.js`. No se cambió el código del bot ni se hizo commit, push o despliegue. Las pruebas nuevas quedan fallando intencionadamente como evidencia reproducible para la corrección.

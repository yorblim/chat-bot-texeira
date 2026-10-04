# Verificación independiente del formulario — revisión 00045

Código revisado: `73b82b0`, merge de `8860693`. Se contrastó el nuevo informe de Antigravity con la implementación, las once regresiones del formulario y el flujo conectado. No se modificó ni desplegó la aplicación, ni se guardaron datos en producción.

## Resultado

Los cinco hallazgos de `VERIFICACION_FORMULARIO_00044_20261003.md` tienen correcciones concretas y los seis recorridos originales pasan. También pasan los cinco escenarios adicionales de Antigravity. Queda por completar la gestión del editor de **tarifas durante un guardado**, con un defecto de duplicación y un defecto menor de avisos. No requiere cambiar la arquitectura ni rehacer el formulario.

## Comprobaciones realizadas

| Comprobación | Evidencia |
| --- | --- |
| Código e integración | `73b82b0` / `8860693`; árbol limpio al iniciar la revisión. |
| Regresiones existentes del formulario | `test_review_catalog_form_9fcf9df.py`: **11 PASS / 0 FAIL**. Se conservan los seis recorridos iniciales. |
| Flujo de catálogo y bot | `test_catalog_connected_flow.py`: **11 PASS / 0 FAIL**, con base temporal y red externa bloqueada. |
| Contrato JavaScript/API | `test_catalog_ui_contract.py`: **PASS**, incluido escape y cabecera CSRF. |
| Nuevas regresiones independientes de tarifas | `test_review_rate_save_73b82b0.py`: **0 PASS / 2 FAIL**, JavaScript real y DOM/API simulados. |
| Revisión servida en Cloud Run | Consulta independiente: `texeira-whatsapp-00045-sfc`, creada/lista, **100 % del tráfico**. |
| Salud pública | Primera petición agotó 45 segundos; el reintento respondió **200**, `{"status":"ok"}`, en aproximadamente **715 ms**. No se atribuye causa ni se deduce disponibilidad continua. |

Logs: `logs/review_73b82b0_form.log`, `logs/review_73b82b0_connected.log`, `logs/review_73b82b0_contract.log`, `logs/review_73b82b0_rate_save.log`.

No se reejecutaron aquí las demás suites declaradas en el informe. Las pruebas JS ejecutan el código generado del formulario con DOM, reloj y API simulados: no son guardados reales contra Neon ni certificación de diseño en un navegador.

La prueba conectada emite avisos de dependencias y un fallo de inicialización del LLM sin clave en un recorrido aislado. Termina con 11 PASS, pero no acredita calidad de respuestas con el proveedor real. La inicialización del recuperador tocó un archivo generado de Chroma (`length.bin`); se comprobó que estaba limpio antes de la prueba y su escritura coincidió con ésta, y se restauró exclusivamente ese archivo. No queda modificación de datos versionados ni código de aplicación causada por esta revisión.

## Correcciones anteriores confirmadas

- `getLimaDateStr()` usa el instante absoluto menos cinco horas y pasa fecha de Lima y límites de vigencia.
- `showRateForm()` comprueba el borrador antes de sustituirlo por otra tarifa o una nueva.
- La referencia base usa la instantánea confirmada; aceptar descartar restaura los campos del tour.
- El guardado de tour toma una instantánea del contenido enviado, manteniendo posteriores ediciones pendientes. Se añade identidad de sesión del editor.
- `loadTourRates()` comprueba secuencia de solicitud y tour actual antes de aplicar una respuesta o un error anterior.

## 1. P2 — El segundo guardado de una tarifa recién creada puede duplicarla

Ubicación: `catalog_ui.py:1424–1431`, respuesta exitosa de `saveRate()`. Contrato de persistencia: `catalog_service.py:822–862`.

Recorrido reproducido:

1. Crear una tarifa con precio 50 y enviarla. El primer POST no tiene `id`, correctamente.
2. Mientras espera, añadir una condición en el formulario.
3. Recibir éxito de la API con `rate_id:99`. Se conserva el borrador, pero `rateId` sigue vacío.
4. Volver a guardar esa condición. El segundo POST vuelve a salir **sin `id`**.

La regresión comprueba el segundo payload: espera `id:99` y obtiene `undefined`. El servidor hace UPDATE cuando recibe `id`, e INSERT cuando no lo recibe; por tanto, este recorrido puede crear otra tarifa en lugar de actualizar la que acaba de guardar. La base admite varias tarifas con ese nombre. El fallo se reprodujo con API simulada, no mediante duplicados creados en producción.

La prueba añadida por Antigravity comprueba que las condiciones posteriores se conservan y el formulario sigue pendiente, pero se detiene antes del segundo guardado; por eso pasa y no detecta la omisión del ID.

Corrección: adoptar el ID confirmado en el editor de la misma tarifa y en su instantánea confirmada, manteniendo pendientes las modificaciones posteriores. No adoptar ese ID si ya se abrió otra tarifa o sesión. También es válida una estrategia explícita que impida modificar el formulario durante el POST y evite este recorrido.

## 2. P3 — La respuesta de A sustituye la referencia de cambios de B

Ubicación: `catalog_ui.py:1403–1429`. `currentEditorSessionId` identifica el editor del tour; no cambia al sustituir la tarifa dentro del mismo tour.

Recorrido reproducido:

1. Editar y guardar tarifa A (`id:1`). Mantener su POST pendiente.
2. Abrir tarifa B (`id:2`) confirmando el descarte del borrador visible. B aparece sin cambios pendientes.
3. Resolver el POST de A con éxito.
4. El editor sigue mostrando B, pero `initialRateSnapshot` pasa a contener `id:1`, el de A. B queda marcada como pendiente aunque no se haya editado.

La regresión espera que la referencia de B conserve `id:2` y obtiene `id:1`. El efecto demostrado es un aviso de descarte falso; **no se demostró pérdida ni sobrescritura de datos de B**.

Corrección: identificar cada edición de tarifa, además de la sesión del tour, y comprobar esa identidad antes de ocultar el formulario, cambiar su instantánea, adoptar IDs o actualizar su estado de guardado. Se admite bloquear explícitamente el cambio de tarifa mientras está guardando. Una recarga legítima de la lista tras guardar A puede mantenerse sin modificar el borrador de B.

## Límites de otras afirmaciones del informe

- El ciclo conectado comprueba creación, aparición textual por categoría, datos guardados y desaparición del listado al desactivar. Invoca `rag_chain()` por texto; no recorre un botón real `btn_tour` desde el webhook. No equivale a una prueba de navegación real por WhatsApp.
- Su última aserción de desactivación acepta que la respuesta contenga «asesor», entre otras condiciones. Por sí sola permitiría una oferta de precio seguida de esa palabra. Conviene exigir además que no se oferte el precio ni la reserva del tour desactivado y comprobar la ruta correspondiente.
- No se reprodujo en esta revisión la auditoría visual de 320, 390, 600 y 1440 px. La afirmación de tres columnas a 1440 px tampoco se desprende del CSS vigente: `admin_theme.py:365–367` establece dos columnas con `!important`. Verificar el estilo calculado y las capturas antes de dar por acreditada una disposición concreta. Esto no implica que dos columnas sean un defecto de diseño.
- Se comprobó `/health`; no se repitió aquí la autenticación de `/catalogo`. No se midió facturación: escala a cero no equivale a garantía de costo final cero.

## Encargo final para Antigravity

Completar el guardado de tarifas en `catalog_ui.py` con una gestión coherente de identidad del tour, identidad de edición de tarifa y solicitud en curso:

1. Al crear una tarifa y conservar ediciones posteriores, adoptar `res.rate_id` en la misma tarifa y ajustar su instantánea confirmada. El siguiente guardado debe enviar ese ID y actualizar una única fila, conservando las condiciones posteriores.
2. Si se cambia de tarifa antes de resolver un POST anterior, ese resultado no puede modificar el formulario, instantánea, ID ni estado de guardado del nuevo editor. Revisar también los callbacks de error y `finally` con el mismo criterio. Puede implementarse bloqueo explícito mientras guarda si mantiene una experiencia clara.
3. Ejecutar `tests/run_isolated.py test_review_rate_save_73b82b0.py`. Las dos regresiones nuevas deben pasar sin debilitar las aserciones. Admiten impedir edición/cambio durante el POST como alternativa a conservarlos de forma concurrente. Conservar las once regresiones existentes y el contrato API/CSRF.
4. Añadir una comprobación con base aislada de creación → edición posterior → segundo guardado: **una tarifa**, mismo ID, condiciones actualizadas. Completar la prueba de selección por botón del tour nuevo y endurecer la aserción de tour desactivado conforme al contrato actual, sin volver a exigir un listado plano que ya se sustituyó por categorías.
5. Aportar o identificar la evidencia de navegador ya obtenida para los cuatro anchos. Registrar los resultados medidos y el estilo calculado; no sustituirlo por una descripción del CSS. Mantener componentes, datos de agencia, endpoints y reglas existentes.
6. Seguir `AGENTS.md`: rama, pruebas locales, respaldo/integración y despliegue de esa versión probada. Comprobar después revisión y salud, y distinguir pruebas locales de acciones reales en producción.

No se requieren nuevas funciones comerciales ni otro rediseño. Los cinco arreglos anteriores quedan reconocidos; el cierre pendiente es el guardado de tarifas y la evidencia de aceptación indicada.

## Archivos de esta revisión

Se añadieron exclusivamente este informe y `tests/test_review_rate_save_73b82b0.py` / `.js`. El archivo JS reutiliza el fixture de las once pruebas existentes sin modificarlas. No se hicieron commit, push ni despliegue. Las dos regresiones nuevas quedan fallando como evidencia para la corrección.

# Verificación de cierre funcional del formulario de catálogo

Fecha: 4 de octubre de 2026. Código revisado: `9bc1175`, integración de `10f3344`. Revisión observada en Cloud Run: `texeira-whatsapp-00047-khb`.

## Conclusión

**Los dos defectos pendientes de `VERIFICACION_FORMULARIO_00045.md` están corregidos y sus regresiones independientes pasan.** Se puede cerrar esta corrección funcional del formulario de catálogo y tarifas dentro del alcance comprobado. No se identificaron nuevos fallos bloqueantes en esos arreglos.

El código conserva las mejoras anteriores y completa la identidad de las tarifas durante el guardado. Las comprobaciones de interfaz usan el JavaScript generado con DOM/API simulados; las de persistencia utilizan una base temporal. No se enviaron mensajes reales a clientes, se guardaron datos en producción ni se hicieron cambios o despliegues de la aplicación durante esta revisión.

## Evidencia independiente ejecutada

Todas las suites locales se ejecutaron mediante `tests/run_isolated.py`, con base temporal y red externa bloqueada.

| Suite | Resultado | Qué acredita |
| --- | --- | --- |
| `test_review_rate_save_73b82b0.py` | **2 PASS / 0 FAIL** | Segundo guardado con ID confirmado; respuesta de A no modifica el estado de B. |
| `test_review_catalog_form_9fcf9df.py` | **11 PASS / 0 FAIL** | Regresiones anteriores de borradores, precio confirmado, guardado, respuesta tardía y vigencia de Lima. |
| `test_catalog_connected_flow.py` | **12 PASS / 0 FAIL** | Catálogo-bot, tarifa creada y actualizada sin duplicación, selección por webhook interactivo y desactivación. |
| `test_catalog_ui_contract.py` | **PASS** | JavaScript renderizado, escape, edición, guardado y contrato API/CSRF. |
| `test_conversational.py` | **36 PASS / 0 FAIL** | Regresiones conversacionales relevantes. |
| `test_audit_20260912.py` | **21 casos PASS** | Endpoints, integridad, conflictos y métricas en entorno aislado. |

Logs conservados en `logs/`, con prefijo `review_9bc1175_` y el nombre de cada suite. No se reejecutaron las otras suites declaradas por Antigravity.

## Cierre de los defectos anteriores

### Identidad de tarifa nueva y segundo guardado

`catalog_ui.py:1442–1457` obtiene el ID confirmado de la respuesta. Si el administrador editó durante el POST y sigue en la misma tarifa, conserva esos cambios, adopta el ID en `rateId` y lo incorpora a la instantánea confirmada. El siguiente guardado envía `payload.id` y actualiza la tarifa existente.

La regresión JavaScript original ahora pasa sin cambios en sus aserciones. La prueba de integración crea una tarifa sin ID, realiza el segundo POST con el ID confirmado y verifica **una única fila**, el mismo ID, precio actualizado y condiciones actualizadas. Esta segunda prueba comprueba la persistencia; la regresión JS comprueba que el editor envía correctamente el ID.

### Respuestas anteriores y editor de otra tarifa

`currentRateEditorSessionId` identifica la edición de tarifa, además de la sesión del tour. Cambia al abrir o retirar el editor. El resultado de un POST anterior sólo puede actualizar los campos y la instantánea si coincide esa identidad. El manejo de error y la restauración del botón también quedan sujetos a ella.

El recorrido de guardar A, abrir B y recibir después el éxito de A conserva el ID y la instantánea de B, que sigue sin cambios pendientes falsos. La regresión independiente pasa.

## Catálogo conectado y tours inactivos

- Se comprobó la creación y consulta del tour sintético Cañón de Tinajani Trek en la base aislada.
- La prueba añadió un mensaje `interactive.button_reply` con `btn_tour:canon-tinajani-trek:es` al webhook, con transporte saliente simulado. El log observado registra `route=evidence_tour_overview`.
- Tras desactivar ese tour, desaparece del listado comprobado y la consulta no ofrece su precio guardado ni la frase de solicitud de reserva.
- `verified_routes.py:452–468` incorpora identificación de tours personalizados inactivos cuando no existe coincidencia activa o canónica. Se mantiene la prioridad de los matches anteriores. Las regresiones conversacionales y de auditoría pasan.

Una limitación de cobertura permanece en la prueba interactiva: su aserción textual admite sólo el nombre del tour, y el botón se construye en la prueba en lugar de comprobar que aparezca entre los generados por la categoría. El comportamiento observado en esta ejecución sí alcanzó la ficha del tour. No se considera una regresión de la aplicación ni impide cerrar los dos defectos de guardado corregidos; se distingue de una certificación de todo el recorrido comercial real.

## Verificación del despliegue

Consulta independiente de Cloud Run:

- `latestCreatedRevisionName`: `texeira-whatsapp-00047-khb`.
- `latestReadyRevisionName`: `texeira-whatsapp-00047-khb`.
- Tráfico: **100 %** para esa revisión.
- Endpoint público `/health`: **HTTP 200**, `{"status":"ok"}` en esta comprobación.

El repositorio estaba limpio antes de iniciar la revisión y `git diff --check` no reportó problemas. Se contrastaron los commits locales; no se repitió el push ni se verificó de nuevo el contenido del remoto mediante fetch. La revisión y la salud no sustituyen una prueba con mensajes reales de WhatsApp.

## Alcance del cierre

Se cierra la **corrección funcional del formulario y del guardado de tarifas** comprobada aquí. No se certifica el 100 % del sistema, precisión del LLM, disponibilidad continua, costo final, guardados reales en Neon o todo el comportamiento visual en móviles.

La aclaración del informe sobre las columnas concuerda con el CSS: dos columnas en escritorio y una bajo 700 px en el tema compartido. No se ejecutó aquí una auditoría de renderizado real a 320, 390, 600 y 1440 px; leer esa regla no demuestra por sí solo ausencia de desbordamiento en cualquier contenido.

Las pruebas reales del piloto y la evaluación de respuestas en distintos idiomas mantienen su propio alcance y evidencia. Messenger continúa fuera de esta tarea, según la decisión del usuario.

## Trazabilidad de esta revisión

Se añadió exclusivamente este documento. No se modificaron pruebas ni aplicación, no se hicieron commit/push y no se ejecutó `actualizar_nube.bat`. La evidencia queda centralizada en `docs/` y `logs/`, conforme a `AGENTS.md`.

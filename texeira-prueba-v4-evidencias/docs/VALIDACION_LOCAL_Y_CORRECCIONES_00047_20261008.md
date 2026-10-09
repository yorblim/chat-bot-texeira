# Validación local y correcciones del piloto — 08–09/10/2026

## Alcance y estado

Se continúa el plan de validación de la revisión 00047 en orden: reproducir defectos en local, corregirlos, ejecutar regresiones, integrar mediante Git y después comprobar producción y WhatsApp. El usuario hará la prueba desde su teléfono **más tarde**. Messenger permanece aplazado.

Base de esta revisión: `main` en `62b9a94`. Rama de trabajo: `feature/validate-whatsapp-plan-and-recommendations`. Las modificaciones se limitan a la carpeta activa. El objetivo sigue siendo atención turística con información oficial, catálogo vigente y derivación humana honesta. No se añaden reservas confirmadas, pagos, destinos inventados ni nuevas fuentes de conocimiento.

## Defectos reproducidos y comportamiento corregido

La primera ejecución de 14 regresiones independientes obtuvo **3 aprobados y 11 fallos**. Después se incorporaron controles adicionales; la suite final tiene **20 pruebas**, incluidas ocho variantes de negación natural en un método con subcasos. El log inicial se conserva en `logs/piloto_00047_recommendation_edges_before_20261008.log` y el final en `logs/piloto_00047_recommendation_edges_after_20261009.log`.

1. **Duración vigente:** una duración borrada, desconocida o expresada solamente en noches no acredita un número exacto de días. El filtro admite datos explícitos en español e inglés y no inventa «Full Day» para productos sin duración documentada.
2. **Preferencias entre turnos:** una respuesta sobre tiempo conserva la última preferencia explícita de caminatas. Una preferencia nueva puede reemplazar la anterior; una pregunta como «¿Hay caminatas?» no revoca una negativa. Se comprueban negativas naturales como «No quiero hacer caminatas», «No me gustan las caminatas», «I don't want to hike» e «I don't like hiking», después de preferencias positivas y negativas y tras un seguimiento temporal. Esta clasificación no certifica accesibilidad ni ausencia absoluta de cualquier desplazamiento a pie.
3. **Alternativas rechazadas:** «ninguno» u «otras opciones» excluyen los tours previamente recomendados bajo los mismos criterios. Si se agotan las opciones verificadas, el bot propone ajustar preferencias o revisar opciones anteriores sin repetir indefinidamente la misma lista.
4. **Memoria por identidad:** se guardan IDs ofrecidos/rechazados y criterios en los metadatos JSON de la respuesta, utilizando la memoria existente. Un cambio de nombre no pierde la identidad. Historias antiguas se reconocen únicamente por el formato propio de recomendaciones; si no pueden identificarse los productos, se pide aclaración. Las listas de categorías no se interpretan como recomendaciones rechazadas.
5. **Idioma real del detector activo:** «2 days» permanece en inglés. El detector efectivo está instalado por `trial_support.py`; cambiar únicamente el detector original de `app.py` no corregía la ejecución. La prueba comprueba ruta, tour e idioma de la respuesta.
6. **Disponibilidad frente a preferencias:** «¿Tienen paquete de 7 días?» y su equivalente inglés mantienen la ruta de confirmación comercial. Esa consulta no se convierte en una preferencia temporal para recomendaciones posteriores.

No se modificaron tarifas, horarios, inclusiones, hechos F1/F2/F3, recursos multimedia ni el transporte de WhatsApp.

## Verificaciones locales

Todas las ejecuciones usan `tests/run_isolated.py`, SQLite y catálogo temporales, proveedores externos bloqueados y transporte simulado donde corresponde. Los logs están en `logs/` y se descartan los informes generados por suites antiguas en el espejo temporal.

| Suite | Resultado local | Log |
| --- | --- | --- |
| `test_validation_recommendation_edges_20261008.py` | 20/20 aprobadas | `piloto_00047_recommendation_edges_after_20261009.log` |
| `test_recommendations_and_schedules.py` | 5/5 aprobadas | `piloto_00047_recommendations_20261009.log` |
| `test_review_followups_20261002.py` | 4/4 aprobadas | `piloto_00047_followups_20261008.log` |
| `test_review_preferences_00041.py` | 2/2 aprobadas | `piloto_00047_preferences_20261008.log` |
| `test_conversation_memory.py` | 8/8 aprobadas | `piloto_00047_memory_20261008.log` |
| `test_whatsapp_flow_polish.py` | 13/13 aprobadas | `piloto_00047_flow_20261009.log` |
| `test_conversational.py` | 36 comprobaciones aprobadas | `piloto_00047_conversational_20261008.log` |
| `test_audit_20260912.py` | 21 casos de endpoint aprobados y controles de integridad | `piloto_00047_audit_20261008.log` |
| `test_isolated_artifact_guard.py` | 7/7 aprobadas | `piloto_00047_guard_20261009.log` |
| `test_review_recommendations_20261002.py` | 6/6 aprobadas y cierre temporal completado | `piloto_00047_independent_recommendations_20261009.log` |
| `test_isolated_chroma_cleanup.py` | 3/3 aprobadas | `piloto_00047_chroma_cleanup_20261009.log` |
| `test_index_preflight.py` | Manifiesto y 20 documentos coherentes | `piloto_00047_index_preflight_20261009.log` |

El bloqueo inicial de TestClient en el sandbox provino del loopback interno de asyncio/AnyIO en Windows. Esas suites se ejecutaron con permiso de ejecución local fuera de ese sandbox, conservando el bloqueo de red externa del runner. No se cambió el bucle de eventos de la aplicación por esa condición del entorno.

## Protección de fuentes e históricos

El runner copia el índice vectorial a estado temporal y dirige escrituras Python de `docs/` a un espejo temporal. Incluye controles de escritura, lectura posterior, modos append/update/exclusivo, metadatos y bloqueo de mutaciones sobre originales. No constituye un sandbox para código C ni para subprocess arbitrarios; la enumeración de artefactos nuevos debe usar `TEXEIRA_ISOLATED_DOCS_DIR`.

Se reprodujo además un fallo de limpieza del índice temporal en Windows: Chroma mantenía abiertos archivos HNSW tras terminar las aserciones. El cierre ahora detiene explícitamente solo los sistemas persistentes cuyo directorio pertenece al estado temporal de esa ejecución. Los tres controles de limpieza comprueban liberación con clientes todavía referenciados, conservación de sistemas fuera del directorio solicitado y eliminación del estado incluso cuando la prueba devuelve un código de error. No se silencian fallos mediante `ignore_cleanup_errors`.

Comparación byte a byte con `git show HEAD:<ruta>`: los tres históricos permanecen intactos:

| Archivo en `docs/evaluaciones/` | SHA-256 |
| --- | --- |
| `RESULTADOS_POSPRUEBA_TESIS_20260921.json` | `7030845ec01017ca6c4d94359d4c53a9c38ddf7c254799496a8ed931c1af4310` |
| `INFORME_POSPRUEBA_TESIS_20260921.md` | `05dcde96e2ee475a5fa9bb316723ce5507d3823697326c7fe4a29c9e06c0a8ac` |
| `RESULTADOS_POSPRUEBA_TESIS_20261004_RECALIBRADO.json` | `94cf536525bd19fb215968908345919a5c3fe907969b8901acdd18a080de4b59` |

## Qué acredita esta revisión y qué queda

Las trazas `CASETRACE` de la nueva suite comprueban respuestas y rutas por reglas, sin llamadas al recuperador ni al LLM. Otras suites utilizan dobles de generación y/o recuperación local. **No se invocó Groq real, no se enviaron mensajes a clientes ni se probó recepción en WhatsApp.** Un mock exitoso no valida la calidad de un modelo real.

Estas regresiones no equivalen a ejecutar ni aprobar los 42 casos del registro del piloto. El JSON `REGISTRO_VALIDACION_WHATSAPP_00047.json` conserva sus casos pendientes; no se calcula una precisión actual. El 73,3 % histórico corresponde a 22/30 respuestas antiguas y no describe esta versión.

Para continuar:

1. Las regresiones locales están cerradas; respaldar/integrar la rama según `AGENTS.md`.
2. Desplegar la versión integrada manteniendo la configuración existente de escala a cero (`min-instances=0`). Esta opción no garantiza una factura de cero ni disponibilidad ininterrumpida.
3. Comprobar revisión activa, salud y seguridad de paneles; esas comprobaciones no certifican recepción en el teléfono.
4. Cuando el usuario esté disponible, ejecutar y registrar el recorrido real: categorías/paginación, recomendaciones y cambios de preferencias, entidad/idioma de botones, fotos correctas y solicitud única al asesor.
5. Completar los casos restantes por modalidad y acreditar recuperación/generación real cuando corresponda. Después realizar validación humana, preprueba/posprueba y encuestas para contrastar la tesis. Messenger continúa pendiente por decisión del usuario.

Integración cerrada el 09/10: commit de correcciones `6fd6131`, rama `feature/validate-whatsapp-plan-and-recommendations`, merge a `main` `61cafec`. Rama y main respaldadas en `origin`; árbol limpio al iniciar el despliegue. Se ejecutó `actualizar_nube.bat` desde esa integración. Consultar [VERIFICACION_DESPLIEGUE_RECOMENDACIONES_20261009.md](VERIFICACION_DESPLIEGUE_RECOMENDACIONES_20261009.md) para su resultado y las comprobaciones posteriores. El cierre local no da por completado el proyecto ni las pruebas de WhatsApp.

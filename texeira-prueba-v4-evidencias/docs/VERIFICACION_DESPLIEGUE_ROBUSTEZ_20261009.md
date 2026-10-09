# Despliegue y verificación de robustez conversacional — 09/10/2026

## Código y validación local

Commit de aplicación, banco y pruebas: `bc3b333`. Primera integración respaldada en `origin/main`: `85f5c6e`. Rama de implementación: `feature/automated-conversation-robustness-20261009`. Rama de la corrección de compilación: `feature/fix-pyarrow-build-compatibility-20261009`; rama de cierre documental: `feature/record-robustness-deployment-20261009`.

El lote final registró **148 casos: 138 estructurales aprobados, 0 estructurales fallidos y 10 exploraciones pendientes de evaluación real**. Procesó 183 mensajes, con 169 textos distintos y 14 repeticiones como seguimientos. Las siete suites seleccionadas terminaron con código 0; las fuentes seleccionadas permanecieron estables durante la ejecución. Controles adicionales: contrato del informe 7/7 y erratas de entidad 4/4.

La [evidencia completa](evaluaciones/ROBUSTEZ_AUTOMATICA_20261009T181951Z_8f9ce584.json) conserva entradas, respuestas, rutas, aserciones, excepciones y hashes. El [plan de pruebas por lotes](PLAN_PRUEBAS_AUTOMATICAS_Y_CIERRE_20261009.md) detalla el baseline, las correcciones y los límites. Estos resultados no son una precisión porcentual del bot ni aprobación automática de los 42 casos académicos.

Se corrigieron rutas e idioma para consultas breves ES/EN, reconocimiento acotado de erratas únicas en nombres, precio coloquial, persistencia de preferencias de caminatas y duración numérica/escrita. No se modificaron ofertas reales, tarifas, horarios, imágenes, proveedor ni secretos. Los datos sintéticos del banco no se guardaron en producción.

## Despliegue

Proyecto `texeira-whatsapp-bot`; servicio `texeira-whatsapp`; región `us-central1`. Script existente `actualizar_nube.bat`, sin modificaciones. Log: `logs/despliegue_85f5c6e_20261009.log`.

Cloud Build: `fa945f68-35e6-453c-9df7-86a3518c9db8`, iniciado el `2026-10-09T18:27:36.071981527Z`. La subida del código terminó antes de preparar este registro documental.

**Primer intento fallido:** Cloud Build terminó `FAILURE` el `2026-10-09T18:38:18.879669Z`. El paso de importación/descarga de SentenceTransformer falló al importar PyArrow 26.0.0: requiere NumPy >=2, mientras LangChain 0.3.14 seleccionó NumPy 1.26.4. Log: `logs/cloudbuild_fa945f68_20261009.log`.

La consulta posterior confirmó que `texeira-whatsapp-00048-mvd` continuaba con 100 % del tráfico. El script imprimió el fallo, aunque su proceso finalizó con código 0: se comprobó el estado de Cloud Build y del servicio, sin inferir éxito del código de salida del `.bat`.

La corrección mínima fija `pyarrow==25.0.1` en `requirements.txt`, reproduciendo la combinación NumPy 1.26.4 / datasets 5.0.1 / PyArrow 25.0.1 del build exitoso anterior `71769e58-221e-49b9-a6be-c68afac3532c`. No se subió NumPy ni se modificó Python, Dockerfile o la arquitectura.

Fuentes primarias de compatibilidad: [LangChain 0.3.14](https://raw.githubusercontent.com/langchain-ai/langchain/langchain%3D%3D0.3.14/libs/langchain/pyproject.toml) requiere NumPy <2 para Python <3.12; [datasets 5.0.1](https://raw.githubusercontent.com/huggingface/datasets/5.0.1/setup.py) admite PyArrow >=21; [el cambio oficial de Arrow](https://apache.googlesource.com/arrow/+/b60d43701bae097566bda6b96cd514690ca9dc9d) distingue compatibilidad NumPy 1.x en Arrow 25 de la exigencia de NumPy 2 en Arrow 26.

La corrección se comprobó en un venv temporal con acceso a los paquetes locales: NumPy 1.26.4 / PyArrow 25.0.1 / datasets 5.0.1 / sentence-transformers 3.4.1. Pasaron los imports, una tabla Arrow creada desde NumPy y un Dataset. Con el Python de ese entorno también pasaron el preflight del índice (20 documentos), 36 controles conversacionales y 12 pruebas de catálogo conectado, bajo el ejecutor aislado. Logs: `logs/pyarrow_dependency_imports_20261009.log`, `logs/pyarrow_index_preflight_20261009.log`, `logs/pyarrow_conversational_20261009.log`, `logs/pyarrow_catalog_connected_20261009.log`.

Es una comprobación local Windows; el paso de importación/modelo del siguiente Cloud Build verificará el entorno Linux. No se cambió el PyArrow global instalado ni se enviaron mensajes al teléfono.

Corrección de dependencia: `038dd0b`, integrada y respaldada en `origin/main` mediante `8cc37a0`. Reintento ejecutado con el mismo script, desde ese estado limpio de Git. Log: `logs/despliegue_8cc37a0_20261009.log`.

Segundo Cloud Build: `f64cdb59-d39a-46b0-b309-a5271089e5be`, iniciado el `2026-10-09T20:25:23.928483899Z`.

**Segundo intento completado y verificado:** Cloud Build `SUCCESS`, terminado el `2026-10-09T20:43:37.816126Z`. Digest: `sha256:385477623bb0795c5acb879e2850ffd145bfb9c0cd2cd8181044477cff797642`. La imagen de la revisión tiene exactamente ese digest. El entorno Linux superó el paso de importación y descarga del modelo.

Cloud Run: `texeira-whatsapp-00049-xf5`, con `latestCreatedRevisionName = latestReadyRevisionName`, **100 % del tráfico** y `Ready=True` desde `2026-10-09T20:47:52.598504Z`. Recursos leídos de la revisión: CPU `1`, memoria `2Gi`, máximo `2`, CPU boost activo. Se conservó `--min-instances 0` en el script; no aparece una anotación de mínimo cuando se utiliza ese valor predeterminado.

URL canónica: [servicio desplegado](https://texeira-whatsapp-1038134693816.us-central1.run.app). Evidencias: `logs/servicio_00049_20261009.json`, `logs/revision_00049_20261009.json`, `logs/cloudbuild_f64cdb59_20261009.log`.

## Comprobaciones posteriores en producción

- `tests/verify_live_deployment.py`: código 0. `/health` devolvió HTTP 200 con `{"status":"ok"}`; `/` devolvió HTTP 200 con `status=running` y versión declarada `2.0.0-tesis`. `/dashboard` devolvió 401 sin credenciales y 200 con autenticación.
- Las consultas sintéticas «ayuda» y «qué tours tienen» mediante `/test-chat` pasaron las aserciones de respuesta sin teléfonos ni imágenes no solicitadas. Neon registró dos interacciones y cuatro turnos del alias sintético; se eliminaron únicamente esos datos al terminar. Log: `logs/verificacion_api_00049_20261009.log`.
- `tests/verify_panels_readonly.py`: código 0. `/handoffs`, `/catalogo`, `/dashboard` y `/operational-metrics` devolvieron 401 sin credenciales y 200 autenticados, con navegación y marcadores HTML esperados. Log: `logs/verificacion_paneles_00049_20261009.log`.
- Lectura autenticada de `/api/catalog/tours?all=1`: permanecen exactamente activos `camino-inka`, `inka-jungle` y `maras-moray`. No se modificaron estados, tarifas ni horarios. Evidencias: `logs/catalogo_recomendacion_00049_20261009.json`, `logs/verificacion_catalogo_00049_20261009.log`.

Estos checks acreditan salud observada, acceso, markup y persistencia del canal sintético. No acreditan todas las acciones de los paneles, las diez exploraciones del modelo real ni recepción de mensajes o imágenes en WhatsApp. Las correcciones conversacionales nuevas se verificaron en el banco local; no se presentan las dos consultas de smoke como ejecución de sus variantes en producción.

El plan y registro formal conservan sus nombres para continuidad, con objetivo actualizado a `00049-xf5`. Los 42 casos y sus ejecuciones se mantienen sin cambios y sin aprobaciones ficticias. La evidencia JSON del lote sigue representando su ejecución local original; no se modifica su campo de verificación de producción después del hecho.

## Alcance pendiente

Las diez exploraciones de idiomas adicionales, mezclas y preguntas abiertas mantienen `pending_review`. Se observaron sus rutas con recuperación/generación interceptadas; no se llamó a Groq real ni se certificaron fluidez o fidelidad del modelo.

El usuario no necesita enviar cada variante por WhatsApp. Quedan hasta cuatro recorridos breves para botones/entidad, inglés visible, multimedia y solicitud de asesor sin duplicados, reutilizando las tres capturas ya recibidas. No equivalen a probar todas las formas de escribir.

Se conservan exclusivamente Camino Inca, Inka Jungle y Maras–Moray activos, conforme a la decisión del usuario. Messenger sigue aplazado. La precisión actual permanece sin medir (`null`); los históricos no se recalifican con este lote.

El script mantiene `min-instances=0`, `max-instances=2` y memoria `2Gi`. Escalar a cero no garantiza una factura de $0.00 ni disponibilidad ininterrumpida. No se añadieron recursos o servicios nuevos.

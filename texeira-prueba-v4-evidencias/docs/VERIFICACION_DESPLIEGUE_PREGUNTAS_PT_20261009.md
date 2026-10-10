# Verificación de preguntas abiertas y portugués — 09–10/10/2026

## Cambios y evidencia local

Se corrigieron el enrutamiento de preguntas abiertas hacia RAG y la continuidad de preferencias, respuestas, botones y solicitud de asesor en portugués. Las preguntas que nombran un tour ya no reciben automáticamente una ficha general que no responde a lo preguntado. Se conservan las comprobaciones de catálogo activo y ausencia de evidencia.

Implementación: rama `feature/fix-open-questions-and-portuguese-20261009`, commit `45c2d76`. Integración respaldada en `origin/main`: `6096bcc`. El árbol estaba limpio al iniciar el despliegue. El [informe de correcciones](CORRECCION_PREGUNTAS_ABIERTAS_Y_PORTUGUES_20261009.md) describe las causas, alcance y pruebas.

Pruebas locales nuevas: 58/58 de preguntas/preferencias, 12/12 de botones/API y 13/13 de asesor. También pasaron conversación 36/36, auditoría 21/21 y las suites existentes de atención humana. El lote final de siete suites terminó con código 0 y fuentes estables: 138 casos estructurales aprobados, 0 fallidos y 10 exploraciones pendientes, sobre 183 turnos. Estas coberturas se solapan y no se suman como una medición de precisión.

Evidencia congelada: `docs/evaluaciones/ROBUSTEZ_AUTOMATICA_20261009T214028Z_9ffa49a2.json`. No se modifican sus indicadores de evaluación real ni el registro formal de WhatsApp después de la ejecución.

## Compilación y recuperación del despliegue

Se ejecutó el script existente `actualizar_nube.bat`, sin modificarlo, desde `6096bcc`. Proyecto `texeira-whatsapp-bot`, servicio `texeira-whatsapp`, región `us-central1`.

Cloud Build `727073fa-3fad-4b48-a800-9926e8ba14b7` terminó **SUCCESS** el `2026-10-09T22:00:46.997876Z`; inicio `2026-10-09T21:46:17.289063489Z`. Superó la instalación de dependencias y la importación/descarga de SentenceTransformer.

Digest construido: `sha256:fbdb1847f3593d1885aae1ca9747e3c9235f72fb7cb486a7dec28e0a02b91f2e`.

El cliente local de gcloud falló al consultar la operación de Cloud Build por una resolución DNS fallida de `cloudbuild.googleapis.com`. La compilación había finalizado correctamente, pero el servicio seguía en `texeira-whatsapp-00049-xf5` con 100 % del tráfico. El código de salida 0 del `.bat` no se utilizó como prueba de éxito.

Se retomó la activación con `gcloud run deploy --image` usando el digest inmutable del mismo build. Se conservaron las opciones del script: memoria `2Gi`, CPU boost, mínimo `0`, máximo `2`, plataforma managed y acceso público del webhook. No se inició otra compilación ni se cambiaron secretos, proveedor o catálogo.

Evidencias en `logs/`: `despliegue_6096bcc_20261009.log`, `cloudbuild_727073fa_20261009.log`, `cloudbuild_727073fa_resultado_20261009.json` y `despliegue_imagen_6096bcc_20261009.log`.

## Revisión y verificaciones en producción

Revisión **`texeira-whatsapp-00050-wh7`**, `Ready=True` desde `2026-10-09T22:06:46.930214Z`. El servicio confirmó `latestCreatedRevisionName = latestReadyRevisionName` y **100 % del tráfico**; `Ready=True` desde `2026-10-09T22:06:48.344887Z`. Su digest coincide exactamente con el de Cloud Build. Evidencias: `logs/servicio_00050_20261009.json` y `logs/revision_00050_20261009.json`.

Recursos leídos de la revisión: CPU `1`, memoria `2Gi`, máximo `2`, CPU boost activo, concurrencia `5`, timeout `600` y puerto `8080`. Se conservó mínimo `0` en los dos comandos de despliegue; no figura una anotación de mínimo distinta del valor predeterminado. La comparación con `00049-xf5` confirmó que el entorno y las referencias a secretos permanecieron iguales, sin publicar sus valores.

Las comprobaciones de API se ejecutaron el 10/10/2026 UTC. Los primeros intentos agotaron los límites de lectura: `/health` a 20 segundos; `/handoffs` y `/api/catalog/tours` a 60 segundos. Fallaron antes de los POST sintéticos. Se conservan los logs fallidos, sin presentarlos como aprobados. En Cloud Logging se observaron HTTP 200 para salud y catálogo, y 401 para la petición no autenticada de handoffs con latencia de 67,56 segundos. Estos datos no establecen por sí solos la causa de los timeouts.

Un reintento público acotado de `/health` devolvió **HTTP 200 en 0,633163 segundos**. Evidencias: `logs/health_00050_reintento_20261010.log` y su cuerpo JSON.

- `tests/verify_live_portuguese_recommendations.py`: salida **0**. La lectura del catálogo comprobó exactamente los tres tours autorizados. «Recomende um passeio de meio dia, não quero fazer caminhadas» recomendó Maras–Moray en portugués, con botones `:pt`. El seguimiento «4 dias» conservó la restricción, respondió en PT y quedó pendiente de ajuste, sin contabilizarlo como resuelto. Neon registró dos interacciones PT y cuatro turnos; se eliminaron únicamente las filas del usuario sintético único. Sin mensajes a WhatsApp, solicitudes reales de asesor ni modificaciones al catálogo. Log: `logs/verificacion_pt_00050_reintento_20261010.log`.
- `tests/verify_panels_readonly.py`: salida **0**. Los cuatro paneles `/handoffs`, `/catalogo`, `/dashboard` y `/operational-metrics` devolvieron 401 sin credenciales y 200 autenticados, con navegación y marcadores HTML esperados. Verifica acceso y markup, no todas las acciones de formularios. Log: `logs/verificacion_paneles_00050_reintento_20261010.log`.
- `tests/verify_live_deployment.py`: salida **0**. `/health` y `/` respondieron 200; la raíz declaró `status=running` y versión `2.0.0-tesis`. `/dashboard` devolvió 401 sin credenciales y 200 autenticado. «ayuda» y «qué tours tienen» por `/test-chat` respondieron sin teléfonos ni imágenes no solicitadas. Neon registró dos interacciones y cuatro turnos; se eliminaron las filas del alias sintético de esta suite. Log: `logs/verificacion_api_00050_reintento_20261010.log`.

URL canónica: [servicio desplegado](https://texeira-whatsapp-1038134693816.us-central1.run.app). Las tres suites posteriores terminaron con código 0 en sus reintentos. Se conservan sus primeros intentos fallidos como evidencia independiente.

El cierre documental se registra en la rama `feature/record-open-pt-deployment-20261009`. Solo añade documentación a Git: no cambia la imagen de aplicación ni requiere otro despliegue.

## Alcance y pendientes

La validación local demuestra rutas, idioma de plantillas, estado y continuidad; no certifica precisión del LLM real o recepción de mensajes en el teléfono. La prueba API usa usuarios sintéticos y no transporta mensajes por WhatsApp. La prueba física permanece aplazada por el usuario.

Se mantienen exclusivamente `camino-inka`, `inka-jungle` y `maras-moray` activos. No se agregan datos turísticos ni recursos de pago. Messenger permanece aplazado. La escala a cero (`min-instances=0`) no garantiza una factura de $0 ni disponibilidad ininterrumpida.

Los históricos de septiembre, la recalificación 22/30 (73,3 %) y el registro formal de WhatsApp se conservan intactos. No se aprueban casos académicos a partir de simulaciones o comprobaciones de salud.

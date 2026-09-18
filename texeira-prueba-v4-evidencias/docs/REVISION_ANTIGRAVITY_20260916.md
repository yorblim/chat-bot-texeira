# Revisión de cambios Antigravity — 16/09/2026

**Decisión: no aprobar aún el despliegue.** Revisión del Dockerfile, Compose, filtros, entrada pública y guía Cloud Run. No se modificó código productivo, instalaron herramientas, usaron credenciales, desplegaron servicios ni hicieron llamadas al LLM. Se añadió un diagnóstico sintético y documentación de revisión.

## Hallazgos que bloquean el cierre

1. **P1 — Mensajes descartados durante un arranque fallido.** `whatsapp_entry.startup` captura la excepción sin impedir servir tráfico; POST /webhook devuelve 202 cuando no está listo, sin guardar ni procesar el evento. La respuesta exitosa puede dar por recibido un mensaje perdido. En el mismo estado, /healthz devuelve HTTP 200 y expone el detalle de excepción. Diagnóstico aislado reprodujo 200/error y 202/no listo. Debe fallar el arranque o indicar indisponibilidad con código no exitoso, sin datos internos.
2. **P1 — ACK espera todo el procesamiento.** El nuevo proxy ASGI almacena la respuesta en memoria y solo la devuelve después de `await local_app(...)`, incluyendo BackgroundTasks. La respuesta rápida original se convirtió en una respuesta bloqueada por RAG/Groq. Reproducción: tarea simulada posterior al cuerpo HTTP termina antes del retorno externo. Para Cloud Run hace falta diseñar ACK y trabajo duradero compatibles con asignación CPU y reintentos; no basta restaurar un ACK rápido y asumir trabajo de fondo garantizado.
3. **P1 — Persistencia pendiente.** Cloud Run no conserva su sistema de archivos al terminar la instancia; `/app/state` sin backend persistente no conserva deduplicación, solicitudes ni métricas. Un directorio creado en Docker no es volumen remoto. La guía lo trata como opcional, pero se perdería parte funcional del piloto. `max-instances=1` tampoco convierte el disco en persistente.
4. **P1 — Subida de fuentes sin filtro gcloud.** No existe .gcloudignore ni .gitignore en la raíz activa revisada. `.dockerignore` filtra el contexto Docker, no garantiza exclusión del archivo de fuentes que `gcloud --source .` sube antes de construir. La carpeta contiene bases y logs del piloto. Crear un paquete mínimo/filtro y revisar lista efectiva antes de subir.
5. **P1 — Cloud Run presentado erróneamente como gratis sin facturación.** «Cuenta Google existente basta», «1 GB gratis» y «arranca en <2s» no están demostrados. Google exige cuenta de facturación para Free Tier; los límites son por consumo, no una VM siempre gratis. Build, registro y red pueden tener cargos independientes. Presupuesto del usuario: gratuito; no activar facturación ni desplegar asumiendo autorización de gasto.
6. **P2 — Compose y Docker usan distintos puertos.** Imagen inicia 8080 por defecto, Compose publica y sondea 8022 y no configura PORT. Resultado previsto: servicio inaccesible y healthcheck fallido. Unificar PORT/mapeo/sondeo.
7. **P2 — Verificación acepta token vacío.** Con META_VERIFY_TOKEN vacío y hub.verify_token vacío, GET /webhook devuelve challenge 200. Reproducido con valores sintéticos. Requerir secreto no vacío; comparar de manera segura. No demuestra un bypass de firma POST, pero acepta una configuración inválida.
8. **P2 — Guía de secretos incorrecta.** Comandos `echo VALOR | gcloud ...` no solicitan entrada oculta como promete el texto: escribir valores reales ahí puede dejarlos en historial y añadir fin de línea. La cuenta por defecto usa número de proyecto, no `$PROJECT_ID-compute@...`. Descubrir cuenta real o crear una dedicada y configurar secretos por una vía revisada.

## Mejoras válidas observadas

- Dockerfile descarga el modelo antes de activar modo offline.
- Entrada Docker usa PORT y limita superficie a webhook/health.
- Compose usa META_* y directorio de estado, corrigiendo nombres antiguos y montaje de SQLite sobre archivo.
- `.dockerignore` excluye varias categorías privadas y obsoletas. Falta verificar el paquete completo y el filtro de subida del proveedor.

## Pruebas y límites

`audit_antigravity_20260916/check_entry.py` usa ASGI local y aplicación ficticia, sin modelo, bases ni red. Resultados en `entry_results.json`: health/error 200, detalle expuesto true, POST/no listo 202, token vacío 200, BackgroundTasks completadas antes de responder true. Son hallazgos reproducidos, no aprobación de esos comportamientos.

Pruebas existentes de runtime_settings, métricas y 21 regresiones ejecutadas por separado; consultar logs del directorio de auditoría. Aunque pasen, no cubren arranque/proxy/despliegue nuevo. Docker y gcloud no están disponibles mediante Get-Command en esta sesión; no se construyó imagen ni verificó servicio remoto.

## Próximo paso

Corregir estos defectos localmente y decidir alojamiento/persistencia compatible con presupuesto. Messenger continúa aplazado. No seguir las instrucciones Cloud Run como receta aprobada. No presentar cambios en documentación como despliegue terminado.

Fuentes oficiales consultadas el 16/09/2026:
- https://docs.cloud.google.com/free/docs/free-cloud-features (cuenta de facturación y cuota gratuita).
- https://cloud.google.com/run/pricing (cargos por uso y costes separados de build/registro).
- https://docs.cloud.google.com/run/docs/container-contract (filesystem, startup y ejecución).
- https://docs.cloud.google.com/sdk/gcloud/reference/topic/gcloudignore (filtrado de subida).

# Despliegue de correcciones de recomendaciones — 09/10/2026

## Código y verificaciones previas

- Commit de aplicación y pruebas: `6fd6131`.
- Integración respaldada en GitHub: `61cafec`, rama `main`.
- Script existente: `actualizar_nube.bat`, sin modificaciones.
- Log de despliegue: `logs/despliegue_61cafec_20261009.log`.
- Informe local: [VALIDACION_LOCAL_Y_CORRECCIONES_00047_20261008.md](VALIDACION_LOCAL_Y_CORRECCIONES_00047_20261008.md).
- Veinte regresiones nuevas aprobadas, recorridos interactivos simulados aprobados, memoria y catálogo verificados, fuentes/índice coherentes y cierre temporal de Chroma probado. Ver el informe para los resultados de cada suite y su alcance.

Las comprobaciones locales bloquearon proveedores externos. No se modificaron tarifas, horarios, recursos ni hechos oficiales. Los históricos de septiembre y la recalificación permanecieron idénticos byte a byte.

## Servicio y estado del despliegue

Proyecto: `texeira-whatsapp-bot`. Servicio: `texeira-whatsapp`. Región: `us-central1`.

Antes del despliegue se observó `texeira-whatsapp-00047-khb` con 100 % del tráfico. El script conserva `min-instances=0`, `max-instances=2`, memoria `2Gi` y CPU boost; no se cambiaron secretos ni proveedor.

**Despliegue completado y verificado:** revisión `texeira-whatsapp-00048-mvd`, con `latestCreatedRevisionName = latestReadyRevisionName` y **100 % del tráfico**. El proceso del script terminó con código 0.

Cloud Build `71769e58-221e-49b9-a6be-c68afac3532c`: `SUCCESS`. Inicio `2026-10-09T06:49:41.588858119Z`; fin `2026-10-09T07:06:12.036802Z` (aproximadamente 16 min 30 s). Digest de imagen: `sha256:6f8fbc6484025ce12e239760d05cd5104ae5e22d79960ad08a131a6e9f9b73d5`. Log consultado: `logs/cloudbuild_71769e58_20261009.log`.

Cloud Run informó `Ready=True` el `2026-10-09T07:10:44.634806Z`. Sus condiciones registraron importación del contenedor en 3 min 19 s y contenedores saludables en 57,47 s para **este despliegue**; no son garantías de disponibilidad ni límites de arranque para futuras peticiones.

Recursos leídos del servicio: CPU `1`, memoria `2Gi`, máximo de revisión `2`, CPU boost activo. Se mantuvo `--min-instances 0` en el script (la anotación de mínimo no aparece cuando se utiliza el valor predeterminado cero).

URL canónica: [servicio desplegado](https://texeira-whatsapp-1038134693816.us-central1.run.app). URL adicional leída del servicio: `https://texeira-whatsapp-a5uzavilla-uc.a.run.app`.

## Verificación posterior

`tests/verify_live_deployment.py` terminó con código 0. Evidencia en `logs/verificacion_api_00048_20261009.log`:

- `/health`: HTTP 200 y `{"status":"ok"}`.
- `/`: HTTP 200, `status=running`, versión declarada `2.0.0-tesis`.
- `/dashboard`: HTTP 401 sin credenciales y HTTP 200 con autenticación.
- «ayuda» y «qué tours tienen»: HTTP 200 mediante `/test-chat`, sin teléfonos ni imágenes no solicitadas según las aserciones del script.
- Neon: dos interacciones y cuatro turnos correspondientes únicamente al alias sintético de esa prueba. Esos datos se eliminaron al terminar; no se eliminaron conversaciones de clientes.

`tests/verify_panels_readonly.py` terminó con código 0. Evidencia en `logs/verificacion_paneles_00048_20261009.log`: `/handoffs`, `/catalogo`, `/dashboard` y `/operational-metrics` devolvieron 401 sin credenciales y 200 autenticados, con navegación administrativa y sus marcadores HTML. Es una comprobación de acceso y markup; no acredita todas las acciones de los paneles.

La verificación de salud y paneles no demuestra corrección de todas las respuestas ni recepción en WhatsApp. Los recorridos de recomendaciones nuevos se acreditan por pruebas locales; la comprobación en el teléfono permanece pendiente.

## Continuación del piloto y límites

El usuario indicó que realizará la prueba real desde WhatsApp más tarde. El [plan de 42 casos](PLAN_VALIDACION_WHATSAPP_REVISION_00047.md) y el [registro por modalidad](REGISTRO_VALIDACION_WHATSAPP_00047.json) conservan sus nombres para mantener continuidad, pero su revisión objetivo se actualiza a `00048-mvd`. Permanecen **0/42 casos ejecutados** en ese registro. Se conservaron exactamente los casos, sus estados, sus ejecuciones vacías, la plantilla y el histórico; únicamente se actualizaron la revisión objetivo y la fecha del JSON. Las dos consultas sintéticas del smoke no se presentaron como ejecución completa de esos casos.

Al retomar, confirmar nuevamente la revisión y registrar la que atiende cada intento. No aprobar casos del teléfono mediante mocks ni mediante este despliegue.

La calidad de generación de Groq real, la entrega de imágenes y mensajes al teléfono y la atención completada por un asesor requieren evidencia específica. No hay una precisión global actual calculada; el 73,3 % histórico no corresponde a esta versión. Messenger permanece aplazado.

`min-instances=0` conserva la escala a cero en inactividad; no garantiza factura de cero ni disponibilidad 24/7. No se añadieron recursos ni servicios de pago nuevos.

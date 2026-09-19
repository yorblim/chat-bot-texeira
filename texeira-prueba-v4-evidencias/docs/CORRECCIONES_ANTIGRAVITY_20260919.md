# Correcciones verificadas — 19/09/2026

Complementa la revisión inicial `REVISION_ANTIGRAVITY_20260919.md`; sus hallazgos describen el estado anterior a estas correcciones.

## Cambios

- Autenticación de historiales (lectura y borrado), métricas, chat de pruebas y documentación, tanto en la entrada pública como en app y en el panel de asesores. Configuración incompleta rechaza acceso. El modo local sin credenciales queda limitado a loopback.
- Retirado el valor fijo de contraseña del Dockerfile. Cloud Run exige usuario/contraseña y PostgreSQL al arrancar. Un secreto inyectado debe sustituir la credencial publicada; el historial Git no se reescribe.
- Webhooks con adquisición atómica, estado processing/failed/completed y propietario por intento. Un lease de 900 segundos permite recuperar intentos interrumpidos; un propietario vencido no puede renovar para enviar. En curso devuelve 503; completado devuelve 200 sin volver a procesar; fallo devuelve 503 y permite reintentar. Ya no se descartan reintentos por superar dos minutos de antigüedad.
- Los IDs de deduplicación del sistema anterior se conservan como completados. No puede reconstruirse automáticamente si uno de esos mensajes antiguos falló antes de este cambio.
- Interacciones idempotentes mediante client_message_id. Cierre de conexiones, propagación de errores de commit, iteración de cursores y conflicto compatible con el índice parcial.
- Solicitud humana concurrente: INSERT con ON CONFLICT sobre el índice de solicitudes abiertas y recuperación del ticket existente; actualización condicionada al estado observado para evitar sobrescrituras entre asesores.
- Envío de fotos requiere solicitud explícita y respeta las rutas de ayuda/listado. Se probaron listas/ayuda sin fotos ni números telefónicos en la respuesta.
- Pruebas conversacionales y de deduplicación ahora devuelven exit no cero si fallan; informes de las suites ajustadas se generan en docs/ y logs en logs/.

## Verificación

14 ejecuciones satisfactorias de 13 scripts: persistencia (6 regresiones), flujo SQLite/wrapper, seguridad en entrada lista, conversación (29 comprobaciones), auditoría (21 casos), deduplicación (23 comprobaciones), handoff, métricas operativas, entrada pública, runtime, Messenger simulado, recuperación de webhook (6 regresiones) y concurrencia en SQLite **y PostgreSQL 17.10 real**. Las pruebas usan dobles de envío; no se mandaron mensajes ni se llamó al LLM.

La prueba PostgreSQL utilizó una instancia portable aislada, exclusivamente en 127.0.0.1:55439 y con datos sintéticos. Comprobó ocho solicitudes simultáneas, un único ticket abierto, ocho intentos del mismo webhook, un único propietario, recuperación de fallos y leases vencidos, inserción/reintento con RETURNING, resumen de métricas y devolución de conexiones al pool. El programa está en `tests/test_persistence_concurrency.py`; por defecto usa SQLite. Para PostgreSQL solo acepta TEST_DATABASE_URL de loopback:55439, usuario codex_test y base postgres de pruebas.

La instalación preexistente de PostgreSQL estaba incompleta. Se usó un paquete portable oficial de [EDB](https://www.enterprisedb.com/download-postgresql-binaries), proveedor enlazado por [PostgreSQL para Windows](https://www.postgresql.org/download/windows/), sin modificar la instalación ni registrar servicios. Se detuvo la instancia y se eliminaron los artefactos temporales de state/ al terminar; se conservaron los logs.

Sintaxis revisada en 66 archivos Python; `git diff --check` sin errores. Logs de ejecución: `logs/*_20260919.log`. El listado efectivo de gcloud contiene 50 archivos, incluye db_adapter.py y excluye state/, logs/, tests/, históricos y archivos .env; manifiesto en `PAQUETE_DESPLIEGUE_20260919.txt`. No se construyó una imagen Linux ni se hizo una prueba con proveedores reales.

## Integración y despliegue

Rama de trabajo: `feature/corregir-persistencia-transacciones`. Solo se modificó la carpeta activa. Las correcciones se registran mediante commit y merge, sin subir bases, secretos ni runtimes de pruebas.

La inspección de Cloud Run encontró la revisión `texeira-whatsapp-00019-nn4`, con ADMIN_PASSWORD como secreto, pero sin DATABASE_URL ni secreto de base de datos. **Despliegue pendiente de definir/configurar PostgreSQL remoto y rotar la credencial administrativa publicada.** No ejecutar el despliegue antes: la nueva versión rechaza esa configuración incompleta. El script existente mantiene min-instances=0; no se autoriza gasto ni se certifica una factura de cero.

Con la base remota configurada, crear una versión nueva de ADMIN_PASSWORD por una vía segura, ejecutar `actualizar_nube.bat` desde main respaldado y verificar healthz=200, rutas privadas sin credenciales=401, y pruebas controladas de listas/ayuda. El corte a PostgreSQL no migra automáticamente historiales ni métricas SQLite previos; cualquier dato del piloto que deba conservarse requiere respaldo/importación antes del corte.

## Límite de entrega

La recuperación depende de reintentos de Meta; no existe un trabajador autónomo que reproduzca mensajes si el proveedor deja de reintentar. Una caída después de que Meta acepte un envío y antes de registrar completed sigue siendo una ventana de entrega incierta: no se afirma entrega exactamente una vez. Las métricas cuentan intentos; aceptación de API no demuestra entrega al teléfono ni resolución real.

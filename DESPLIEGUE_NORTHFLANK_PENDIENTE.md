# Despliegue pendiente — presupuesto cero

Actualización: 16/09/2026. Usuario: «no quiero pagar nada». No activar cuentas de facturación, pruebas que puedan generar cargos ni servicios pagados. Messenger aplazado.

## Estado real

No hay despliegue remoto verificado. Northflank tiene un proyecto texeira-bot en US Central; la capacidad gratuita suficiente para este bot no quedó demostrada en esta conversación. Cloud Run no está aprobado ni es una solución sin cuenta de facturación. Se retiraron de esta guía los comandos de despliegue y secretos incorrectos. La copia anterior está en texeira-prueba-v4-evidencias/audit_fixes_20260916/.

## Correcciones locales

- Entrada pública falla el arranque si no puede cargar la configuración/RAG.
- /healthz devuelve 503 sin detalles internos cuando no está lista. POST no disponible devuelve 503 y no simula recepción exitosa.
- Handshake requiere token no vacío; firma POST sigue en app.py.
- Proxy transmite el ACK sin retenerlo hasta finalizar BackgroundTasks.
- Cloud Run rechazado explícitamente: el trabajo después del ACK requiere CPU continua; todavía no hay cola durable.
- Compose fija PORT=8022, publica ese puerto y usa el mismo en salud; volumen state-data para SQLite en Docker local/VPS.
- .dockerignore y .gcloudignore permiten solo código activo, cuatro JSON de catálogo y el índice vigente. Antes de subir verificar lista efectiva de archivos con la herramienta del proveedor.

## Límite que aún requiere resolver

Un volumen Docker solo persiste donde exista realmente ese volumen; no hace persistente un plan de nube efímero. Para desplegar necesitamos recursos gratuitos comprobados, CPU continua y almacenamiento persistente, o diseñar/probar una alternativa gratuita de cola y almacenamiento. No sustituir la base ni quitar RAG para encajar en una cuota sin explicar alcance y validar resultados.

El procesamiento actual usa BackgroundTasks en memoria: un cierre abrupto tras el ACK puede perder trabajo. Esta corrección elimina el retraso del proxy, pero no agrega una cola durable ni garantiza entrega exactamente una vez. Probar reinicios y recuperación antes de declarar el piloto estable.

## Antes de publicar

1. Confirmar recursos, condiciones de registro y persistencia de una opción sin cobros. No prometer 24/7.
2. Construir imagen y probar memoria, arranque, puerto, firma, ACK y persistencia. Docker no estaba disponible localmente en la auditoría; no se afirma build exitoso.
3. Introducir credenciales mediante gestor protegido sin pegarlas en historial de terminal. No subir .env ni bases del piloto.
4. Usar únicamente whatsapp_entry:app como entrada pública. Mantener paneles privados.
5. Verificar token Meta, URL HTTPS y suscripción messages; probar con los tres destinatarios existentes y PC apagado.
6. Documentar respaldo y actualizaciones. Mantener Groq dentro de su cuota; no consumir consultas de evaluación adicionales sin autorización.

Referencias de las limitaciones Cloud Run: https://docs.cloud.google.com/free/docs/free-cloud-features y https://docs.cloud.google.com/run/docs/container-contract . Cloud Run descartado para la configuración actual y presupuesto indicado.

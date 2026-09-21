# Preparación del piloto con PostgreSQL

Se continúa la rama `feature/despliegue-piloto-secretos-explicitos` iniciada por Gemini.
Su commit fdb5dc6 fija `DATABASE_URL:1` y `ADMIN_PASSWORD:2` en el script de despliegue.
La cuenta de servicio de Cloud Run ya tiene `roles/secretmanager.secretAccessor`
sobre DATABASE_URL. No se incluyen valores de secretos en este documento.

La revisión detectó que faltaba copiar `conversation_memory.py` en el Dockerfile,
aunque ya figuraba en las listas permitidas. Se incorpora al contenedor para
evitar un error de importación al arrancar.

Validación previa a integración: memoria 8/8, conversación 29/29, auditoría 21/21,
comprobación del empaquetado, referencias de secretos y `min-instances=0`.
La escala a cero permite reducir consumo; no garantiza una factura de cero.

Revisión anterior al despliegue: `texeira-whatsapp-00019-nn4`, con 100% del tráfico.
Si la nueva revisión falla la validación, esta revisión permite restaurar el
tráfico. Mantener habilitadas las versiones previas de secretos durante la prueba.
Después del despliegue se comprobarán salud, autenticación, acceso a PostgreSQL,
historial por API y respuestas de ayuda/listas sin imágenes ni teléfonos no pedidos.

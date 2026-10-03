# Verificación independiente de revisión 00040

Fecha local: 2026-10-01 (America/Lima).

## Confirmado por consultas de lectura

- Rama local main, aplicación integrada 01927ca, HEAD documental f13fa21. Antes de crear este informe, árbol limpio y referencias locales origin/main y gitlab/main iguales a HEAD; no se realizó fetch ni se comprobó de nuevo el servidor remoto Git.
- Cloud Run latestCreated y latestReady: texeira-whatsapp-00040-xwc; 100% del tráfico. maxScale=2 y startup-cpu-boost=true.
- GET /health desde PowerShell agotó 30 segundos. Reintento con curl: HTTP 200, cuerpo {"status":"ok"}, tiempo cliente 11.322345 segundos.
- Cloud Logging de /health en esa revisión muestra HTTP 200, incluida una petición con latencia de 54.990494993 segundos y otra de 0.003556100 segundos. No se determinó la causa del tiempo inicial. No acredita disponibilidad ininterrumpida ni rendimiento de WhatsApp.

## Precisiones del reporte

- test_whatsapp_flow_polish.py contiene 13 pruebas en el código actual; el informe de despliegue consigna 11. Las 13 ya fueron ejecutadas independientemente con resultado OK al revisar 01927ca en el turno anterior; no se repitieron suites locales hoy.
- min-instances=0 establece escala a cero; no garantiza factura total cero.
- No se repitieron checks autenticados de paneles ni se enviaron mensajes WhatsApp. La verificación de cuatro paneles corresponde al reporte del despliegue.

## Siguiente paso

Prueba manual desde un número autorizado al bot +1 555 205 3249: saludo y categorías, seleccionar un tour de páginas posteriores y consultar su tarifa, Humantay seguido por altitud/dificultad, foto existente e inexistente, solicitud de atención con tour/contexto y repetición sin duplicar. Verificar ticket en panel con coordinación del asesor. No confirmar reserva comercial real ni enviar respuesta al cliente desde esta revisión.

La preparación técnica permite iniciar esta prueba. La entrega y continuidad de conversación en WhatsApp siguen pendientes de comprobación en el teléfono.

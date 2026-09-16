# Estado actualizado — 15 de septiembre de 2026

**Punto de reanudación vigente:** consultar `CONTINUAR_AGENTE.md` y `BITACORA_AVANCES.md`. La muestra Groq está pendiente: el evaluador falló antes de llamar al proveedor, fue corregido y la ejecución posterior fue rechazada por revisión automática. Se pidió una nueva autorización explícita; aún no recibida. No contar la salida inválida como evaluación real. Los párrafos siguientes conservan el historial y pueden describir procesos, URLs y pendientes ya superados.

Revisión Antigravity: mejoras de inglés comprobadas; corregida duración inglesa fijada a 4 días, ampliadas traducciones de inclusiones y respuesta humana en inglés. 16/16 casos ES/EN, prueba de cantidades, pruebas de solicitudes y 21/21 regresiones PASS. Sin Groq ni mensajes externos. Fuentes sin cambios. Informe vigente: texeira-prueba-v4-evidencias/REVISION_ANTIGRAVITY_20260915.md. Los estados de procesos y túneles del 14 de septiembre más abajo son históricos; no asumir que siguen activos.

**Métricas operativas activadas:** panel http://127.0.0.1:8023/operational-metrics. Tabla nueva operational_events en trial_logs.db; distingue procesamiento, aceptación API, fallo de envío y fallo de procesamiento. Los errores permanecen en el denominador; solicitudes únicas WhatsApp por estado. No presenta aceptación API como entrega o resolución validada. Históricos sin reconstrucción. Detalles y limitaciones en METRICAS_OPERATIVAS.md dentro de v4. Pruebas operativas, humanas y 21 casos de regresión PASS, sin LLM ni mensajes externos. Procesos actuales: WhatsApp 30088, asesores 29716; logs wa_metrics y advisor_metrics. Avisos al WhatsApp del asesor siguen aplazados por decisión del usuario.

**Etapa de atención humana, parte local implementada:** escribir `asesor` crea una solicitud persistente en human_requests.db, con el contexto reciente. El mensaje confirma registro pendiente, nunca atención completada. Hay una solicitud abierta por usuario/canal; el panel permite tomarla y cerrarla con asesor y resultado. `escalated_to_human` ahora representa registro en la cola, no notificación enviada ni atención terminada; la evaluación debe distinguir estos eventos. El panel está en http://127.0.0.1:8023/handoffs y no se publica mediante whatsapp_entry. WhatsApp PID 30620, panel PID 29964. Nuevos logs wa_handoff.out.log/wa_handoff.err.log, advisor.out.log/advisor.err.log.

Validación: test_handoff.py PASS (base temporal, estados, duplicados concurrentes, separación de canales, CSRF, panel no público); regresión de 21 casos PASS después del aviso para solicitar asesor. Ningún mensaje al asesor se envió. Falta confirmar el número del asesor y autorización para compartir consulta/contacto, configurar el canal WhatsApp solicitado por el usuario y ejecutar prueba real de solicitud y atención. La parte de avisos externos NO está implementada aún. Respaldo de código anterior en audit_handoff_backup.

**Conversación real comprobada:** el usuario recibió la respuesta de Machu Picchu en tren. Logs wa_renovado: una entrada, ruta evidence_includes, envío Meta HTTP 200. Esto comprueba el flujo WhatsApp de respuesta determinista, no una evaluación generativa completa. Se corrigió la presentación en verified_routes.py: equivalencias de tren y entradas sin repetición, redacción legible, conservando datos y fuentes. Regresión actualizada: 21 casos PASS, sin API. Servidor reiniciado PID 6356; logs vigentes wa_formato.out.log/wa_formato.err.log. La nueva presentación aún requiere observación en el teléfono; los archivos de fuentes y el índice no cambiaron.

**Última actualización: token renovado y servidor reiniciado.** Meta devolvió HTTP 200 y confirmó el número de prueba. Se reemplazó el proceso WhatsApp 23016 por 30680, con nueva carga del .env. Verificación local correcta y túnel público accesible (403 sin credenciales, esperado). Logs actuales: `wa_renovado.out.log` y `wa_renovado.err.log`. Evidencia: `VERIFICACION_REINICIO.json`. Falta un nuevo mensaje del usuario para confirmar la respuesta con esta credencial; no reenviar automáticamente mensajes antiguos.

**Diagnóstico posterior de falta de respuesta:** procesos Python 23016 y Cloudflare 20760 activos; webhook local y público responden 403 sin autenticación (esperado). El registro muestra un mensaje entrante procesado por la ruta social y un intento de respuesta rechazado con HTTP 401. Consulta independiente con el token actual del .env: HTTP 401, código 190, subcódigo 463. La conectividad entrante está demostrada; la salida está bloqueada por credencial rechazada. Renovar META_ACCESS_TOKEN y reiniciar el servidor 8022 para cargarlo antes de repetir la prueba. No se enviaron mensajes adicionales desde herramientas.

**Última verificación (19:35 UTC): callback guardado y activo en Meta.** El túnel anterior desapareció (Cloudflare: Tunnel not found). Se reinició únicamente su proceso; nuevo PID 20760. Callback vigente: `https://usb-objects-interview-poetry.trycloudflare.com/webhook`. Meta aceptó la actualización por API (HTTP 200, success=true); una lectura posterior confirmó la URL persistida, active=true y messages suscrito. Evidencia: `VERIFICACION_CALLBACK_20260914.json`. Falta comprobar una conversación real enviada por el usuario desde un número de prueba autorizado. Las URLs anteriores de este documento son históricas.

Último avance: con autorización explícita del usuario, se abrió Cloudflare hacia 8022 (PID 25964). URL nueva: `https://discover-namespace-freeware-photos.trycloudflare.com/webhook`. Comprobaciones externas: webhook sin autenticación devuelve 403; dashboard devuelve 404. La URL se ingresó en Meta, pero falta guardar: Meta vació el token de verificación y se pidió al usuario ingresar META_VERIFY_TOKEN directamente allí. No está confirmado el nuevo callback ni el flujo real de mensajes aún. El túnel es temporal y depende del PC encendido.

Organización: 43 archivos antiguos archivados sin borrar en `texeira-prueba-v4-evidencias/historico/20260914`; mapa en PLAN_ORGANIZACION_20260914.json. LEEME_PRIMERO.md identifica la versión activa y pruebas verificadas. No se movieron bases, índices, credenciales ni versiones completas. Los siete módulos activos comparados conservaron sus hashes.

Actualización posterior: el usuario renovó el token. Meta respondió HTTP 200 y se confirmó que corresponde al número de prueba +1 555 205 3249. Se inició el servidor WhatsApp local (PID 23016, puerto 8022). En Meta, el campo `messages` está suscrito y el callback sigue en `https://institution-remote-unlike-jones.trycloudflare.com/webhook`. La revisión automática bloqueó iniciar un nuevo túnel Cloudflare por requerir autorización explícita para el tránsito de mensajes por ese proveedor. No se abrió el túnel ni se cambió el callback. Sigue pendiente la prueba de extremo a extremo. El bloqueo por token descrito más abajo quedó resuelto.

Versión: `texeira-prueba-v4-evidencias`. Índice activo verificado: **`chroma_v4_evidencias_db`**. La referencia al índice del 12 de septiembre, más abajo, es histórica.

Etapa 1 verificada: 21 casos de regresión local y cuatro búsquedas del retriever aprobados. RRF60/top5/máximo dos fragmentos por tour. Los 20 documentos y metadatos almacenados en Chroma coinciden exactamente con los generados desde las fuentes actuales; sus hashes también coinciden. No fue necesario restaurar el índice.

Evidencia: `texeira-prueba-v4-evidencias/ESTADO_VERIFICADO_20260914.json`, `AUDIT_TEST_RESULTS.json`, `AUDIT_RETRIEVAL_RESULTS.json` y `VERIFICACION_INDICE_20260914.json`. Snapshot de archivos y resultados sin credenciales: `audit_snapshot_20260914/` dentro de v4. No sustituye un repositorio Git ni una copia completa del entorno.

**Etapa 2 bloqueada por credencial:** las variables de Meta están presentes, pero una consulta de solo lectura del número devolvió HTTP 401, código 190/subcódigo 463. Resultado: `VERIFICACION_META_20260914.json`. Se solicitó renovar únicamente META_ACCESS_TOKEN en el archivo local original y avisar sin compartir el valor. Después corresponde verificar el acceso al número, servidor, callback y flujo completo.

No se hicieron llamadas externas al LLM ni se enviaron mensajes; no se cambiaron credenciales, túneles o suscripciones de Meta. No se modificó código de la aplicación en esta etapa.

Siguen pendientes derivación humana, métricas operativas, disponibilidad, Messenger y evaluación pre/post según `AUDITORIA_TESIS_20260914.md`. Estas pruebas no certifican resultados académicos ni rendimiento generativo.

## Registro histórico — 12 de septiembre de 2026

Usar **texeira-prueba-v4-evidencias**, puerto **8021**: http://127.0.0.1:8021/chat.

Informe vigente: texeira-prueba-v4-evidencias/AUDITORIA_FINAL_20260912.md.

Resultados: 21 casos locales de endpoint, cuatro búsquedas con el retriever real local y comprobación HTTP de /chat y /test-chat. Cero llamadas externas a LLM en esta auditoría. El servidor arrancó con precarga de 25,05 s. La comprobación HTTP devolvió el bus de subida/bajada en Machu Picchu por la ruta determinista correcta.

Fuentes conciliadas: dos fotografías del folleto y dos PDF del usuario. Catálogo/evidencia activa: 19 productos/variantes documentados. Índice nuevo: chroma_audit_20260912_r2_db. Datos comerciales no publicados y horarios contradictorios siguen pendientes de la agencia.

Versiones anteriores, informes v2/v3/v4 previos e índices anteriores son históricos. No ejecutar sus scripts de evaluación como si midieran la versión actual sin revisar rutas y expectativas. No restaurar archivos .ps1 sobre .py. El respaldo exacto de esta intervención está en audit_backup_20260912 dentro de v4.

El original texeira-chatbot no fue modificado ni se integró a WhatsApp. Las pruebas locales no sustituyen una prueba generativa autorizada ni la evaluación académica con participantes.

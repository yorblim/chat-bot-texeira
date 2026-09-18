# Qué mide esta etapa

Panel: http://127.0.0.1:8023/operational-metrics. Disponible desde el panel de asesores.

Se registran mensajes de texto de WhatsApp admitidos por el webhook después de su validación y deduplicación. La tabla nueva `operational_events` vive en trial_logs.db. No modifica ni reconstruye los registros históricos.

- `processing`: el mensaje comenzó a procesarse y no tiene resultado final registrado. Puede incluir interrupciones del servidor; no asumir éxito.
- `api_accepted`: la función de envío recibió aceptación HTTP de Meta. No equivale a entrega, lectura o resolución.
- `send_failed`: la función de envío rechazó o no pudo completar el envío.
- `processing_failed`: ocurrió un error en el procesamiento. No se elimina del denominador.
- `generation_ms`: tiempo desde la lectura del webhook en el servidor hasta antes del intento de envío, incluyendo preparación y registro local.
- `response_attempt_ms`: tiempo desde ese mismo inicio hasta el resultado del intento de envío. El promedio mostrado para aceptación API utiliza solo envíos aceptados.

La aceptación API divide envíos aceptados entre todos los eventos registrados, incluidos errores y pendientes. Las consultas con límite del proveedor permanecen en el denominador. Una respuesta de fallback aceptada por Meta es un envío aceptado, no necesariamente una consulta resuelta. `model_claims_resolved` conserva la señal del bot separada; no se publica como precisión ni resolución validada.

El conteo humano distingue solicitudes únicas WhatsApp pendientes, en atención y cerradas. Cerrar exige un resultado del asesor; no acredita automáticamente satisfacción del cliente. Las solicitudes del canal test se excluyen de este panel de WhatsApp.

Todavía no se mide: entrega confirmada al teléfono, primera respuesta por conversación, precisión mediante rúbrica humana, resolución validada, disponibilidad ni atención fuera del horario real de la agencia. No usar los indicadores antiguos como sustitutos. El panel histórico /dashboard incorpora una advertencia en el código actualizado; un servidor viejo necesita reiniciarse para mostrarla.

Limitaciones: las métricas cubren los mensajes que el manejador actual admite; no representan todos los eventos de Meta, mensajes multimedia o eventos no recibidos. La persistencia no garantiza recuperación automática de trabajos interrumpidos. La base de datos y los datos históricos se conservan; no se afirma disponibilidad 24/7.

Pruebas: test_operational_metrics.py cubre webhook con aceptación, rechazo de envío y fallo interno simulados; verifica inclusión de errores, latencias, aislamiento de solicitudes locales y ausencia del endpoint en la app pública. test_handoff.py y los 21 casos de test_audit_20260912.py también pasaron. Se usaron bases temporales, sin enviar mensajes ni llamar a LLM externos. Los resultados de esas pruebas no se agregan a las métricas del piloto.

Respaldo previo: audit_metrics_backup (código y copia coherente SQLite). Al revertir código, conservar las bases actuales para no perder interacciones nuevas; no sobrescribirlas con el respaldo automáticamente.

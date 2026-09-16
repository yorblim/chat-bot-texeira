# Correcciones del despliegue — 16/09/2026

Corregidos defectos reproducidos en REVISION_ANTIGRAVITY_20260916.md:
- Startup falla si no carga configuración/RAG; no sirve tráfico aparentando estar listo.
- Salud y POST no listos: 503, sin detalles de excepción públicos.
- Token de verificación vacío rechazado, comparación segura.
- Proxy ASGI transmite respuesta/cuerpo originales inmediatamente; preserva rechazo de firma y no espera BackgroundTasks para emitir ACK.
- Shutdown ejecuta handlers del app delegado. No se crean loops secundarios para startup.
- Compose fija PORT=8022 coherente con exposición/sondeo. CMD exec permite señal al proceso.
- Filtros explícitos de subida Docker/gcloud; guía de secretos y facturación errónea retirada.
- Cloud Run/scale-to-zero bloqueado explícitamente: no es compatible con trabajo en memoria y persistencia actual. No se cambió a servicios de pago.

Pruebas locales: test_public_entry.py, test_runtime_settings.py, test_operational_metrics.py, test_handoff.py y test_audit_20260912.py (21 casos), exit=0. Logs en audit_fixes_20260916. Sin Groq, Meta ni mensajes externos.

NO resuelto: alojamiento remoto gratuito, almacenamiento remoto persistente, cola durable ante caída tras ACK, construcción/consumo de imagen Linux, arranque y conversación reales. Los filtros deben verificarse con listado efectivo del proveedor antes de subir. No se instaló Docker ni gcloud ni reiniciaron servidores. Presupuesto del usuario: cero; no desplegar en cuenta facturable.

# Corrección del envío desde la consola de asesores

## Problemas reproducidos

1. Cerrar un ticket pendiente intentaba enviar WhatsApp antes de devolver HTTP 400.
2. Si el proveedor devolvía False, el ticket se cerraba con HTTP 200 y `ok: true`.

## Cambio

La actualización y el envío comparten una operación: valida los campos, bloquea
el ticket, valida la transición y prepara la actualización antes de llamar al
proveedor. SQLite usa BEGIN IMMEDIATE y PostgreSQL SELECT FOR UPDATE. Un cierre
concurrente espera el bloqueo y, si el primero terminó, encuentra el ticket cerrado
y se rechaza sin un segundo envío.

False o una excepción del proveedor provocan rollback y HTTP 502 con `ok: false`.
Estado, asesor, nota y timestamp anteriores se conservan. La interfaz ya muestra
el error HTTP en lugar de éxito. Se rechazan opciones de envío no booleanas y
envíos desde tickets que no pertenecen a WhatsApp. Las notas internas no envían.

## Pruebas

- `tests/test_handoff_send_failures.py`: 7 pruebas con proveedor simulado:
  transición inválida, campos inválidos, False, excepción, repetición del cierre,
  nota interna y cierres concurrentes.
- Regresiones: envío híbrido existente, handoff, notificaciones, memoria (8),
  conversación (29) y auditoría (21), todas aprobadas.
- PostgreSQL real: prueba en esquema exclusivo `advisor_probe_<uuid>` con copia
  vacía de la estructura de requests, proveedor simulado y limpieza en finally.
  Verifica rechazo previo al envío, rollback y exclusión de cierres simultáneos.
  No se envían mensajes ni se modifican tickets reales.

## Validación en Vivo en Producción (Cloud Run)

- **PR Integrado:** PR #4 (`feature/corregir-envio-panel-asesores` fusionado a `main` en commit `d6f3ea6`).
- **Compilación Cloud Build:** `aac33065-6d7f-4976-b81a-f7d039d8d2d6` (SUCCESS).
- **Servicio y Revisión Activa:** `texeira-whatsapp` en `texeira-whatsapp-00023-rp9` (recibiendo el 100% del tráfico).
- **Consumo y Escala a Cero:** El servicio opera con `min-instances = 0`, lo que reduce a cero las instancias activas y el costo de cómputo en reposo cuando no hay tráfico entrante. Esto optimiza el consumo, aunque no garantiza costo $0 absoluto, ya que persisten cargos variables por peticiones atendidas, ancho de banda saliente, consultas a Secret Manager y artefactos almacenados.
- **Script de Auditoría en Vivo:** `tests/test_handoff_pr4_cloudrun.py` (Aprobado al 100%):
  - Salud (`/health` HTTP 200) y protección anónima (`/handoffs` HTTP 401).
  - Carga de consola con Basic Auth y extracción de token anti-CSRF.
  - Generación de ticket ante derivación humana por `/test-chat`.
  - Rechazo de actualización sin token CSRF (HTTP 403).
  - Rechazo de transición prematura `pending` $\to$ `closed` sin tomar caso (HTTP 400).
  - Toma de ticket a `in_progress` (HTTP 200).
  - Rechazo de parámetro de envío no booleano `send_to_customer='false'` (HTTP 400).
  - Cierre formal con nota interna y sin despacho a cliente (`ok: true`, `message_sent: false`).
  - Bloqueo de doble cierre sobre ticket ya cerrado (HTTP 400).
  - Verificación de persistencia final de estado en `/handoffs/data` (estado `closed`).
  - **Higiene y Limpieza en `finally`:** La prueba implementa un bloque de limpieza en `finally` para purgar de Neon PostgreSQL los registros sintéticos creados (`requests`, `interactions`, `conversation_memory`) bajo el identificador de prueba.

## Límites

1. **Simulación vs. Entrega Real en Producción:**
   El comportamiento ante fallos del proveedor de mensajería (rollback atómico y HTTP 502 ante excepciones o respuesta `False`) fue verificado mediante simulación controlada (`tests/test_handoff_send_failures.py`). En la validación en vivo sobre Cloud Run se operó mediante nota interna (`send_to_customer=False`), ya que no se indujeron fallos deliberados en la infraestructura productiva de Meta. Esta comprobación es válida para asegurar la integridad de la máquina de estados y las transacciones, pero no equivale a una validación de entrega de mensajes a terminales móviles reales de WhatsApp.
2. **Incertidumbre de Red Externa:**
   La aceptación de Meta no equivale a entrega al teléfono del usuario. Una interrupción de red puede dejar el resultado externo incierto; por ello, la interfaz solicita comprobar la entrega antes de reintentar y no realiza reintentos automáticos no supervisados.
3. **Consistencia Exactamente-Una-Vez:**
   Un fallo del commit posterior a la aceptación externa tampoco permite garantizar envío exactamente una vez sin un mecanismo de conciliación asíncrona persistente con el proveedor.
4. **Concurrencia:**
   La transacción mantiene un bloqueo durante la llamada al proveedor (con timeout estricto); en SQLite bloquea escrituras concurrentes, mientras que en PostgreSQL utiliza aislamiento a nivel de fila (`SELECT ... FOR UPDATE`).



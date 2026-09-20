# Entrega 2: memoria conversacional persistente

## Alcance

El contexto reciente se almacena en `conversation_memory`, separado por `user_id`,
en PostgreSQL si está configurada `DATABASE_URL` o en el archivo SQLite configurado.
Conserva hasta 20 mensajes por usuario (10 pares pregunta/respuesta), incluyendo
rol, contenido y timestamp. No migra conversaciones que solo existían en RAM.

Las operaciones de escritura usan transacciones: `BEGIN IMMEDIATE` en SQLite y
bloqueo de la fila del usuario con `FOR UPDATE` en PostgreSQL. La inserción inicial
usa `ON CONFLICT DO NOTHING`. Cada par de la ruta verificada se guarda junto, sin
reescribir una copia antigua del historial. Las respuestas intermedias del RAG se
suprimen mediante un ContextVar y se registra la respuesta definitiva. Atención
humana actualiza su texto final en la base. Los fallos de persistencia se propagan;
no se sustituye silenciosamente la base por memoria RAM.

Se incluye el nuevo módulo en las listas permitidas de Docker y Cloud Build.
El esquema PostgreSQL se crea de forma aditiva durante la inicialización existente;
SQLite crea la tabla cuando se usa. No se cambian las rutas HTTP ni su autenticación.

## Verificación realizada

- `tests/test_conversation_memory.py`: 8 pruebas aprobadas. Nuevo proceso,
  aislamiento, borrado, límite de retención, 30 escritores concurrentes,
  rollback, lecturas desacopladas, suspensión de respuestas intermedias,
  integración de rutas y texto final de atención humana.
- `tests/test_conversation_memory_postgres.py`: PASS contra Neon con un esquema
  exclusivo generado para la prueba. Verifica 12 turnos concurrentes, nuevas
  conexiones, aislamiento, límite, borrado y rollback. El esquema se elimina
  al finalizar. No se modifican tablas existentes del piloto.
- Secreto de PostgreSQL recuperado de Secret Manager solo en memoria; ningún
  valor de credencial se registra en esta evidencia.
- Regresiones aprobadas: SSL/autenticación (22), persistencia (6), persistencia
  universal, concurrencia, recuperación de webhooks, conversación (29), auditoría
  (21), deduplicación, handoff, notificación de asesores, métricas operativas,
  entrada pública y revisión final local.
- La revisión final local tenía una ruta obsoleta al JSON de evaluación; se
  corrigió para resolver `docs/evaluaciones` desde la ubicación del test.
- El evaluador simulado usa ahora una base temporal en lugar de reemplazar el
  repositorio de memoria por un diccionario.

## Límites y despliegue

La prueba PostgreSQL usa el repositorio y el adaptador SQL en un esquema aislado;
no constituye una prueba de reinicio de Cloud Run ni de entrega real por WhatsApp.
Queda esa verificación para el despliegue posterior a la revisión del PR.
La persistencia serializa las escrituras; no serializa toda la generación de
respuestas de dos solicitudes simultáneas del mismo usuario. La retención está
acotada por cantidad de mensajes, no por antigüedad ni número total de usuarios.
SQLite solo conserva datos si se conserva su archivo: en Cloud Run se requiere
PostgreSQL para resistir el reemplazo del contenedor.

No se realizó merge ni despliegue. La tabla nueva es aditiva; volver a la versión
anterior del código no exige eliminarla.

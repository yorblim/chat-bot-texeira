# Revisión independiente del arreglo del webhook 2a6d01d

Fecha de cierre de revisión: 2026-10-03 (Lima).
Carpeta activa: `texeira-prueba-v4-evidencias`.
Commit local y referencia local de `origin/main` consultados: `2a6d01d`.

## Dictamen

La corrección resuelve el caso probado de system seguido de texto y evita el fallback inmediato tras un timeout del envío interactivo. Las 13 pruebas de la suite citada y las 6 de recuperación pasaron al volver a ejecutarlas.

Sin embargo, no basta para cerrar el incidente: dos nuevas regresiones integradas fallan. El envío con resultado incierto sigue siendo repetible al reentregar el webhook, y los mensajes de distintos remitentes de un mismo lote se atribuyen al primer contacto.

La explicación de la cita del cliente de WhatsApp es compatible con las capturas anteriores. No se reconsultó la traza completa del incidente: el informe de Antigravity contiene extractos con identificadores abreviados, no una correlación completa que permita atribuir esta revisión a ese incidente concreto. Los fallos descritos aquí se reprodujeron exclusivamente con entradas sintéticas y proveedores simulados.

## P1: resultado de envío incierto tratado como fallo reintentable

Recorrido actual:

1. Meta puede aceptar el envío interactivo y perderse la respuesta HTTP. En el test, el proveedor simulado registra la aceptación y después lanza `httpx.ReadTimeout`.
2. `src/services/whatsapp.py:258` devuelve `False` sin fallback inmediato: ese cambio es correcto para impedir un segundo envío dentro de la misma llamada.
3. `app.py:2773` usa ese booleano para marcar el recibo como `failed`, sin distinguir entrega rechazada de resultado desconocido.
4. `app.py:2807` devuelve HTTP 503. La reentrega del mismo ID puede reclamar el recibo fallido mediante `database.py:424`.
5. Se ejecuta otra llamada de salida interactiva.

Reproducción integrada: primer webhook 503, reentrega 200, dos aceptaciones simuladas del proveedor para el mismo ID entrante. La prueba falla con `2 != 1`. Esto prueba el riesgo con aceptación previa al timeout; no significa que todos los timeouts hayan entregado un mensaje.

Corrección requerida: distinguir y persistir **aceptado**, **rechazado** y **resultado incierto** en el recorrido completo, incluidos recibos y métricas. Establecer una política explícita de conciliación o revisión de los resultados inciertos, evitando reenvíos automáticos ciegos. No solucionar esto devolviendo éxito ficticio o marcando una entrega desconocida como aceptada/resuelta. Los errores previos al envío que permitan un reintento seguro deben conservar su recuperación.

## P1 condicionado a lote multiusuario: destinatario e historial incorrectos

`app.py:2351` selecciona `contacts[0]` una vez para el value y lo adjunta a todos los mensajes (`:2355`). Después `:2433-2436` prioriza ese contacto sobre `msg.from`.

Reproducción sintética firmada:

- Contactos A y B: `51900000001`, `51900000002`.
- Dos mensajes de texto, uno con `from=A` y otro con `from=B`.
- Resultado HTTP 200.
- Destinos reales capturados en el mock: `[A, A]`.
- Usuarios pasados a RAG/historial: `[A, A]`.

La prueba esperaba `[A, B]` y falla. No se afirma que ese lote se haya recibido en producción. El manejador que admite arrays debe conservar la asociación por mensaje y no inferir el remitente por la posición del primer contacto.

Corrección requerida: asociar cada mensaje con su propio remitente y el contacto correspondiente, respetando teléfono y BSUID cuando estén presentes. Un contacto no relacionado no debe sustituir al remitente ni mezclarse con su memoria. Verificar además lotes distribuidos entre varios entry/change, para no reutilizar contactos o metadatos de otra unidad.

## Observación adicional: fallback de todos los 4xx

La rama `src/services/whatsapp.py:245` aplica fallback a cualquier 4xx, incluyendo credenciales inválidas, permisos y límites. La prueba actual sólo representa un 400 de formato. Cambiar a texto no arregla un token inválido, un límite ni una ventana comercial caducada. Limitar el fallback a errores cuyo motivo confirme que cambiar el formato puede resolverlo; conservar códigos y causas para decidir la recuperación apropiada.

## Evidencia y alcance

| Suite reejecutada | Resultado |
| --- | --- |
| `test_review_anti_echo_20261002.py` | 13 PASS |
| `test_webhook_recovery.py` | 6 PASS |
| `test_review_webhook_2a6d01d.py` (nueva e independiente) | 2 FAIL |

Las 13 pruebas incluyen 7 casos propios y 6 heredados de la suite de recuperación. Su resultado es válido, pero no equivale a 13 escenarios nuevos de lotes ni acredita los dos casos integrados añadidos aquí. No se reejecutaron las otras cuatro suites del resumen de Antigravity en esta revisión.

Todos los tests utilizaron el ejecutor aislado, SQLite temporal, modelo simulado y transporte simulado. No hubo mensajes reales, consumo de Groq ni escrituras a la base de producción.

```powershell
python tests/run_isolated.py test_review_anti_echo_20261002.py
python tests/run_isolated.py test_webhook_recovery.py
python tests/run_isolated.py test_review_webhook_2a6d01d.py
```

Logs:

- `logs/review_2a6d01d_anti_echo.log`
- `logs/review_2a6d01d_recovery.log`
- `logs/review_2a6d01d_integrated.log`

## Estado del despliegue observado

La consulta de solo lectura a Cloud Run durante esta revisión devolvió `latestCreatedRevisionName = latestReadyRevisionName = texeira-whatsapp-00041-bmx`, con 100% de tráfico. No confirmó todavía una nueva revisión del arreglo. Esta observación no demuestra que la construcción en segundo plano haya fallado; puede seguir en curso.

No se desplegó, detuvo ni modificó ningún servicio. La aplicación de Antigravity se mantuvo intacta; se añadió únicamente la prueba integrada y este documento.

## Encargo de cierre para Antigravity

Antes de cerrar el arreglo o pasar a las vistas, revisa este informe y ejecuta `test_review_webhook_2a6d01d.py`. Corrige en un mismo cambio la política de envíos inciertos y la asociación de remitentes/contactos por mensaje, y revisa los errores de Meta permitidos para fallback. Conserva recuperación de fallos seguros, deduplicación de mensajes completados, firmas, idiomas, catálogo y reservas.

Prueba timeout después de aceptación seguido de reentrega; dos usuarios en un lote; múltiples entry/change; system y from_me junto a texto; estados junto a mensajes; y éxito parcial del lote seguido de reentrega. No duplicar mensajes completados ni atribuir una conversación al usuario equivocado. Documenta los resultados inciertos sin contarlos como entregas o consultas resueltas.

Ejecuta las regresiones locales relevantes, respalda e integra mediante `feature/...` según `AGENTS.md`, y comprueba revisión, tráfico y comportamiento real tras desplegar. `/health` por sí solo no valida estas garantías.

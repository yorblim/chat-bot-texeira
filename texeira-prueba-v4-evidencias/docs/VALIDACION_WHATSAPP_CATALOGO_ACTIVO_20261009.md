# Observación real de WhatsApp: recomendación y catálogo activo

Fecha de revisión: 09/10/2026, America/Lima.

## Evidencia recibida

El usuario envió una captura de WhatsApp con la consulta:

> Recomiéndame un tour de un día no quiero hacer caminata

Respuesta visible:

> No puedo confirmar opciones activas que coincidan con esas preferencias con la información disponible en el catálogo. ¿Quieres ajustar tus preferencias o confirmar los datos que faltan con un asesor?

Se observan los botones «Ver Tours» y «Consultar asesor». La captura muestra 2:23 AM y «Hoy», sin fecha explícita ni medida de latencia. Copia local: `logs/whatsapp_recomendacion_sin_coincidencias_20261009.png`.

## Comprobación independiente

Se consultó Cloud Run mediante `gcloud run services describe`: revisión lista `texeira-whatsapp-00048-mvd`, con 100% del tráfico en el momento de la revisión. Esto acredita el estado consultado, no identifica por sí solo el contenedor que atendió la captura.

Se leyó `GET /api/catalog/tours?all=1` en el origen canónico del bot, usando autenticación limitada a ese origen y sin redirecciones. No se modificó el catálogo ni se expusieron credenciales. La respuesta contenía 19 tours; 3 activos y 16 inactivos.

| Tour activo | Identificador | Duración vigente |
| --- | --- | --- |
| Camino Inca Clásico 4D/3N | `camino-inka` | 4 días / 3 noches |
| Inka Jungle to Machu Picchu | `inka-jungle` | 4 días / 3 noches |
| Maras - Moray | `maras-moray` | Medio día |

Instantánea de los campos consultados: `logs/catalogo_recomendacion_00048_20261009.json`. Los archivos de `logs/` son evidencia local; esta tabla deja los hallazgos relevantes versionados.

La inspección de `verified_routes.py` y una revisión independiente de sus funciones confirmaron que el texto reconoce `un día` como preferencia de un día y `no quiero hacer caminata` como rechazo de senderismo. El singular «caminata» no es la causa de esta respuesta.

El filtro actual exige que la duración documentada coincida con la solicitada. Ninguno de los tres tours activos satisface un día; por ello no hay candidatos. Los dos productos de cuatro días también tienen perfil de senderismo. Los tours de un día del catálogo, como Valle Sagrado o Machu Picchu en Tren, se encuentran desactivados y no deben ofrecerse.

## Resultado y decisión del usuario

La respuesta observada es coherente con la oferta activa y no permite atribuir un defecto de interpretación a este caso. El bot no completó una recomendación, pero evitó ofrecer productos desactivados o duraciones incompatibles. No se acredita con esta observación la calidad de todas las recomendaciones.

El usuario confirmó expresamente: **«Mantener solo esos tres por ahora»**. Se conserva esta restricción para la continuación. No se reactivó ningún tour ni se cambiaron datos oficiales, código o infraestructura.

Esta consulta combina dos preferencias en un mensaje y no reproduce exactamente las precondiciones ni los pasos REC-03/REC-04 del plan. Se registra como observación adicional; no se marcan esos casos como aprobados, ni se calcula precisión actual. La ruta interna, intervención de recuperación/LLM, latencia y persistencia de esta interacción no se verificaron con logs del mensaje.

## Prueba de medio día: respuesta recibida

El usuario remitió una segunda captura con la consulta:

> Recomiéndame un tour de medio día, no quiero hacer caminatas.

Respuesta visible:

> 🌟 Según lo que buscas, estas son nuestras recomendaciones verificadas:
>
> · Maras - Moray (Medio día, 08:40-14:00 — salineras artesanales y terrazas agrícolas circulares).
>
> Escribe el nombre de cualquiera de ellos para ver detalles, fotos o tarifas, o escribe 👉 asesor para coordinar con nuestro equipo 😊

Los botones visibles son «Ver Tours» y «Consultar asesor». La captura muestra 2:32 a. m., sin fecha explícita ni medida de latencia. Copia local: `logs/whatsapp_recomendacion_medio_dia_20261009.png`.

El producto, la duración y el horario coinciden con la instantánea de producción obtenida en esta revisión: `maras-moray`, activo, `Medio día`, `08:40-14:00`. Es el candidato esperado entre los tres tours activos. La respuesta no ofrece productos de cuatro días ni los tours desactivados, y no contiene teléfonos o fotos no solicitados.

Resultado puntual: recomendación compatible observada en WhatsApp. No constituye aprobación de todas las recomendaciones ni acredita por sí sola el uso de RAG/LLM, la latencia o los registros internos. La consulta combina preferencias y no reproduce exactamente los casos REC-03/REC-04 del plan; continúa como observación adicional, sin modificar las aprobaciones de la matriz de 42 casos ni calcular un porcentaje de precisión.

Su clasificación como tour sin senderismo no implica ausencia absoluta de desplazamientos a pie ni una garantía de accesibilidad.

## Rechazo de la recomendación: respuesta recibida

El usuario remitió una tercera captura de la continuación en el mismo chat:

> Ninguno, dame otras opciones.

Respuesta visible:

> No quedan otras opciones verificadas con esas preferencias después de los tours que rechazaste. ¿Quieres cambiar tus preferencias o volver a ver alguna opción anterior?

Se conservan los botones «Ver Tours» y «Consultar asesor». La captura muestra envío a las 2:34 a. m. y respuesta a las 2:35 a. m.; estas marcas con precisión de minutos no permiten calcular la latencia. Copia local: `logs/whatsapp_rechazo_sin_alternativas_20261009.png`.

Resultado puntual: la respuesta reconoce el rechazo y agotamiento de alternativas compatibles con el catálogo observado, sin repetir Maras–Moray, ofrecer tours inactivos o sugerir productos de cuatro días. Ofrece cambiar las preferencias o revisar una opción previa. El comportamiento es coherente con conservar medio día y rechazo de senderismo; no se inspeccionó la memoria interna de ese mensaje.

Este recorrido contrasta rechazo y continuidad en WhatsApp, pero no replica la preparación exacta de REC-05 (`¿Qué tours me recomiendas?` → `Paisajes, tengo un día`). Se conserva como observación adicional sin aprobar por equivalencia el caso formal ni modificar el porcentaje de evaluación.

## Siguiente paso, pendiente

Enviar en el mismo chat:

> Ahora sí quiero hacer caminatas y tengo 4 días.

Debe sustituir la preferencia negativa anterior por el interés explícito en caminatas y cambiar la duración a cuatro días. Con el catálogo observado, Camino Inca e Inka Jungle son candidatos compatibles; Maras–Moray tiene medio día. El rechazo previo de una opción de medio día no debe bloquear esta petición con criterios nuevos. Comprobar la respuesta recibida antes de aprobar este cambio de preferencias.

No se requiere despliegue para este registro documental. Continúan pendientes la matriz completa del piloto, la evidencia del uso real de RAG/LLM y la evaluación humana en campo. Messenger continúa aplazado.

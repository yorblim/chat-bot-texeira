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

## Siguiente paso, pendiente

Enviar desde el mismo WhatsApp:

> Recomiéndame un tour de medio día, no quiero hacer caminatas.

Con el catálogo observado, Maras–Moray es el candidato esperado. Debe comprobarse la respuesta recibida antes de dar por aprobado el recorrido. Su clasificación como tour sin senderismo no implica ausencia absoluta de desplazamientos a pie ni una garantía de accesibilidad.

No se requiere despliegue para este registro documental. Continúan pendientes la matriz completa del piloto, la evidencia del uso real de RAG/LLM y la evaluación humana en campo. Messenger continúa aplazado.

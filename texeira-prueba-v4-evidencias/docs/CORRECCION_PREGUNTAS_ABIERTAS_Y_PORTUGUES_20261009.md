# Corrección de preguntas abiertas y continuidad en portugués

Solicitud: corregir los defectos detectados en el banco automático sin ampliar el proyecto de atención turística por WhatsApp. Rama: `feature/fix-open-questions-and-portuguese-20261009`. Base: `aa378e5`.

## Causas y comportamiento corregido

1. Una entidad mencionada bastaba para producir una ficha general. La pregunta «How should I prepare for the Inca Trail and what gear is documented?» recibía precio/horario/duración y se contaba como resuelta sin contestar la pregunta. Ahora solo un nombre de tour aislado o una petición explícita de información general produce una ficha. Preparación, equipo y comparaciones siguen hacia recuperación y generación, conservando antes las comprobaciones del catálogo activo.
2. Dos detectores de asesoría tenían vocabularios distintos. Se comparte el criterio de preguntas abiertas y comparativas entre las capas de enrutamiento. La capa histórica tampoco recaptura preguntas mixtas de preparación e inclusiones como una respuesta a un único campo.
3. «Meio dia», «não quero fazer caminhadas», «quatro dias», rechazos y otras opciones no se interpretaban de forma completa en portugués. Las recomendaciones conservan restricciones entre turnos, sustituyen una preferencia cuando el cliente la cambia explícitamente y no repiten los tours rechazados bajo los mismos criterios. Si no hay coincidencias, solicitan ajustar preferencias sin inventar alternativas ni resolver la consulta.
4. Se localizan las plantillas de recomendación, navegación, fotos, inactividad, fallos y solicitud de asesor. Los botones conservan `:pt`, la entidad original y las restricciones de longitud existentes. Una solicitud repetida conserva un solo ticket y no confirma una reserva comercial.
5. Las respuestas cortas compartidas con español, como «4 dias» o «cultura», conservan una conversación explícitamente portuguesa. El idioma resultante se utiliza en botones y registros tanto del webhook como de `/test-chat`, sin alterar variables globales por solicitud.
6. El prompt mantiene el idioma de la pregunta y exige datos del contexto. Sin recuperador o documentos no se llama al modelo. Las respuestas de ausencia de evidencia, fallos o límites del proveedor no se consideran resueltas; se incorpora la ausencia explícita de evidencia en portugués.

Los datos escritos libremente en el catálogo y los nombres propios se conservan. Estas modificaciones no certifican traducción perfecta de cualquier texto libre ni respuestas correctas en todos los idiomas. No se añaden datos turísticos ni se activan tours.

## Verificación local

- `test_open_questions_and_portuguese_20261009.py`: regresiones independientes de preguntas abiertas ES/EN/PT, comparaciones, fichas/campos simples, preferencias, rechazo, falta de evidencia y alcanzabilidad de generación. Baseline original: 13 aprobadas / 30 fallidas en 43 pruebas; después se amplió la cobertura. Datos sintéticos, recuperador vacío y generación bloqueada, salvo marcadores **no factuales** para verificar el recorrido y prompt.
- `test_portuguese_buttons_20261009.py`: etiquetas, IDs, idioma de callbacks nuevos/heredados, ambigüedad sin adivinar, navegación real del código, metadatos de `/test-chat` y fallos controlados. Transporte WhatsApp simulado.
- `test_portuguese_handoff.py`: solicitud explícita, negaciones/citas, estados, duplicados y fallo de registro, con persistencia temporal y notificaciones desactivadas.
- Banco completo de siete suites mediante `tests/run_pilot_batch.py`, además de conversación, auditoría y suites de atención humana. El banco conserva las diez exploraciones pendientes de evaluación real; no las convierte en aprobadas por pasar regresiones.

Durante la revisión se detectaron y corrigieron una colisión de idioma en «qué no está incluido» y la pérdida de fichas de peticiones generales «information about…» / «quiero saber del…». Las aserciones se conservaron. Los ensayos preliminares quedan como evidencia, no como aprobación de las fuentes finales. Algunos procesos de TestClient quedaron bloqueados en la creación del socket local de Windows dentro del sandbox; se reejecutaron con permiso para ese socket y el mismo ejecutor que bloquea conexiones externas y aísla datos.

**Resultado final:** 58/58 pruebas nuevas de preguntas/preferencias, 12/12 de botones/API y 13/13 de asesor; conversación 36/36 y auditoría 21/21. Las tres suites existentes de solicitudes/notificaciones/fallos también pasan. Banco completo: siete suites con salida 0, 138 casos estructurales aprobados, cero fallos y diez exploraciones pendientes, sobre 183 turnos. Son coberturas parcialmente solapadas: no se suman como una medición de precisión.

Informe final del banco sobre fuentes congeladas: `docs/evaluaciones/ROBUSTEZ_AUTOMATICA_20261009T214028Z_9ffa49a2.json`. Los ensayos `213113Z` (fallos luego corregidos), `213412Z` (aprobado) y `213805Z` (fuentes cambiaron durante la ejecución, no válido para cerrar) se conservan separados. La aprobación final corresponde a `214028Z`, no a una salida parcial anterior. Los registros detallados de las nuevas suites están en `logs/*_release_20261009.log`.

## Límites de la evidencia

Las pruebas demuestran enrutamiento, restricciones, idioma de plantillas, estado y continuidad. No demuestran precisión del LLM real, entrega al teléfono, disponibilidad comercial ni resolución validada por el cliente. Los marcadores de generación no son hechos turísticos. No se realizaron llamadas deliberadas a Groq/OpenAI ni envíos reales a WhatsApp durante la validación local.

Se conservan intactos los históricos de septiembre, la recalificación de 22/30 y el registro formal de WhatsApp; no se añaden aprobaciones a partir de simulaciones. La prueba física se mantiene para cuando el usuario pueda realizarla.

## Git y producción

La integración y el despliegue deben completarse después de la validación local, mediante el script existente `actualizar_nube.bat`. Mantener `min-instances=0`, `max-instances=2`, memoria `2Gi`, proveedor y secretos existentes. La escala a cero no garantiza una factura de $0.

Pendiente registrar commit, revisión activa y resultados de `/health`, paneles y dos turnos deterministas PT por API. La prueba de API utiliza un usuario sintético único y elimina solo sus interacciones y memoria en Neon; no modifica el catálogo ni solicita atención real.

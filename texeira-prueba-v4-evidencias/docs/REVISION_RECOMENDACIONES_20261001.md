# Hallazgos de piloto: recomendaciones bloqueadas y horarios de categorías

Fecha local: 2026-10-01. Código leído: 8f7c74d, main. No se modificó aplicación ni producción; no se consumió API.

## Conversación real aportada por el usuario

Después de mostrar Montaña de 7 Colores y Valle Sagrado, el usuario escribe «que tours me recomiedas», «cuales me recomienedas» y «ninguno necesito que em recomiendes». El bot responde tres veces pidiendo elegir entre ambos tours. Esto bloquea una intención general de asesoramiento.

## Causa confirmada en código

app.py, resolve_contextual_retriever_query: examina los seis mensajes recientes, incluidas respuestas del bot. Si el turno más reciente con entidades menciona dos tours, last_turn_had_multiple dispara is_ambiguous sin exigir que la consulta actual necesite identificar un tour particular. rag_chain retorna evidence_ambiguous antes de recuperar documentos o invocar el LLM. La propia aclaración vuelve a introducir dos entidades y refuerza el bloqueo.

verified_routes admite recomendaciones como consultas interpretativas, pero esta detección de ambigüedad posterior impide su ejecución. Añadir solo más variantes de «recomendar» no resolvería la política de contexto.

## Segunda inconsistencia visible

get_dynamic_cat_specs usa duración canónica de CAT_SPECS_DICT cuando falta duration. Esos valores mezclan Full Day y horarios antiguos. El render de categoría imprime ese respaldo en lugar del campo schedule vigente. La conversación muestra Montaña 04:00-18:30 y Valle Sagrado 07:00-18:30; el catálogo versionado registra 04:30-17:00 y 07:30-18:30 respectivamente. No se consultó el catálogo administrativo de producción en esta revisión.

## Corrección solicitada para el encargo existente

1. Aplicar aclaración de entidad solo cuando la intención necesita identificar un tour. Un listado emitido por el bot no equivale a selección del usuario. Recomendaciones generales, rechazo de opciones y cambio de tema deben salir de la aclaración; no repetirla incondicionalmente.
2. Para recomendaciones sin preferencias, preguntar brevemente por intereses/tiempo; al recibirlos, orientar con datos verificados de tours activos. Reutilizar LLM/RAG cuando aporta interpretación. No inventar dificultad, precios o cupos ni crear una regla por cada errata.
3. Duración y horario son campos distintos. Las categorías deben usar los campos vigentes del catálogo; sin datos, omitir o indicar por confirmar. No restaurar horarios antiguos de un texto estático.
4. Reproducir el recorrido exacto y variantes ES/EN. Mantener aclaración para referencias realmente ambiguas («fotos del otro»), preservar cambios de tour, y comprobar actualización de horario del catálogo al listado. Verificar las rutas/llamadas reales sin forzar modelo para cada clic.

Sigue pendiente el cierre del piloto real: los tests anteriores no cubrían este recorrido. Registrar el fallo como consulta pendiente/no resuelta.

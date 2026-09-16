# Plan de cierre del prototipo Texeira

## Objetivo y alcance

Terminar una versión de prueba estable, evaluada y documentada del chatbot turístico. Mantener el enfoque RAG existente. No confundir prototipo con operación comercial ni evaluación técnica con resultados académicos obtenidos con participantes.

Trabajar en C:\Users\HP\Desktop\Chat bot\texeira-prueba. El proyecto original texeira-chatbot y su conexión de WhatsApp quedan protegidos. Leer CONTINUAR_EN_OPENCODE.md y texeira-prueba/REVISION_OPENCODE.md antes de editar; consultar otros archivos solo cuando haga falta.

## Reglas de ejecución eficiente

- Continuar sobre el estado actual, comprobar cambios recientes y conservar modificaciones del usuario. No rehacer proyecto ni cambiar arquitectura, proveedor, modelo o dependencias sin una causa comprobada.
- Primero pruebas locales y dobles del proveedor. No ejecutar llamadas reales al LLM sin autorización explícita nueva del usuario. No ejecutar evaluate_ten.py live automáticamente.
- No imprimir ni copiar secretos de .env, ni enviarlos como contexto a otro modelo. No compartir bases de conversaciones. El arranque de app.py carga internamente credenciales; los tests deben sustituir get_llm antes de invocar la cadena.
- No instalar paquetes, regenerar índices, cambiar datos, desplegar ni tocar WhatsApp como parte de una corrección de indicadores.
- Preservar RRF=60, final_k=5, máximo dos fragmentos por tour. No introducir respuestas esperadas de evaluación en recuperación/prompts.
- No editar evidencias históricas ni declarar pruebas simuladas como evaluaciones de generación. Detener reintentos automáticos ante errores del proveedor.
- Mantener actualizada una lista breve de completado, pendiente y bloqueado en ESTADO_CIERRE.md. Informar con cambios, evidencia y limitaciones; no repetir el plan completo en cada turno.

## Fase 1 — Establecer el punto de partida

Leer resultados y revisar únicamente funciones afectadas. Guardar copia o diff de los archivos que se van a editar, excluyendo credenciales y bases de conversaciones. No realizar git reset ni eliminar trabajo anterior.

Referencias: trial_support.py; app.py (rag_chain, needs_escalation, endpoints y escritura de historial); review_opencode.py; REVISION_OPENCODE.json. Servidor de prueba: puerto 8020, arranque con INICIAR.ps1. Comprobar el proceso antes de reiniciar únicamente ese servidor.

Cierre: identificar versión actual y disponer de reversión de los cambios propios.

## Fase 2 — Resolver los cuatro fallos verificados

1. **Derivación real**: separar recomendación de consultar a la agencia de una transferencia ejecutada. La copia no tiene un mecanismo efectivo de asignación a asesores; no marcar escalated_to_human=true por frases o por fallback. No inventar un sistema de derivación para justificar el indicador.
2. **Información comercial pendiente**: aplicar la decisión tanto a rutas deterministas como a la ruta LLM. Pagos/adelantos, disponibilidad/reserva y cotización exacta en soles sin datos deben quedar pendientes. Una pregunta informativa sobre un rango conocido no debe pasar a pendiente solo por mencionar precio o una fuente. Definir claramente el significado del indicador, sin presentarlo como medida de exactitud factual.
3. **Contacto de la agencia**: distinguir fuentes externas de investigación de canales publicados de Texeira. Usar agency de data/provisional.json. Evitar sustituciones que funcionen solo para una frase exacta; tampoco borrar enlaces válidos cuando el usuario solicita fuentes. No inventar teléfonos, horarios ni disponibilidad del contacto.
4. **Historial coherente**: guardar la respuesta definitiva después de los ajustes. El texto recibido por el usuario y el que se usa como historial deben coincidir; evitar registrar el mismo turno dos veces. Revisar también el prefijo de prototipo añadido por el adaptador.

Mejora editorial vinculada: explicar falta de tipo de cambio/cotización sin exponer reglas internas. Responder directamente sobre reembolso, no con una frase genérica de gratuidad.

Cierre: pruebas reproducibles de los cuatro defectos pasan, sin modificar el catálogo ni ocultar errores.

## Fase 3 — Regresión local sin gasto de API

Convertir los hallazgos de review_opencode.py en comprobaciones con expectativas explícitas, conservando la evidencia anterior en otro archivo. Probar la cadena y /test-chat con recuperación y proveedor simulados, y escritura de logs simulada o base temporal. No cargar embeddings si el test no evalúa recuperación.

Casos mínimos:
- Reproducción histórica C06–C09.
- «Contacta a un asesor para consultar los detalles»: no transferencia ejecutada.
- Variante que ofrece un enlace de otro operador para contactar con Texeira: no atribuirlo a la agencia.
- Solicitud legítima de fuentes de precios: puede conservar fuentes externas claramente identificadas.
- «¿Cuál es el precio en soles de Salkantay?»: falta cotización; pendiente incluso si toma ruta determinista.
- Precio referencial conocido en USD: respuesta informativa sin falso pendiente.
- Pregunta de seguimiento: el historial contiene exactamente la respuesta final mostrada.
- Consultas equivalentes en inglés sobre pagos/reservas, para evitar controles únicamente españoles.
- Error de proveedor: no clasificarlo como respuesta correcta ni resolución autónoma.

Reutilizar test_trial.py para precios, contexto e aislamiento cuando sea pertinente. Si se prueba recuperación real, usar índice existente offline; no regenerarlo. Distinguir tests de contenido determinista de texto producido por un simulador.

Cierre: guardar comando, resultado, alcance y fecha; no afirmar que todos los idiomas o todas las preguntas funcionan por unos pocos ejemplos.

## Fase 4 — Comprobar la copia en ejecución

Reiniciar solo la copia de prueba cuando sea necesario. Confirmar precarga y HTTP 200 en /chat. El buscador tarda aproximadamente 30 segundos al arrancar, según mediciones anteriores; no prometer ese tiempo exacto. No ejecutar consultas RAG reales de manera implícita.

Entregar al usuario una secuencia corta para revisar interfaz y respuestas locales. Si se necesita verificar generación real, preparar una lista mínima de casos afectados, explicar cuántas solicitudes se harán y esperar autorización. Registrar recuperación y generación por separado si se añaden mediciones; no atribuir por diferencia tiempos de corridas distintas.

Cierre: versión verificada accesible, y claridad sobre qué se comprobó con IA real, con simulador o solo por inspección.

## Fase 5 — Evaluación y documentación técnica

Conservar EVALUACION_10_CASOS.md y evidencias previas. Crear un informe nuevo de antes/después de los casos afectados, separando contenido, indicadores, infraestructura y latencia. No sustituir el dataset original ni cambiar expectativas para ajustarlas a las respuestas. No reportar una tasa global de precisión a partir de una mezcla de pruebas deterministas y respuestas simuladas.

Si se pretende ejecutar el conjunto académico completo, revisar previamente texeira-chatbot/AGENTS.md y docs/PROJECT_STATUS.md en modo lectura. Ese conjunto tiene contratos y problemas documentados propios; su ejecución y consumo de API requieren autorización. No mezclar resultados de catálogo/proveedor distintos con el baseline original.

Documentar arquitectura realmente utilizada: respuestas locales + recuperación BM25/vectorial con RRF + proveedor configurado. No afirmar tecnologías o experimentos no realizados. Incluir limitaciones: políticas y disponibilidad no conectadas, estimaciones, contexto, detección de idioma y falta de derivación real.

Cierre: informe trazable a archivos de evidencia, con pendientes explícitos.

## Fase 6 — Validación de datos con la agencia

Preparar una ficha para que el usuario confirme con la agencia: tours/variantes ofrecidos, tarifas y moneda, inclusiones/exclusiones, duración, reservas, pagos/adelantos, cancelación, descuentos, seguro y contactos. No contactar a terceros automáticamente.

Mientras no haya confirmación, mantener precios referenciales, escenarios simulados y paquete 7D/6N hipotético. Las fuentes de otros operadores no prueban tarifas de Texeira. Registrar fecha y origen de cada confirmación futura. Si cambian datos, planificar un índice nuevo de prueba y su evaluación con autorización; no reconstruir índices protegidos.

Cierre del prototipo: incertidumbres etiquetadas. Cierre comercial: requiere datos confirmados; no se puede completar por suposición.

## Fase 7 — Preparar entrega y eventual integración

Entregar README breve: cómo iniciar la copia, pruebas, significado de indicadores, límites, archivos de evidencia y reversión. Crear checklist de demostración para el grupo del proyecto.

Antes de integrar cambios al original o WhatsApp, presentar diff concreto, resultados, respaldo/reversión y riesgos. Esperar autorización expresa para migrar, cambiar credenciales/URLs, publicar o enviar mensajes. Mantener la copia estable disponible mientras se decide. No prometer disponibilidad permanente con un servidor local o túnel temporal.

Para la tesis: preparar trazabilidad entre objetivos, implementación y evaluación. Los cuestionarios, participantes y resultados de impacto aún requieren ejecución real por el equipo; no inventar encuestas, muestras, porcentajes ni aprobación de la agencia. La edición del documento académico debe basarse en el archivo que el usuario indique.

## Criterio honesto de terminado

Se puede declarar «copia de prueba corregida y validada localmente» al cerrar fases 1–5 con evidencias. Datos oficiales, evaluación con usuarios, integración WhatsApp y despliegue son cierres separados que dependen de confirmaciones/autorizaciones. Completar todo lo independiente y listar cada dependencia concreta; nunca declarar el proyecto comercial o la tesis terminados si faltan esas etapas.

## Prompt para OpenCode

Continúa este proyecto leyendo PLAN_FINAL_OPENCODE.md, CONTINUAR_EN_OPENCODE.md y texeira-prueba/REVISION_OPENCODE.md. Ejecuta las fases 1–5 con cambios mínimos y pruebas locales sin llamadas reales a IA; prepara los entregables de las fases 6–7 y detente solo en sus dependencias externas o autorizaciones explícitas. Trabaja únicamente en texeira-prueba y documentos de continuidad, preservando texeira-chatbot, WhatsApp, índices y evidencias históricas. No leas ni expongas secretos. No instales paquetes ni cambies arquitectura/proveedor para resolver estos fallos. Usa pruebas con expectativas y registra resultados nuevos: un texto simulado no demuestra calidad generativa. Actualiza ESTADO_CIERRE.md y al final entrega cambios, evidencia, pendientes y pasos exactos de uso. No declares corregido algo sin comprobarlo ni prometas ausencia total de alucinaciones. Ahorra tokens leyendo solo lo necesario, sin repetir evaluaciones completas ni pedir confirmaciones para cambios locales ya autorizados. Pide autorización antes de llamadas reales a IA, integración al original, publicación o mensajes externos.

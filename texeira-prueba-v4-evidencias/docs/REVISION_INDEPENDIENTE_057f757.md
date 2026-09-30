# Revisión independiente de 057f757

Fecha: 2026-09-30. Rama observada: feature/polish-whatsapp-flow. Sin cambios a la aplicación ni despliegues.

## Ejecución reproducida

`python tests/run_isolated.py test_whatsapp_flow_polish.py`: 13 pruebas, 10 aprobadas, 3 fallos, salida 1. Evidencia: `logs/revision_flow_20260930.log`.

Los tres fallos esperan «no figura actualmente en nuestro catálogo activo», pero reciben «no se encuentra disponible actualmente en nuestro catálogo activo»: test_apply_request_inactive_tour_direct, test_journey_3_deactivated_tour_clicking_old_button y test_journey_4_inactive_tour_to_other_options. No prueban por sí mismos un fallo funcional; sí invalidan el 13/13 reportado para este estado. Alinear el contrato del mensaje manteniendo las verificaciones de rutas, botones prohibidos y ausencia de tickets. Las aserciones posteriores al primer fallo todavía deben ejecutarse.

## Revisión de código y evidencia RAG

- Se corrigió el retorno estructurado de apply_request.
- Existe paginación compartida y salida a categorías en páginas intermedias. La primera página todavía muestra dos tours y Más tours, sin Categorías; no afirmar salida por botón desde todas las páginas.
- test_rag_llm_verification sustituye app.get_llm por MagicMock con respuestas preescritas. Demuestra encaminamiento al modelo simulado, no síntesis fiel ni calidad de un proveedor real.
- Los documentos reportados en varios casos proceden de invocaciones separadas del retriever. En el seguimiento se añade manualmente Laguna Humantay a esa consulta. Esto no acredita qué documentos recuperó efectivamente rag_chain para el seguimiento. Instrumentar la llamada interna y registrar contexto y documentos efectivos, distinguiéndolos del historial.
- Etiquetar todos los casos con MagicMock como modelo simulado. model_called=True debe aclarar ese significado. Los casos deterministas registran model_called=False como literal; comprobar con un espía que no se invoque el modelo si se afirma ausencia de llamadas.
- Verificar proveedor/modelo configurados antes de proponer API real: ChatOpenAI es también el cliente utilizado por Groq, no evidencia suficiente de proveedor OpenAI.

No se ejecutó la suite RAG en esta revisión: su tearDown sobrescribe el JSON de evidencia versionado. Se inspeccionó su código. No se consumió API real ni se enviaron mensajes WhatsApp.

## Cierre recomendado

Reproducir suite limpia, corregir trazabilidad del pipeline y entregar informe preciso. Luego coordinar una evaluación sintética pequeña con el proveedor real configurado y el piloto de WhatsApp. No ampliar funcionalidades ni declarar 100% validado a partir de mocks. min-instances=0 no garantiza una factura nula.

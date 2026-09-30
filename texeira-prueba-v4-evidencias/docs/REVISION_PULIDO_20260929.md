# Revisión independiente del pulido de WhatsApp

Código revisado: HEAD 753b5c7. Revisión de lectura; no se modificó la aplicación ni se desplegó.

## Evidencia ejecutada

`tests/run_isolated.py test_whatsapp_flow_polish.py`: 11 pruebas, 10 exitosas y 1 fallo; salida 1. Registro: `logs/revision_flow_20260929.log`.

Falla `test_journey_1_greeting_to_rates`, línea 167: espera `Horario`, pero la ficha de Camino Inca no contiene ese campo en la base temporal inicializada desde el catálogo versionado. Revisar el fixture y el contrato para datos presentes/ausentes. No inventar un horario ni quitar la comprobación simplemente para obtener PASS.

## Hallazgos

1. `handoff_support.apply_request`, rama de reserva de tour inactivo: prepara `result`, pero termina con `return` sin valor. Los consumidores en app.py asignan el retorno y acceden a `rag_result["response"]`. Cambiar a `return result` y probar explícitamente esa rama; los botones pueden ser interceptados antes y no ejercitarla.
2. Paginación en `get_quick_buttons`: las páginas intermedias usan dos botones de tour y uno de Más tours. Categorías solo aparece al final. No hay una salida visible inmediata a categorías en páginas intermedias. Además el cuerpo de la categoría enumera todos sus tours aunque los botones cambien de página. Alinear texto y navegación y probar pulsando los botones que realmente se emitieron, hasta cubrir todos los tours activos.
3. El informe de 11/11 no se reprodujo en la ejecución aislada. No afirmar 100% probado ni solicitar despliegue hasta corregir/reproducir esta evidencia.

## Siguiente validación

Consolidar estos puntos en el encargo existente; después comprobar rutas deterministas frente a recuperación y llamadas LLM, sin forzar uso del modelo ni consumir API real sin necesidad. La suite de envío simulado no certifica entrega de WhatsApp ni uso de IA real.

No se consultaron ni cambiaron datos de producción. El costo cero no se garantiza con min-instances=0.

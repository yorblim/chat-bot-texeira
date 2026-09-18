# Continuidad del chatbot Texeira

## Encargo siguiente

Corregir únicamente en `texeira-prueba` dos fallos observados: indicadores incorrectos de resolución/derivación y confusión entre fuentes de precios y contacto de la agencia. Trabajar con cambios pequeños; no rehacer arquitectura. Ahorrar tokens: leer solo archivos relevantes, probar con proveedor simulado primero y repetir únicamente los casos afectados. No instalar dependencias ni cambiar proveedor/modelo sin necesidad.

## Límites

- `texeira-chatbot` es el proyecto original conectado a WhatsApp. No modificarlo.
- `texeira-prueba` es la copia aislada, servidor local en puerto 8020; no tiene credenciales Meta activas.
- No leer ni imprimir valores de `.env`, tokens o secretos. La copia carga internamente credenciales del proveedor desde el original: ejecutar una consulta real puede consumir cuota.
- No regenerar índices ni cambiar catálogo, embeddings, RRF=60, final_k=5 o máximo dos fragmentos por tour.
- Los precios son estimaciones y las inclusiones son escenarios simulados. No presentarlos como compromisos oficiales de Texeira.
- No enviar mensajes, publicar, reservar ni contactar con terceros.
- Conservar evidencias previas. No incluir expectativas de evaluación en el índice o prompt.

## Estado comprobado

- `trial_support.py` adapta catálogo, idioma, respuestas deterministas, políticas pendientes y recuperación cacheada. Se instala desde el final de `app.py`.
- Un evento de arranque precarga el buscador. Carga observada ~30 s; servidor empieza a aceptar solicitudes después. No elimina el coste de generación del proveedor.
- `INICIAR.ps1` inicia la copia con embeddings offline. Python disponible: `C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe`.
- Servidor disponible durante la última sesión en http://127.0.0.1:8020/chat. Comprobar si sigue activo antes de iniciar otro proceso. No detener servidores ajenos.
- Las pruebas anteriores de cinco casos corrigieron idioma inglés, respuestas repetitivas y cancelaciones españolas pendientes.
- Última evaluación: diez casos; cuatro deterministas y seis con proveedor real. HTTP 200 en los seis; latencias observadas 0,9–5,3 s. No equivale a una validación general o académica.

## Lectura mínima

1. `texeira-prueba/RESULTADOS_10_CASOS.md`.
2. `texeira-prueba/trial_support.py`.
3. En `texeira-prueba/app.py`, buscar `resolved_autonomously`, `escalated_to_human`, `needs_escalation`, `is_escalation_response` y `/test-chat`.
4. Consultar solo los registros necesarios de `evaluation-ten-live-20260911-111304.json`; criterios en `EVALUACION_10_CASOS.md`.

## Fallos a corregir

- C06: respuesta sobre paquete hipotético correcta, pero `escalated_to_human=true` sin derivación real. No inferir una derivación efectiva por mencionar un asesor, especialmente si se niega que vaya a contactar.
- C07–C09: condiciones comerciales pendientes registradas como `resolved_autonomously=true` y `needs_agency_confirmation=false`. Distinguir respuesta informativa de operación pendiente; no marcar toda consulta informativa como pendiente indiscriminadamente.
- C08: ofrece fuentes de precios de otros operadores para contactar con Texeira. Usar el contacto publicado del objeto `agency` de `data/provisional.json`, nunca teléfonos inventados ni atribuir fuentes externas a la agencia.
- Mejora secundaria C09: explicar que falta cotización/tipo de cambio confirmado; evitar hablar de «prohibiciones» internas al cliente.

## Validación económica

Crear pruebas de regresión sin llamadas reales para indicadores y contacto. El script `evaluate_ten.py local` simula el LLM, pero carga el índice real y tarda en arrancar. No evaluar calidad del texto simulado como si fuera generado. `evaluate_ten.py live ...` sí llama al proveedor: evitar ejecutar la corrida completa para estos cambios. Mantener expectativas anteriores y registrar nuevos resultados aparte. Reportar qué se corrigió, qué se comprobó y qué queda pendiente, sin afirmar cero alucinaciones.

El modelo gratuito usado en OpenCode depende de la configuración de esa herramienta. No se comprobó su disponibilidad, cuotas ni tratamiento de datos. Este documento permite continuar sin copiar el historial completo ni compartir secretos.

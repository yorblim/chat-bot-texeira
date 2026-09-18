# Versión aislada de prueba

Esta carpeta contiene una copia del servidor y los módulos necesarios, adaptada para el catálogo provisional del 11 de septiembre. No sustituye texeira-chatbot ni está conectada a WhatsApp.

- Catálogo: data/provisional.json. Rangos orientativos y condiciones simuladas, nunca tarifas oficiales.
- Índice: chroma_provisional_db, solo documentos provisionales. Conserva BM25 + vector + RRF, top 5, máximo 2 fragmentos por tour, RRF 60 y embeddings anteriores. READY.json liga el índice al hash del catálogo y evita usarlo tras cambiar la fuente.
- Conversaciones: trial_logs.db, independiente. Historial en RAM propio del proceso.
- No se copió .env. Al arrancar lee únicamente configuración y claves del proveedor LLM del .env original. Las credenciales de Meta están vacías en este proceso. No se imprimen claves.
- Los saludos antiguos se conservan; las respuestas comerciales antiguas se desactivan. Listados muestran rangos. Consultas simples en español sobre un tour tienen respuesta estructurada con seguimiento; otras consultas usan el RAG provisional.
- El modelo recibe instrucciones sobre incertidumbre y cada respuesta lleva un aviso referencial. El aviso no garantiza corrección de la generación: falta evaluar el modelo real.
- Las políticas desconocidas permanecen pendientes. El paquete 7D/6N sigue identificado como hipotético.
- No se arrastra el historial de WhatsApp ni se utilizan fotos del catálogo de ejemplo.

## Abrir localmente

Ejecutar INICIAR.ps1 con PowerShell. Usa 127.0.0.1:8020; no expone el servicio públicamente. Abrir http://127.0.0.1:8020/chat. Cerrar con Ctrl+C.

Los listados, contactos y fichas simples en español no consumen LLM. Las consultas que pasan al RAG sí utilizan la cuenta configurada. El script test_trial.py simula el LLM y comprueba la recuperación real local sin consumir esa API.

## Límites

No es un reemplazo listo para producción. El esquema y la fuente cambiaron: no mezclar estos resultados con el baseline anterior. La detección de idioma y varias métricas se heredan del prototipo y aún necesitan evaluación; un resultado marcado como resuelto no prueba su exactitud. Los nombres del listado se conservan en español. Se ha probado una selección de escenarios, no todas las conversaciones ni los cuatro idiomas con el proveedor real.

Para deshacer basta cerrar esta prueba y continuar usando texeira-chatbot; el original se conserva intacto. No ejecutar ingest_hybrid.py del proyecto anterior para actualizar este índice.

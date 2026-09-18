# Medición local — 11 de septiembre de 2026

Ejecutado measure_local_latency.py con modelos locales en modo offline, sin invocar un proveedor LLM. Resultados en local_latency.json.

| Etapa | Segundos |
| --- | ---: |
| Inicializar buscador, importaciones, embeddings e índice existente | 32,999 |
| Primera búsqueda | 0,533 |
| Segunda búsqueda idéntica | 0,049 |

La instancia se reutiliza mediante lru_cache; se comprobó identidad del objeto. La demora local inicial es considerable. Esto es compatible con los 38,204 segundos observados en la primera consulta RAG del servidor, pero no permite descomponer retrospectivamente aquella petición ni calcular por diferencia el tiempo del proveedor: son ejecuciones distintas.

No se cambiaron modelo, catálogo, reglas de recuperación ni servidor. No se hicieron llamadas al proveedor ni se regeneró el índice. Las advertencias de telemetría y deprecación no impidieron la medición.

Siguiente mejora propuesta: precargar el buscador al arrancar el servidor. Traslada la espera al arranque, no elimina el coste de carga. Luego medir por separado recuperación y generación en solicitudes futuras. Una sola medición no establece latencia típica ni garantiza tiempos futuros.

## Precarga implementada

trial_support.install registra un evento de arranque que carga el mismo buscador cacheado antes de que Uvicorn termine el inicio. La carga se ejecuta en un hilo; no genera respuestas ni invoca el LLM. Si falta el índice o falla la carga, el servidor no declara el arranque completado. INICIAR.ps1 conserva el modo offline para los embeddings. La primera búsqueda aún debe calcular el embedding de la pregunta y las consultas RAG siguen dependiendo del proveedor.

Verificación: arranque real con precarga de 29,94 s, seguido de Application startup complete. GET /chat respondió HTTP 200 con la etiqueta de prueba. No se hicieron consultas al proveedor para esta verificación.

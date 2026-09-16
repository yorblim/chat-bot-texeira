# Mapa del proyecto

## Objetivo y arquitectura
Agente RAG para automatizar la atención informativa de Texeira Travel Tour,
Cusco, con información del catálogo, soporte ES/EN y fallback prudente.
Flujo RAG: app.py → HybridRetriever → BM25 + vectores → RRF → máximo
2 chunks por tour → top 5 → contexto con metadata → Groq → respuesta.
La aplicación también tiene respuestas predefinidas y navegación de UI.

## Archivos principales
- app.py: API, contexto enriquecido, historial y proveedor LLM.
- src/retriever.py y src/preprocessing.py: recuperación y preparación del catálogo.
- data/tours_catalog.json: fuente del índice híbrido; ingest_hybrid.py: ingesta.
- chroma_hybrid_db/: índice actual. chroma_db/: base anterior protegida.
- evaluation/: dataset congelado, evaluadores y resultados baseline.
- database.py, chat_ui.py y admin_dashboard.py: logs e interfaces.
- docs/PROJECT_STATUS.md: estado verificado, diferencias y próximos pasos.

## Reglas que deben conservarse
- Antes de trabajar, leer docs/PROJECT_STATUS.md y la solicitud vigente.
- Sin autorización, no modificar código, catálogo, prompts, modelo, embeddings,
  chunking, índices, dataset ni resultados baseline; no instalar ni ejecutar ingestas.
- Conservar final_k=5, max_chunks_per_tour=2 y rrf_k=60. No optimizar Q08/Q21.
- No borrar ni reconstruir chroma_db; no alimentar el índice híbrido con TXT antiguos.
- Preservar tour_name, tour_id, price_usd, price_pen y category en el contexto.
- Ground truth solo para evaluación posterior: nunca introducirlo en retrieval o prompt.
- Mantener el baseline con el mismo proveedor/modelo; no mezclar un fallback local.
- Un 429, timeout o error de proveedor no es una respuesta válida ni un fallo del RAG.
  El evaluador aún incumple esta regla para algunos timeouts; no confiar solo en completed.
- Ante problemas: diagnosticar, aportar evidencia y proponer; implementar solo si se pide.
- No exponer secretos de .env ni datos personales de conversaciones.

## Cómo validar
Por defecto, revisión estática y JSON; SQLite únicamente en modo lectura.
Verificar 40 IDs únicos, 38 consultas aplicables y Recall@5 sobre tours únicos.
Contar pendientes contra todo el dataset, no solo contra filas del checkpoint.
No ejecutar app, ingestas o evaluadores para una inspección: pueden escribir o consumir cuota.
Antes de reanudar evaluation/evaluate_e2e.py con autorización, resolver las discrepancias
documentadas y verificar el proveedor/modelo y los errores de infraestructura.
Estado de esta entrega: solo documentación; esperar revisión del usuario.

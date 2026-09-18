# RAG Híbrido: BM25 + Búsqueda Vectorial + Reciprocal Rank Fusion

Módulo de recuperación híbrida para la tesis "Agente Conversacional RAG para Atención al Turista — Texeira Travel Tour".

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    Flujo de Recuperación                     │
│                                                             │
│  Query del turista                                          │
│       │                                                     │
│       ├──→ Preprocessing (normalización quechua)            │
│       │         │                                           │
│       │    ┌────┴────┐                                      │
│       │    │         │                                      │
│       ▼    ▼         ▼                                      │
│  ┌─────────┐  ┌──────────────┐                              │
│  │  BM25   │  │ Vector Store │                              │
│  │(léxico) │  │  (semántico) │                              │
│  └────┬────┘  └──────┬───────┘                              │
│       │              │                                      │
│       └──────┬───────┘                                      │
│              ▼                                              │
│     ┌────────────────┐                                      │
│     │ RRF Ensemble   │  score = Σ 1/(k + rank_i)           │
│     │ (fusionador)   │                                      │
│     └───────┬────────┘                                      │
│             ▼                                               │
│     Top-K Documents ──→ LLM (DeepSeek/Groq/OpenAI)         │
│                            │                                │
│                     System Prompt + Contexto                 │
│                            │                                │
│                      Respuesta al turista                   │
└─────────────────────────────────────────────────────────────┘
```

## Estructura del Proyecto

```
src/
├── __init__.py
├── preprocessing.py    # Tokenización + normalización quechua
├── retriever.py        # BM25 + Vector + RRF Ensemble
├── agent.py            # Cadena RAG orquestada
├── evaluation.py       # Comparación empírica (15 preguntas)
├── requirements_hybrid.txt
└── README.md

data/
└── tours_catalog.json  # Catálogo turístico JSON
```

## Módulos

### 1. `preprocessing.py` — Normalización Multilingüe

Resuelve el problema crítico de la recuperación inexacta de toponimias andinas. Un turista que escribe "Sacsayhuaman", "Saqsaywaman" o "Sacsahuaman" debe recuperar el mismo documento.

**Diccionario de normalización**: 40+ términos quechuas/andinos con variantes fonéticas y ortográficas mapeadas a su forma canónica.

**Pipeline de tokenización**:
1. Minúsculas
2. Eliminación de acentos (á→a)
3. Eliminación de puntuación
4. Tokenización por espacio
5. Eliminación de stop words (ES/EN/PT)
6. Normalización quechua por token

### 2. `retriever.py` — Recuperación Híbrida

**BM25RetrieverCustom**: Búsqueda léxica con `rank_bm25`, tokenización multilingüe y normalización quechua.索引进行搜索。

**Vector Store Retriever**: Búsqueda semántica con ChromaDB y embeddings HuggingFace `paraphrase-multilingual-MiniLM-L12-v2` (local, sin costo).

**HybridRetriever**: Fusiona ambos rankings usando **Reciprocal Rank Fusion (RRF)**:
```
score(doc) = 1/(k + rank_bm25) + 1/(k + rank_vector)
```
Donde `k=60` (constante de suavizado del paper original de Cormack et al., SIGIR 2009).

### 3. `agent.py` — Cadena RAG Orquestada

- System prompt multilingüe (ES/EN/PT) con 6 reglas anti-alucinación
- Control de tono corporativo para agencia de turismo
- Guardrails para precios (siempre moneda), itinerarios y topografía andina
- Conversation history (memoria de corto plazo)
- Integración con `get_llm()` de `app.py` (multi-proveedor)

### 4. `evaluation.py` — Evaluación Empírica

**15 preguntas frecuentes** categorizadas:
- Preguntas con nombres quechuas (3): evalúa normalización
- Errores ortográficos (2): evalúa tolerancia
- Multilingües (2): evalúa detección de idioma
- Datos específicos (2): evalúa precisión factual
- Fuera de alcance (2): evalúa fallback correcto
- Comparaciones (2): evalúa recuperación de múltiples docs
- Variantes fonéticas (2): evalúa robustez léxica

**Métricas RAGAS**:
- `faithfulness`: Fidelidad al contexto (anti-alucinación)
- `answer_relevancy`: Relevancia de la respuesta
- `context_precision`: Precisión de la recuperación

**Comparación**:
- Enfoque 1: RAG Tradicional (solo vectores densos)
- Enfoque 2: RAG Híbrido (BM25 + Vectores + RRF)

## Ejecución

### Requisitos previos
```bash
pip install -r requirements.txt
pip install -r src/requirements_hybrid.txt
python ingest.py  # Indexar documentos en ChromaDB
```

### Ejecutar el agente híbrido
```python
from src.agent import create_hybrid_agent, ask_hybrid

agent = create_hybrid_agent()
result = ask_hybrid("¿Cuánto cuesta ir a Sacsayhuaman?", agent)
print(result["response"])
```

### Ejecutar la evaluación comparativa
```bash
# Evaluación completa (15 preguntas)
python -m src.evaluation

# Evaluación rápida (5 preguntas, debug)
python -m src.evaluation --quick
```

### Diagnosticar recuperación
```python
from src.retriever import build_hybrid_retriever, compare_retrievers
from src.agent import create_vector_agent

retriever = build_hybrid_retriever()
# Ver diferencias entre BM25, Vector y Hybrid para una query
```

## Interpretación de Resultados para la Tesis

### Capítulo de Resultados
1. **Tabla comparativa**: faithfulness, context_precision, answer_relevancy por enfoque
2. **Fallback accuracy**: % de preguntas fuera de alcance manejadas correctamente
3. **Latencia**: tiempo promedio de respuesta por enfoque
4. **Análisis cualitativo**: ejemplos donde BM25 supera a vectores y viceversa

### Capítulo de Discusión
1. **Impacto de la normalización quechua**: comparar recuperación antes/después
2. **Ventaja de RRF sobre ponderación lineal**: por qué RRF es más robusto
3. **Trade-off precisión vs recall**: BM25 es más preciso para términos exactos, vectores cubren más variaciones semánticas
4. **Escalabilidad**: costo computacional de agregar BM25 vs mejora obtenida

### Figuras Sugeridas
- Figura X: Arquitectura del sistema híbrido (sección 3.1)
- Figura Y: Comparación de métricas RAGAS por enfoque (sección 4.2)
- Figura Z: Ejemplo de normalización quechua y recuperación (sección 3.2)

## Referencias

- Cormack, G., Clarke, C., Butt, S. (2009). "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods". SIGIR.
- Lewis, P. et al. (2020). "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks". NeurIPS.
- Es, S. et al. (2024). "RAGAS: Automated Evaluation of Retrieval Augmented Generation". arXiv.

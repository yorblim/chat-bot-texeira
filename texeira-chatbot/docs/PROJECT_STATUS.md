# Estado del proyecto Texeira Chatbot

Revisión: 2026-09-09. Raíz de trabajo: texeira-chatbot/.
Fuentes: código y artefactos locales, solicitud del usuario y
C:/Users/HP/Downloads/Chat bot.docx. El documento se revisó mediante extracción
del texto y tablas OOXML; no se auditó su diseño visual ni se verificaron sus referencias externas.
Las instrucciones de trabajo proceden del usuario; la tesis es material de contexto.

## Objetivo y relación con la investigación
El objetivo coincide: diseñar, desarrollar y evaluar un agente conversacional
para automatizar el servicio al cliente de Texeira Travel Tour en Cusco,
con respuestas sustentadas en el catálogo, atención multilingüe y disponibilidad.
La tesis plantea investigación cuantitativa, aplicada y preexperimental con
pretest/postest, encuestas a turistas y personal, y observación de logs.
Las 40 consultas técnicas no sustituyen esa evaluación de impacto en la agencia.

En Materiales y métodos se mencionan GPT-4o/Claude como ejemplos, recuperación
vectorial, nube y canales WhatsApp/Messenger. No aparecen Groq, Qwen, BM25,
RRF ni el dataset de 40 consultas. El alcance idiomático es más amplio que ES/EN:
los cuestionarios incluyen portugués y otros idiomas. En Presentación de resultados,
la implementación comercial sigue pendiente y se describe un prototipo controlado.
Actualizar esa trazabilidad documental queda pendiente, sin editar ahora la tesis.

## Estado técnico verificado
- Backend FastAPI en app.py, interfaces de chat y dashboard, logs SQLite.
- Flujo RAG activo: HybridRetriever, BM25 + vectores, RRF, máximo 2 chunks por
  tour y top 5. app.py añade metadata al contexto antes de llamar al modelo.
- Parámetros: final_k=5, max_chunks_per_tour=2, rrf_k=60; BM25 y vector recuperan
  hasta 10 documentos cada uno. Embeddings: paraphrase-multilingual-MiniLM-L12-v2.
- Configuración local y checkpoint: Groq, qwen/qwen3.8-27b, temperatura 0.1,
  máximo 900 tokens de salida. app.py conserva DeepSeek como valor por defecto
  si no se carga la configuración; no confundir ese default con el entorno revisado.
- app.py también atiende respuestas predefinidas y navegación sin pasar por el LLM.
- src/agent.py contiene otra cadena; no es la cadena que usa app.py.
- Fuente híbrida: data/tours_catalog.json. ingest_hybrid.py usa ese catálogo.
  Los TXT y chroma_db pertenecen al flujo anterior y deben permanecer intactos.

Consulta SQLite de solo lectura confirmó 27 chunks en chroma_hybrid_db:

| ID | Chunks |
|---|---:|
| city-tour-cusco | 3 |
| valle-sagrado | 3 |
| machu-picchu-clasico | 3 |
| laguna-humantay | 3 |
| montana-7-colores | 3 |
| salkantay-trek | 7 |
| paquete-completo-7d | 3 |
| policies | 2 |

tour_id, tour_name, category y chunk_index están en los 27 registros;
price_usd en 25 y price_pen en 18. Las imágenes persistidas usan images_json.
Se verificó estructura y metadata, sin regenerar embeddings ni ejecutar retrieval.

## Decisiones congeladas
Conservar catálogo, chunking, índices, embeddings, recuperación, prompts, modelo
y las 40 queries durante el baseline. No añadir sinónimos, boosting, reglas para
preguntas concretas ni cambiar top-k. Mantener el enriquecimiento de contexto
con tour_name, tour_id, price_usd, price_pen y category cuando existan.
Los campos esperados del dataset se utilizan únicamente para evaluar la salida;
no se inyectan en el prompt ni en la consulta de recuperación del evaluador revisado.

Las 10 pruebas piloto (8 correctas, 2 parciales, 0 incorrectas) son antecedentes
reportados por el usuario. No se identificó un informe independiente inequívoco
de esas 10 pruebas; no se presentan como una ejecución reproducida en esta revisión.

## Dataset y baseline de recuperación
evaluation/eval_dataset.json contiene 40 consultas: 35 ES y 5 EN.
Categorías: price 11, includes 7, recommendation 6, itinerary 5, policy 5,
general 4 y out_of_catalog 2. Estilos: standard 35, ambiguous 3 y paraphrase 2;
informal no aparece en la distribución actual.

Se recalcularon los agregados a partir de las filas guardadas, sin nuevas consultas:

| Métrica | Baseline |
|---|---:|
| Hit Rate@5 | 36/38 = 0.9474 |
| MRR | 0.6825 |
| Mean Recall@5 | 0.8658 |

Fuente: evaluation/baseline_retrieval_results.json.
Las 2 consultas fuera de catálogo sin tours relevantes se excluyen.
Recall@5 = tamaño de la intersección de tours únicos recuperados y relevantes,
dividido por el número de tours relevantes; no contar chunks repetidos como tours.
Los fallos Hit@5=0 coinciden con Q08 (tour más económico) y Q21 (principiante).
No optimizarlos todavía. Los resultados miden recuperación de tours, no corrección
de respuestas ni cobertura de todos los temas de cada chunk.

## Evaluación E2E y bloqueo Groq
El checkpoint evaluation/baseline_e2e_results.json, fechado internamente
2026-09-09 18:48:58, tiene 0/40 completed y una fila Q01 con provider_rate_limit.
Por tanto faltan 40 respuestas válidas: 1 consulta intentada y 39 sin fila.
summary.pending_queries=1 cuenta solo la fila fallida y subestima el trabajo pendiente.
Las métricas de generación actuales son null; no hay resultados finales E2E.

El error guardado acredita un 429 después del reintento. El usuario reportó cuota
diaria de 200000 tokens, consumo aproximado de 197000+ y unos 8000 tokens/minuto.
Esos límites son antecedentes de aquella ejecución, no una consulta actual al proveedor.
No se comprobó si la cuota ya se restableció ni se consumieron tokens en esta revisión.
Un error de infraestructura no debe calificarse como respuesta incorrecta del RAG.

## Diferencias y problemas conocidos
1. Timeout: evaluate_e2e.py, bloque except concurrent.futures.TimeoutError,
   genera un fallback artificial y marca completed. Contradice el protocolo pedido;
   puede contaminar calidad y quedar omitido por la reanudación. Además, el cierre
   del ThreadPoolExecutor espera al hilo, por lo que 60 s no garantiza corte efectivo.
   Propuesta pendiente: registrar timeout sin respuesta válida y controlar el timeout
   del cliente. No se cambió el evaluador.
2. Pendientes y cierre: pending_count cuenta solo filas existentes no completadas;
   all_done no exige 40 IDs completados. Propuesta: calcular diferencias de IDs contra
   el dataset y exigir cobertura completa, sin alterar queries ni resultados ahora.
3. Latencias: un reintento 429 que luego completa incorpora la espera en t_generation.
   Propuesta: separar latencia operativa y latencia de inferencia para la interpretación.
4. Alcance E2E: evaluate_e2e.py reconstruye retrieval/contexto y usa get_llm y
   SYSTEM_PROMPT; no ejecuta el endpoint, respuestas predefinidas, historial ni Meta.
   Es un baseline del pipeline RAG aislado. Mantener su alcance explícito y evaluar
   la aplicación completa por separado, sin cambiar silenciosamente el experimento.
5. Precios predefinidos de app.py: Valle Sagrado 65 USD y Montaña de Colores 85 USD,
   frente a 55 y 50 en catálogo. El substring «cuánto cuesta» puede saltarse el RAG.
   Registrar para una corrección autorizada; el contexto enriquecido se conserva.
6. Métricas de app.py: not is_fallback puede marcar un handoff como resuelto;
   los 429 también devuelven resolución positiva, aunque database.py los excluye
   de sus bloques de calidad. Pendiente separar estados de resultado explícitos.
7. Producción: dashboard/historial sin autenticación en el código, HTML del dashboard
   sin escape de mensajes, webhook sin verificación de firma ni deduplicación Meta,
   y sin flujo completo visible de asignación a un asesor. COPY . . sin .dockerignore
   puede incorporar .env y bases locales. Corregir solo con autorización.
8. Rendimiento: se reconstruyen recursos de recuperación por consulta y hay llamadas
   síncronas dentro de rutas async. No optimizar durante este baseline.
9. Artefactos anteriores: hay otros datasets y resultados RAGAS; resumen_resultados.json
   tiene n=0 y medias null para fidelidad/precisión. No mezclar esas corridas con las 40.
10. Tesis frente a evidencia: disponibilidad 24/7, anonimato, integración comercial
    y derivación efectiva requieren validación adicional; no se demuestran por existir
    el prototipo o un prompt estricto. La revisión no certifica cumplimiento legal.

## Fallback local pendiente
Idea del usuario: Groq → Ollama con Qwen3 4B ante 429, timeout o fallo del proveedor,
para producción. Hardware reportado: RTX 4050 y 16 GB RAM; no comprobado aquí.
No se identificó esa integración en el código revisado. No instalar ni implementar.
Si se autoriza posteriormente, registrar proveedor efectivo por respuesta y mantener
el baseline académico exclusivamente con el modelo/proveedor congelado.

## Próximos pasos
1. Revisar y aprobar estos dos documentos. Esta tarea termina aquí.
2. Autorizar, si procede, correcciones del evaluador para timeout, conteo y trazabilidad,
   conservando dataset, pipeline y parámetros del baseline.
3. Verificar disponibilidad de cuota y reanudar con autorización hasta 40/40 respuestas
   válidas del mismo proveedor/modelo; no aceptar errores como completed.
4. Revisar respuestas problemáticas y realizar evaluación formal/RAGAS.
5. Decidir después si se optimiza; comparar con las mismas 40 consultas y preservar baseline.
6. Preparar tablas y vincular evidencia técnica con instrumentos pretest/postest de la tesis.
7. En una fase posterior autorizada, abordar producción y el fallback local opcional.

En esta revisión solo se crean AGENTS.md y docs/PROJECT_STATUS.md. No se modifican
código, configuración, datasets, resultados, bases de datos ni el documento Word;
no se instalan dependencias ni se ejecutan ingestas, evaluación o llamadas al LLM.

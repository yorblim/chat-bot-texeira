# Informe de Evaluación Real del LLM: Groq (Qwen 3.8-27B), Corrección de Ingesta y Cobertura Documental

**Fecha:** 30 de Septiembre de 2026  
**Proyecto:** Texeira Travel Chatbot (`texeira-prueba-v4-evidencias/`)  
**Rama activa:** `feature/polish-whatsapp-flow`  
**Proveedor evaluado:** Groq (`groq`)  
**Modelo evaluado:** `qwen/qwen3.8-27b`  
**Estado:** Ingesta corregida, índice ChromaDB actualizado, preflight validado y evaluación real de 4 llamadas completada satisfactoriamente.

---

## 1. Resumen Ejecutivo y Clasificación de Resultados

Tras la identificación de la omisión de ingesta documental en las fuentes oficiales de la agencia (F2), se ejecutó la comprobación visual de las láminas originales, se incorporaron los hechos verificados a `data/evidence_facts.json` y al catálogo, se reconstruyó el índice ChromaDB conforme al protocolo preflight y se implementó la directiva de **respuesta parcial en preguntas compuestas**.

Posteriormente, se ejecutó la batería sintética de **4 llamadas reales al LLM** en Groq (`qwen/qwen3.8-27b`), precedida por el turno preparatorio determinista.

### Matriz de Resultados Reales con Ingesta Corregida
| Caso | Consulta Evaluada | Comportamiento Efectivo | Clasificación del Resultado |
| :--- | :--- | :--- | :--- |
| **Inka Jungle** | Descenso en bicicleta por Abra Málaga y actividades de aventura | Informa el descenso en bicicleta desde *Abra Málaga (4,350 msnm)* hasta *Santa María (1,450 msnm)*. Aclara que las demás actividades de aventura requieren confirmación con el equipo. Cero alucinaciones de canotaje o tirolina. | **Respuesta informativa exacta con derivación de lo no publicado.** |
| **Laguna Humantay** | Altitud máxima y exigencia de la subida a pie | Informa con exactitud la cota máxima documentada (*4,200 m.s.n.m.* desde Soraypampa a 3,920 msnm). Aclara que la exigencia de la caminata requiere confirmación con el equipo. No rechaza la consulta. | **Respuesta informativa parcial con derivación de lo no publicado.** |
| **City Tour Cusco** | Recorrido y lugares visitados tras consultar Humantay | Detalla los centros arqueológicos (*Koricancha, Sacsayhuamán, Q'enqo, Puka Pukara, Tambomachay*), inclusiones y horarios oficiales. Cero contaminación contextual de Humantay. | **Respuesta informativa completa respaldada en fuentes.** |
| **Comparación** | Camino Inca vs Salkantay Trek en duración y precio | Compara la duración (*4 días / 3 noches* vs *4 días*) y tarifa oficial (*790 USD* vs precio por confirmar con asesor). | **Respuesta informativa comparativa con derivación de lo no publicado.** |

### Balance Técnico y Alcance
- **Comportamiento en preguntas compuestas:** El modelo ya no aplica un rechazo total (*fallback*) cuando dispone de datos para responder una parte de la consulta. Proporciona con precisión la cota oficial y delimita con honestidad qué aspectos específicos (exigencia física, duración de caminata o deportes adicionales) requieren confirmación con la agencia.
- **Alcance de la latencia registrada:** La latencia promedio de **0.891 segundos** (rango: 0.472s – 1.433s) corresponde exclusivamente al tiempo de inferencia de la API de Groq en la llamada al modelo. **No representa el tiempo de respuesta completo de WhatsApp**, el cual incluye la recepción del webhook de Meta, procesamiento en Cloud Run, consultas a base de datos y despacho del mensaje saliente.
- **Consumo reportado (4 llamadas reales):**
  - Prompt tokens: 5,150 | Completion tokens: 316 | Total tokens: 5,466
  - Errores de API / Cuota (HTTP 429): 0 errores.
  - Llamadas a servicios de pago / cambios de proveedor: 0.

---

## 2. Verificación Visual de Láminas Oficiales (PDF F2)

Se inspeccionaron directamente las páginas citadas de `TOURS - Agencia TEXEIRA TRAVEL.pdf` (F2):

### 2.1 Laguna Humantay (F2, Página 9)
- **Lámina visual:** Muestra el diagrama de ruta Cusco (3,360 msnm) → Limatambo (2,554 msnm) → Cruz Pata (3,400 msnm) → Soraypampa (3,920 msnm) y el ascenso con ícono de senderista hasta **`Laguna Humantay 4200 m.s.n.m.`**.
- **Inclusiones confirmadas:** Transporte ida y vuelta, guía profesional bilingüe, almuerzo (y desayuno según F1).
- **Límite documental:** La lámina no especifica duración de caminata en horas ni nivel de exigencia física.
- **Hechos incorporados a `evidence_facts.json`:**
  - `lh-altitude-f2`: `4,200 m.s.n.m. (Soraypampa a 3,920 m.s.n.m.)` (Fuente: F2, Pág. 9).
  - `lh-route-f2`: `Ascenso a pie desde Soraypampa (3,920 m.s.n.m.) hasta Laguna Humantay (4,200 m.s.n.m.). La duración o dificultad de la subida a pie requieren confirmación con la agencia.` (Fuente: F2, Pág. 9).

### 2.2 Inka Jungle to Machu Picchu (F2, Página 17)
- **Lámina visual:** Muestra el circuito completo de 4 días. El punto más elevado está identificado explícitamente como **`Abra Malaga 4350 m.s.n.m.`**. En el Día 1 (tramo Abra Málaga a Santa María 1,450 msnm pasando por Huamanmarka), la infografía incluye una línea punteada azul con **dos pictogramas de ciclistas** y fotografía de descenso en bicicleta en carretera.
- **Límite documental:** No figuran actividades de canotaje/rafting ni tirolina/zipline en la lámina oficial de la agencia, ni tiempos de caminata no respaldados.
- **Hechos incorporados a `evidence_facts.json`:**
  - `ij-altitude-f2`: `Abra Málaga a 4,350 m.s.n.m. (punto más alto del circuito)` (Fuente: F2, Pág. 17).
  - `ij-route-f2`: `Día 1: Descenso en bicicleta desde Abra Málaga (4,350 m.s.n.m.) hasta Santa María (1,450 m.s.n.m.). Otras actividades de aventura y tiempos de caminata requieren confirmación con la agencia.` (Fuente: F2, Pág. 17).

---

## 3. Actualización y Verificación del Índice ChromaDB

Siguiendo el procedimiento preflight estricto del proyecto:
1. Se actualizaron `data/evidence_facts.json` y `data/tours_catalog.json`.
2. Se definió la política `'altitude': 'exclusive_scalar'` en `src/evidence.py`.
3. Se generaron los 20 documentos exactos mediante `trial_support.documents(include_dynamic=False)`.
4. Se reconstruyó la base vectorial en `chroma_catalogo_20260926_db` recalculando los embeddings y persistiendo los archivos binarios y SQLite.
5. Se actualizó el manifiesto `READY.json` con los hashes SHA-256 canónicos de las fuentes y documentos.
6. Se ejecutó `python tests/test_index_preflight.py`:
   ```
   PASS: manifiesto y 20 documentos; independiente de DB administrativa.
   ```

---

## 4. Registro Detallado de Respuestas Reales Obtenidas (Groq / Qwen 3.8-27B)

### Caso 1: Inka Jungle (Pregunta Abierta de Aventura)
- **Pregunta:** *«¿Cómo es el descenso en bicicleta por el Abra Málaga y qué actividades de aventura se hacen en el Inka Jungle?»*
- **Ruta:** `rag_llm` | **Latencia API:** 1.154s | **Tokens:** 1,445 prompt / 68 completion
- **Documento efectivo inyectado:** Chunk `inka-jungle` de F2 con cota de Abra Málaga (4,350 msnm), Santa María (1,450 msnm) y descenso en bicicleta.
- **Respuesta real del LLM Groq:**
  > *"El descenso en bicicleta inicia en \*Abra Málaga\* (4,350 m.s.n.m.) hasta \*Santa María\* (1,450 m.s.n.m.).*  
  > *Las demás actividades de aventura requieren confirmación con el equipo.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Evaluación de criterios:**
  - Cita Abra Málaga y altitud (4,350 msnm): `PASS`
  - Cita bicicleta: `PASS`
  - Evita alucinar actividades no documentadas (canotaje, tirolina): `PASS`
  - Aclara necesidad de confirmación para datos pendientes: `PASS`

### Caso 2: Laguna Humantay (Seguimiento Contextual Elíptico)
- **Turno previo determinista (Turno 0):** *«¿Tienen información de la Laguna Humantay?»* → Respuesta determinista de catálogo.
- **Pregunta de seguimiento (Turno 1):** *«¿A qué altura máxima sobre el nivel del mar se encuentra y qué tan exigente es la subida a pie?»*
- **Ruta:** `rag_llm` | **Latencia API:** 0.472s | **Tokens:** 1,294 prompt / 68 completion
- **Recuperación contextual:** Retriever query enriquecida: *`"Laguna Humantay A qué altura máxima..."`*. Pregunta original conservada intacta.
- **Documento efectivo inyectado:** Chunk `laguna-humantay` conteniendo altitud (4,200 msnm / Soraypampa 3,920 msnm) y ascenso a pie con nota de confirmación.
- **Respuesta real del LLM Groq:**
  > *"📍 La altura máxima es \*4,200 m.s.n.m.\* (desde Soraypampa a 3,920 m.s.n.m.).*  
  > *La exigencia de la caminata requiere confirmación con el equipo.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Evaluación de criterios:**
  - Retiene la pregunta original: `PASS`
  - Recupera documento de Humantay: `PASS`
  - Cita altitud máxima documentada (4,200 msnm / 3,920 msnm): `PASS`
  - Aclara que la exigencia física requiere confirmación: `PASS`
  - Evita rechazo total (no se abstiene por completo de la consulta): `PASS`

### Caso 3: Cambio de Tour tras Humantay (City Tour Cusco)
- **Pregunta de cambio:** *«¿Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco?»*
- **Ruta:** `rag_llm` | **Latencia API:** 1.433s | **Tokens:** 1,215 prompt / 107 completion
- **Recuperación contextual:** Retriever query limpia: *`"Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco"`* (sin contaminación de Humantay).
- **Documento efectivo inyectado:** Chunk `city-tour-cusco` con los 5 centros arqueológicos, horarios e inclusiones.
- **Respuesta real del LLM Groq:**
  > *"El \*City Tour Cusco\* incluye visitas a \*Koricancha\*, \*Sacsayhuamán\*, \*Q'enqo\*, \*Puka Pukara\* y \*Tambomachay\*.*  
  > *Incluye \*bus turístico\* y \*guía profesional\*.*  
  > *Horarios: \*10:00-14:00\* o \*13:30-18:30\*.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Evaluación de criterios:**
  - Identifica el cambio de tour: `PASS`
  - Cita los centros arqueológicos oficiales: `PASS`
  - Cero contaminación con datos de Humantay: `PASS`

### Caso 4: Comparación entre Tours (Camino Inca vs Salkantay Trek)
- **Pregunta comparativa:** *«¿Qué diferencias hay entre el Camino Inca Clásico y el Salkantay Trek en duración y precio?»*
- **Ruta:** `rag_llm` | **Latencia API:** 0.505s | **Tokens:** 1,196 prompt / 73 completion
- **Documentos efectivos inyectados:** Chunks simultáneos de `camino-inka` (precio 790 USD, 4D/3N) y `salkantay-trek` (4 días, sin precio confirmado).
- **Respuesta real del LLM Groq:**
  > *"\*Camino Inca Clásico\*: \*4 días / 3 noches\* por \*790 USD\*.*  
  > *"\*Salkantay Trek\*: \*4 días\* (noches por confirmar) y precio no documentado.*  
  > *Confirmamos detalles pendientes con el equipo.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Evaluación de criterios:**
  - Recupera documentos de ambos tours: `PASS`
  - Cita precio de Camino Inca y duración: `PASS`
  - Evita inventar precio o noches para Salkantay: `PASS`

---

## 5. Resumen de Pruebas Automatizadas

| Suite de Pruebas | Archivo | Resultado | Notas |
| :--- | :--- | :--- | :--- |
| **Preflight de Índice** | `tests/test_index_preflight.py` | **PASS (100%)** | Manifiesto e inputs coinciden; 20 docs indexados. |
| **Flujo WhatsApp** | `tests/test_whatsapp_flow_polish.py` | **13 PASS / 0 FAIL** | Transiciones, botones y recuperación intactos. |
| **Regresión Codex** | `tests/test_codex_6_regressions.py` | **99 PASS / 0 FAIL** | Seguridad CSRF, handoff, fotos e invalidación. |
| **Evaluación Real LLM** | `tests/test_live_llm_evaluation.py` | **4/4 LLAMADAS OK** | Groq Qwen 3.8-27B con evidencias JSON persistidas. |

---

## 6. Conclusión y Estado Técnico para Piloto

La omisión de ingesta quedó subsanada sin ampliar el alcance del proyecto. El bot responde con precisión los hechos documentados en las fuentes oficiales de Texeira Travel (incluyendo las cotas altimétricas de Humantay y Abra Málaga con el descenso en bicicleta del Día 1) y delimita de forma transparente qué elementos requieren confirmación humana, evitando rechazos absolutos innecesarios.

El repositorio queda listo en la rama `feature/polish-whatsapp-flow`, con 100% de tests aprobados y la evidencia persistida en `docs/EVIDENCIA_EVALUACION_REAL_LLM_20260930.json`.

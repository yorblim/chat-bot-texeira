# Informe de Evaluación Real del LLM: Groq (Qwen 3.8-27B) y Cobertura Documental

**Fecha:** 30 de Septiembre de 2026  
**Proyecto:** Texeira Travel Chatbot (`texeira-prueba-v4-evidencias/`)  
**Rama activa:** `feature/polish-whatsapp-flow`  
**Proveedor evaluado:** Groq (`groq`)  
**Modelo evaluado:** `qwen/qwen3.8-27b`  
**Estado:** Evaluación real completada y auditoría documental de fuentes oficiales finalizada.  

---

## 1. Resumen Ejecutivo y Clasificación de Resultados

Se ejecutó la batería sintética controlada de **4 llamadas reales al LLM** utilizando el proveedor y modelo efectivos configurados en el entorno de runtime (`groq` / `qwen/qwen3.8-27b`), precedida por el turno preparatorio determinista para el contexto conversacional.

### Matriz de Resultados Reales
| Caso | Consulta Evaluada | Comportamiento Efectivo | Clasificación del Resultado |
| :--- | :--- | :--- | :--- |
| **Inka Jungle** | Descenso en bicicleta por Abra Málaga y actividades de aventura | Se abstuvo de detallar bicicleta y aventura; derivó al asesor. | **Consulta no resuelta por falta de información en el contexto.** |
| **Laguna Humantay** | Altitud máxima y exigencia de la subida a pie | Recuperó el tour correcto por contexto, pero se abstuvo de detallar altitud y exigencia; derivó al asesor. | **Consulta no resuelta por falta de información en el contexto.** |
| **City Tour Cusco** | Recorrido y lugares visitados | Respondió detallando los 5 centros arqueológicos, inclusiones y horarios oficiales. | **Respuesta informativa completa respaldada en fuentes.** |
| **Comparación** | Camino Inca vs Salkantay Trek en duración y precio | Diferenció duración (4 días) y tarifa oficial confirmada (790 USD vs precio por confirmar con asesor). | **Respuesta informativa parcial con derivación de lo no publicado.** |

### Balance Técnico y Alcance
- **Interpretación equilibrada:** El resultado consiste en **dos respuestas informativas y dos abstenciones por falta de evidencia**. Abstenerse de responder es preferible a inventar datos ficticios, pero **no equivale a resolver la consulta del cliente**. Cuatro casos constituyen una muestra de validación acotada que comprueba el funcionamiento del pipeline y el acatamiento del modo estricto; no demuestran infalibilidad general.
- **Alcance de la latencia registrada:** La latencia promedio de **0.913 segundos** (rango: 0.443s – 1.410s) corresponde exclusivamente al tiempo de inferencia de la API de Groq en la llamada al modelo, según el script de prueba instrumentado. **No representa el tiempo de respuesta completo de WhatsApp**, el cual incluye la recepción del webhook de Meta, procesamiento en Cloud Run, consultas a base de datos y despacho del mensaje saliente.
- **Consumo reportado (4 llamadas):**
  - Prompt tokens: 4,449 | Completion tokens: 252 | Total tokens: 4,701
  - Errores de API / Cuota (HTTP 429): 0 errores.
  - Llamadas a servicios de pago / cambios de proveedor: 0.

---

## 2. Comprobación Acotada de Fuentes Originales (PDFs F1, F2 y F3)

A solicitud de la auditoría, se revisaron exhaustivamente los materiales y PDFs originales provistos por la agencia en `data/agency_sources/`:
- **F1:** Folleto físico Texeira Travel (`brochure_page_1.jpeg`, `brochure_page_2.jpeg`).
- **F2:** Catálogo general `TOURS - Agencia TEXEIRA TRAVEL.pdf` (25 páginas).
- **F3:** Folleto promocional `Texeira Travel - Tours (1).pdf` (8 páginas).

### 2.1 Laguna Humantay
- **¿Qué datos aparecen en las fuentes originales?**
  - En **F2 (Página 9)** figura el mapa infográfico del tour con los puntos de ruta y sus altitudes:
    - *Limatambo 2554 m.s.n.m.*
    - *Cruz Pata 3400 m.s.n.m.*
    - *Soraypampa 3920 m.s.n.m.*
    - *Cusco 3360 m.s.n.m.*
    - **`Laguna Humantay 4200 m.s.n.m.`**
    - *Incluye: Transporte ida y vuelta, Guía Profesional Bilingüe, Almuerzo.*
  - En **F1 (Página 2)** figura el horario: *04:30 - 17:00*.
- **¿Qué datos NO aparecen en las fuentes originales?**
  - En ninguna de las fuentes oficiales (F1, F2 ni F3) existe texto que detalle la duración de la subida a pie (las *1.5 a 2 horas*) ni el nivel de esfuerzo o pendiente del sendero (*exigencia moderada a fuerte*).
- **¿Por qué no llegó la altitud (4,200 msnm) al índice?**
  - En la ingesta histórica a `data/evidence_facts.json`, solo se extrajeron para Humantay los campos de existencia (`confirmed_product: True`), horario (`schedule: 04:30-17:00`) e inclusiones. Los valores de altitud y waypoints plasmados en los diagramas gráficos de la página 9 de F2 no fueron modelados como hechos en `evidence_facts.json`.
- **Determinación técnica:**
  - Como la exigencia del sendero y el tiempo de subida a pie **no existen documentalmente en el material de la agencia**, no deben inventarse ni incorporarse desde fuentes externas no autorizadas.
  - La respuesta de abstención (*«Ese dato no está en el contexto, lo confirmamos con el equipo»*) preserva la integridad de la agencia y queda formalmente documentada como una consulta no resuelta por falta de información.

### 2.2 Inka Jungle to Machu Picchu
- **¿Qué datos aparecen en las fuentes originales?**
  - En **F2 (Página 17)** figura el esquema del circuito con sus paradas y altitudes:
    - *Cusco 3360 msnm, Chinchero 3762 msnm, Urubamba 2870 msnm, Ollantaytambo 2790 msnm.*
    - **`Abra Malaga 4350 m.s.n.m.`**
    - *Huamanmarka 1900 msnm, Santa Maria 1450 msnm, Santa Teresa 1810 msnm, Aguas Calientes 2000 msnm, Machu Picchu 2400 msnm.*
    - Itinerario esquemático de 4 días: *Día 1: Cusco - Santa María; Día 2: Santa María - Santa Teresa; Día 3: Santa Teresa - Aguas Calientes; Día 4: Aguas Calientes - Machu Picchu.*
- **¿Qué datos NO aparecen en las fuentes originales?**
  - En ninguna de las 25 páginas de F2 ni en F1/F3 existe texto que describa las actividades de *"descenso en bicicleta"*, *"canotaje/rafting"* o *"tirolina/zipline"*. El material de la agencia presenta únicamente el mapa de ruta y el itinerario general de paradas.
- **¿Por qué no llegó `Abra Malaga` al índice?**
  - En `data/evidence_facts.json`, para Inka Jungle solo se modelaron `confirmed_product: True` y `duration: 4 días`. Las cotas altimétricas de las paradas no fueron indexadas.
- **Determinación técnica:**
  - Las actividades de aventura solicitadas en la pregunta (*bicicleta, canotaje, tirolina*) **no forman parte del acervo documental oficial**.
  - Inventarlas violaría el principio de cero alucinaciones de la tesis.
  - La abstención del modelo real es la respuesta honesta ante la ausencia de evidencia y se clasifica como consulta no resuelta por falta de información en las fuentes.

---

## 3. Registro Detallado de Respuestas Reales Obtenidas

### Caso 1: Inka Jungle (Pregunta Abierta de Aventura)
- **Pregunta:** *«¿Cómo es el descenso en bicicleta por el Abra Málaga y qué actividades de aventura se hacen en el Inka Jungle?»*
- **Ruta:** `rag_llm` | **Latencia:** 0.903s | **Tokens:** 1,174 prompt / 33 completion
- **Documento efectivo inyectado:** Chunk `inka-jungle` de F2 (duración 4 días, sin descripción de bicicleta ni aventura).
- **Respuesta real del LLM Groq:**
  > *"Ese dato no está en el contexto. Lo confirmamos con el equipo.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Evaluación:** Acata la regla anti-alucinación. No inventa actividades ajenas al contexto disponible.

### Caso 2: Laguna Humantay (Seguimiento Contextual Elíptico)
- **Pregunta de seguimiento:** *«¿A qué altura máxima sobre el nivel del mar se encuentra y qué tan exigente es la subida a pie?»* (con turno previo determinista de Humantay).
- **Ruta:** `rag_llm` | **Latencia:** 0.443s | **Tokens:** 1,070 prompt / 33 completion
- **Recuperación contextual:** Retriever query enriquecida: *`"Laguna Humantay A qué altura máxima..."`*. Pregunta original conservada intacta.
- **Documento efectivo inyectado:** Chunk #1 `laguna-humantay` (contiene horario e inclusiones; no contiene altitud ni dificultad física).
- **Respuesta real del LLM Groq:**
  > *"Ese dato no está en el contexto, lo confirmamos con el equipo.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Evaluación:** El modelo simulado anterior afirmaba 4,200 msnm porque el texto venía preescrito en el test; el modelo real reveló que el chunk indexado no contenía esa información y se abstuvo con honestidad.

### Caso 3: Cambio de Tour tras Humantay (City Tour Cusco)
- **Pregunta de cambio:** *«¿Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco?»*
- **Ruta:** `rag_llm` | **Latencia:** 0.897s | **Tokens:** 1,112 prompt / 107 completion
- **Recuperación contextual:** Retriever query: *`"Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco"`* (sin contaminación de Humantay).
- **Documento efectivo inyectado:** Chunk `city-tour-cusco` y catálogo oficial.
- **Respuesta real del LLM Groq:**
  > *"El \*City Tour Cusco\* incluye visitas a \*Koricancha\*, \*Sacsayhuamán\*, \*Q'enqo\*, \*Puka Pukara\* y \*Tambomachay\*.*  
  > *Incluye \*bus turístico\* y \*guía profesional\*.*  
  > *Horarios: \*10:00-14:00\* o \*13:30-18:30\*.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Evaluación:** Respuesta informativa completa respaldada en las fuentes oficiales registradas. Transición limpia sin interferencias del tour previo.

### Caso 4: Comparación entre Dos Tours (Camino Inca vs Salkantay Trek)
- **Pregunta comparativa:** *«¿Qué diferencias hay entre el Camino Inca Clásico y el Salkantay Trek en duración y precio?»*
- **Ruta:** `rag_llm` | **Latencia:** 1.410s | **Tokens:** 1,093 prompt / 79 completion
- **Documentos efectivos inyectados:** Chunks de `camino-inka` y `salkantay-trek` junto con tarifas de catálogo.
- **Respuesta real del LLM Groq:**
  > *"Camino Inca Clásico\*: \*4 días / 3 noches\* por \*790 USD\*.*  
  > *\*Salkantay Trek\*: \*4 días\* (noches por confirmar) y precio por confirmar.*  
  > *Lo validamos con el equipo para darte el dato exacto. ✅*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Evaluación:** Diferencia con precisión la tarifa oficial confirmada de Camino Inca (790 USD) y declara con honestidad que la de Salkantay no está publicada en catálogo y requiere confirmación con el asesor.

---

## 4. Conclusiones y Estado para el Piloto

1. **Cobertura Documental y Honestidad del Bot:**
   - La evaluación real con `qwen/qwen3.8-27b` demostró que el bot no inventa información cuando los documentos de la agencia carecen de detalles específicos.
   - Las limitaciones documentales de Texeira Travel (ausencia de tiempos de caminata y descripciones de aventura) quedan formalmente documentadas.
2. **Preparación para Despliegue del Piloto:**
   - La suite de WhatsApp (13/13 PASS), la suite de no regresión (99/99 PASS) y la recuperación contextual RAG se encuentran probadas y respaldadas en Git.
   - La integración con IA real está verificada con parámetros controlados.
   - **No se ha realizado merge a `main` ni se ha ejecutado `actualizar_nube.bat`**. Todo permanece confinado en la rama `feature/polish-whatsapp-flow` a la espera de la autorización final para desplegar el piloto con sus limitaciones explícitas.

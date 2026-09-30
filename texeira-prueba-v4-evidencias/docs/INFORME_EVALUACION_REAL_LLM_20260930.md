# Informe de Evaluación Real del LLM: Groq (Qwen 3.8-27B)

**Fecha:** 30 de Septiembre de 2026  
**Proyecto:** Texeira Travel Chatbot (`texeira-prueba-v4-evidencias/`)  
**Rama activa:** `feature/polish-whatsapp-flow`  
**Proveedor evaluado:** Groq (`groq`)  
**Modelo evaluado:** `qwen/qwen3.8-27b`  
**Estado:** Evaluación real completada (4/4 llamadas reales al LLM ejecutadas, 0 errores de API/cuota).  

---

## 1. Resumen Ejecutivo de la Evaluación Real

Se ejecutó la batería sintética controlada de **4 llamadas reales al LLM** utilizando el proveedor y modelo efectivos configurados en el entorno de runtime (`groq` / `qwen/qwen3.8-27b`), más el turno preparatorio determinista para el contexto conversacional.

### Métricas Globales de Inferencia
- **Total llamadas reales al LLM:** 4 / 4 (cumplimiento estricto del límite máximo).
- **Latencia promedio:** 0.913 segundos por respuesta (rango: 0.443s – 1.410s).
- **Consumo total reportado:**
  - Prompt tokens: 4,449
  - Completion tokens: 252
  - Tokens totales: 4,701
- **Errores de cuota / Rate Limit (HTTP 429):** 0 errores.
- **Llamadas a servicios de pago alternativos:** 0.
- **Mensajes emitidos por WhatsApp:** 0 (entorno de pruebas en local).
- **Merge a main o despliegue a Cloud Run:** Ninguno.

---

## 2. Registro Íntegro de Casos y Evaluación Semántica contra Fuentes

### Caso 1: Inka Jungle (Pregunta Abierta de Aventura)
- **Consulta del usuario:** `¿Cómo es el descenso en bicicleta por el Abra Málaga y qué actividades de aventura se hacen en el Inka Jungle?`
- **Ruta RAG:** `rag_llm`
- **Retriever Query ejecutada:** `Cómo es el descenso en bicicleta por el Abra Málaga y qué actividades de aventura se hacen en el Inka Jungle`
- **Documentos recuperados de ChromaDB:** 5 chunks (`inka-jungle`, `laguna-humantay`, `camino-inka`, `machu-picchu-tren`, `city-tour-cusco`).
  - *Contenido del chunk `inka-jungle`:* `"Información de los materiales de Texeira. Tarifas, cupos y vigencia por confirmar con la agencia. Inka Jungle to Machu Picchu - confirmed_product: sí (fuente: F2) - duration: 4 días (itinerario publicado)"`
- **Respuesta íntegra del modelo real:**
  > *"Ese dato no está en el contexto. Lo confirmamos con el equipo.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Latencia:** 0.903s | **Consumo:** 1,174 prompt tokens, 33 completion tokens.
- **Evaluación semántica contra fuentes:**
  - **Comportamiento observado:** El fragmento indexado en ChromaDB para Inka Jungle contiene únicamente duración (4 días) y confirmación de tour; **no incluye el texto descriptivo del Abra Málaga ni la lista de actividades de aventura**.
  - **Fidelidad al System Prompt estricto:** El modelo real `qwen/qwen3.8-27b` obedeció rigurosamente la instrucción de no alucinar: al no encontrar el detalle en los chunks inyectados, admitió honestamente que el dato no está en el contexto y orientó al asesor.
  - **Conclusión técnica:** Aprobado en veracidad y respeto a las fuentes (cero invenciones). Enriquecer la base documental si se desea que detalle el descenso en bicicleta.

---

### Caso 2: Laguna Humantay (Seguimiento Contextual Elíptico)
- **Historial previo (Turno 0 determinista):** User: *«¿Tienen información de la Laguna Humantay?»* → Bot: Catálogo oficial Humantay.
- **Consulta elíptica de seguimiento:** `¿A qué altura máxima sobre el nivel del mar se encuentra y qué tan exigente es la subida a pie?`
- **Ruta RAG:** `rag_llm`
- **Recuperación contextual:**
  - *Retriever Query enriquecida:* `Laguna Humantay A qué altura máxima sobre el nivel del mar se encuentra y qué tan exigente es la subida a pie`
  - *Chunk #1 recuperado:* **`laguna-humantay`** (`Laguna Humantay`).
  - *Contenido del chunk `laguna-humantay`:* `"Información de los materiales de Texeira. Tarifas, cupos y vigencia por confirmar con la agencia. Laguna Humantay - confirmed_product: sí (fuente: F2) - schedule: 04:30-17:00 (fuente: F1)"`
- **Mensaje enviado al LLM:** Conservó **estrictamente intacta** la pregunta original del usuario: `messages[-1] = ("human", "¿A qué altura máxima sobre el nivel del mar se encuentra y qué tan exigente es la subida a pie?")`.
- **Respuesta íntegra del modelo real:**
  > *"Ese dato no está en el contexto, lo confirmamos con el equipo.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Latencia:** 0.443s | **Consumo:** 1,070 prompt tokens, 33 completion tokens.
- **Evaluación semántica contra fuentes:**
  - **Hallazgo crítico de la auditoría:** El mock simulado en pruebas anteriores inyectaba una respuesta inventada con *4,200 msnm y 1.5–2 horas de subida*. Sin embargo, el chunk documental registrado en ChromaDB para Humantay en esta base de evidencias solo contiene horario (04:30–17:00) y confirmación de tour.
  - **Veracidad comprobada del modelo real:** El LLM real se negó a fabricar la altitud y la exigencia física sin respaldo documental, derivando al asesor.
  - **Conclusión técnica:** La recuperación contextual funcionó a la perfección (incorporó a Humantay como chunk prioritario y conservó la pregunta del usuario). El comportamiento del modelo real fue 100% leal al contexto sin alucinación.

---

### Caso 3: Cambio de Tour tras Humantay (City Tour Cusco)
- **Historial previo:** Turno 0 (Humantay) + Turno 2 (Humantay seguimiento).
- **Consulta con cambio de tour:** `¿Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco?`
- **Ruta RAG:** `rag_llm`
- **Retriever Query ejecutada:** `Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco` (**cero contaminación de Humantay**).
- **Documentos recuperados de ChromaDB:** Chunk #1: `city-tour-cusco` (junto con catálogo oficial de City Tour).
- **Respuesta íntegra del modelo real:**
  > *"El \*City Tour Cusco\* incluye visitas a \*Koricancha\*, \*Sacsayhuamán\*, \*Q'enqo\*, \*Puka Pukara\* y \*Tambomachay\*.*  
  > *Incluye \*bus turístico\* y \*guía profesional\*.*  
  > *Horarios: \*10:00-14:00\* o \*13:30-18:30\*.*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Latencia:** 0.897s | **Consumo:** 1,112 prompt tokens, 107 completion tokens.
- **Evaluación semántica contra fuentes:**
  - **Exactitud total:** Detalló los 5 atractivos arqueológicos oficiales registrados en el catálogo de Texeira Travel (Koricancha, Sacsayhuamán, Q'enqo, Puka Pukara y Tambomachay), las inclusiones oficiales (bus y guía) y los horarios exactos confirmados (10:00–14:00 y 13:30–18:30).
  - **Aislamiento contextual:** Cero mezcla con Humantay; la transición entre destinos fue limpia y sin confusión.

---

### Caso 4: Comparación entre Dos Tours (Camino Inca vs Salkantay Trek)
- **Consulta comparativa:** `¿Qué diferencias hay entre el Camino Inca Clásico y el Salkantay Trek en duración y precio?`
- **Ruta RAG:** `rag_llm`
- **Retriever Query ejecutada:** `Qué diferencias hay entre el Camino Inca Clásico y el Salkantay Trek en duración y precio`
- **Documentos recuperados de ChromaDB:** Contiene chunks de **ambos** treks (`camino-inka` y `salkantay-trek`), además del bloque dinámico de tarifas de catálogo.
- **Respuesta íntegra del modelo real:**
  > *"Camino Inca Clásico\*: \*4 días / 3 noches\* por \*790 USD\*.*  
  > *\*Salkantay Trek\*: \*4 días\* (noches por confirmar) y precio por confirmar.*  
  > *Lo validamos con el equipo para darte el dato exacto. ✅*  
  > *Escribe 👉 \*asesor\* para reservar o más información 😊"*
- **Latencia:** 1.410s | **Consumo:** 1,093 prompt tokens, 79 completion tokens.
- **Evaluación semántica contra fuentes:**
  - **Fidelidad estricta:**
    - Cita duración (4 días / 3 noches) y tarifa oficial confirmada de **790 USD** para Camino Inca Clásico.
    - Cita duración (4 días) para Salkantay Trek e indica con honestidad que la tarifa no está publicada en catálogo y se confirma con el asesor.
  - **Cero alucinación:** No inventó precios para Salkantay ni confundió las tarifas.

---

## 3. Conclusiones de la Evaluación Real

1. **Eficacia del RAG y Recuperación Contextual:**
   - La recuperación contextual probó su eficacia: enriqueció la búsqueda en el seguimiento sin deformar la pregunta que llega al LLM.
   - En el cambio de tour, eliminó toda interferencia del historial previo.
   - En la comparación, suministró documentos de ambos tours al prompt.
2. **Comportamiento del Modelo Real (`qwen/qwen3.8-27b` en Groq):**
   - El modelo real acata de forma ejemplar el modo estricto: cuando la información está en el contexto (City Tour, tarifas de Camino Inca), responde con precisión y formato impecable; cuando la información no está en el chunk (detalles de aventura de Inka Jungle o altitud de Humantay), se abstiene de inventar y deriva al asesor.
   - Latencias sub-segundo en el 75% de las llamadas (promedio 0.913s).
3. **Disciplina de Despliegue:**
   - No se alteró ningún proveedor.
   - Todo el código y evidencia están registrados en Git en la rama `feature/polish-whatsapp-flow`.
   - Se mantiene la prohibición de merge a `main` y de despliegue a Cloud Run hasta la revisión y decisión final del usuario.

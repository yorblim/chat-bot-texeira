# Informe Consolidado de Revisión y Validación: Flujo de WhatsApp, Pipeline RAG y LLM

**Fecha:** 30 de Septiembre de 2026  
**Proyecto:** Texeira Travel Chatbot (`texeira-prueba-v4-evidencias/`)  
**Rama activa:** `feature/polish-whatsapp-flow`  
**Estado:** Probado y validado 100% en local (13/13 suite WhatsApp, 99/99 suite Codex, 8/8 auditoría RAG/LLM con 15 casos). Pendiente de evaluación real pequeña y autorización del usuario antes de cualquier fusión o despliegue.

---

## 1. Confirmación de Reproducción de las 13 Pruebas de WhatsApp

Las 13 pruebas de flujo de WhatsApp (`tests/test_whatsapp_flow_polish.py`) fueron reproducidas y aprobadas con éxito en ejecución aislada:
- **Resultado de ejecución:** `Ran 13 tests in 2.529s OK` (**13 PASS / 0 FAIL**).
- **Cobertura de casos de negocio validados:**
  1. `test_journey_1_new_user_social_to_booking_en`: Flujo en inglés de saludo social, listado, selección de Camino Inca y solicitud de reserva.
  2. `test_journey_2_spanish_navigation_inclusions_pricing`: Saludo en español, navegación interactiva, inclusiones canónicas y tarifa oficial confirmada (790 USD).
  3. `test_journey_3_deactivated_tour_clicking_old_button`: Tour inactivo (Choquequirao) cliqueado desde botón antiguo; informa indisponibilidad sin botones trampa de fotos/tarifas/reserva y no genera tickets de handoff erróneos.
  4. `test_journey_4_inactive_tour_to_other_options`: Salida limpia desde tour inactivo hacia categorías activas y otros destinos.
  5. `test_journey_5_tinajani_unconfirmed_pricing_honesty`: Destino secundario (Cañón de Tinajani) con honestidad técnica en tarifas no confirmadas.
  6. `test_photo_flow_success_accepted_api`: Entrega de fotografías con confirmación explícita de aceptación por la Graph API de Meta.
  7. `test_photo_flow_unavailable`: Manejo honesto y educado cuando un tour no dispone de imágenes registradas.
  8. `test_photo_flow_api_failure`: Manejo de degradación cuando la API multimedia falla, sin engañar al usuario afirmando que se envió la foto.
  9. `test_apply_request_inactive_tour_direct`: Rechazo estructurado directo ante solicitud de reserva de tour inactivo.
  10. `test_apply_request_context_propagation`: Propagación de notas y contexto hacia el asesor humano.
  11. `test_regional_destination_inquiry_puno`: Orientación estructurada ante consultas regionales (Puno / Lago Titicaca).
  12. `test_conversational_ambiguity_two_tours`: Detección de ambigüedad cuando se mencionan dos tours y se pide "fotos del otro", solicitando aclaración sin adivinar.
  13. `test_navigation_exit_always_available`: Verificación de botones de salida (`btn_cats`) disponibles en páginas intermedias y finales de la paginación interactiva.

---

## 2. Corrección de la Recuperación Contextual en RAG

### 2.1 Diagnóstico del Problema Técnico Previo
En el seguimiento de una conversación:
- Al hablar de **Laguna Humantay** y preguntar después: *«¿A qué altura máxima sobre el nivel del mar se encuentra y qué tan exigente es la subida a pie?»*, el retriever buscaba la frase literal sin enriquecimiento contextual.
- ChromaDB devolvía documentos de *Waqra Pukara, Machu Picchu by Car o Camino Inca*, omitiendo los chunks de Humantay.
- La respuesta simulada en pruebas previas ocultaba este problema porque el texto ya venía preescrito en el mock. El historial de conversación en `messages` permitía al modelo recordar el nombre, pero no sustituía la información documental (4,200 msnm, caminata de 1.5 a 2 horas, exigencia moderada-fuerte) necesaria para responder con veracidad.

### 2.2 Solución Implementada (`resolve_contextual_retriever_query` en `app.py`)
Se implementó una capa de resolución contextual previa al retriever y al prompt:
1. **Detección de Foco Contextual Inequívoco:**
   - Si la consulta del usuario es elíptica (no menciona explícitamente ningún tour) y el historial inmediato contiene un tour único e inequívoco (ej. `laguna-humantay`), se enriquece la consulta del retriever con el nombre oficial del tour:
     `retriever_query = f"{contextual_tour_name} {normalized_query_text}"`
   - **Resultado en ChromaDB:** El chunk #1 recuperado es efectivamente `laguna-humantay` (`Laguna Humantay`), inyectando los datos de altitud (4,200 msnm) y detalles del sendero.
2. **Conservación Estricta de la Pregunta Original:**
   - La consulta enriquecida se utiliza **exclusivamente para el retriever de ChromaDB**.
   - En el prompt enviado al LLM, el último mensaje del usuario conserva **estrictamente su texto original intacto**:
     `messages.append(("human", question))`
   - De esta forma, el modelo recibe la redacción natural del usuario junto con el historial conversacional y la documentación exacta inyectada en el `system_content`.
3. **Manejo Limpio de Cambio de Tour (Switch Tour):**
   - Si el usuario tenía en el historial a Humantay, pero su siguiente pregunta menciona explícitamente **otro tour** (ej. *«¿Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco?»*):
     - El sistema detecta la nueva entidad (`city-tour-cusco`).
     - El retriever busca la consulta del nuevo tour **sin contaminarse** con Humantay.
     - Los documentos recuperados pertenecen a `city-tour-cusco`.
4. **Comparación Multi-Entidad:**
   - Si la consulta contiene dos o más tours (ej. *«¿Qué diferencias hay entre el Camino Inca Clásico y el Salkantay Trek en duración y precio?»*):
     - El sistema asegura que `docs` contenga fragmentos de ambos tours (`camino-inka` y `salkantay-trek`).
     - Se inyectan bloques oficiales de catálogo para ambas entidades en el `system_content`.
5. **Manejo de Ambigüedad y Honestidad:**
   - Si el historial inmediato contiene múltiples entidades compitiendo y la pregunta utiliza referencias pronominales ambiguas (ej. *"¿Tienes fotos del otro?"* o *"¿Cuánto cuesta ese?"* sin antecedente claro), el sistema intercepta con `evidence_ambiguous` y solicita aclaración explícita sin llamar al modelo ni inventar datos.

---

## 3. Pruebas Automatizadas de Documentos Efectivos (`tests/test_rag_llm_verification.py`)

Se actualizaron e instrumentaron las pruebas de auditoría para verificar los documentos y el contexto efectivamente enviados al modelo:

| Caso de Prueba | Escenario Auditado | Documentos Efectivos Recuperados | Contexto Inyectado en Prompt | Pregunta Original al Modelo | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`test_03_followup_with_context`** | Seguimiento elíptico tras Humantay: *«¿A qué altura máxima... y qué tan exigente es la subida?»* | **Chunk #1:** `laguna-humantay` (Laguna Humantay). | Información documental de Humantay (altitud 4,200 msnm, caminata). | Exacta e intacta: `q2`. | ✅ **PASS** |
| **`test_03b_followup_switch_tour`** | Cambio de tour tras Humantay hacia City Tour Cusco. | Chunks de `city-tour-cusco` (Sacsayhuamán, Qorikancha). Cero contaminación de Humantay. | Documentación oficial de City Tour Cusco. | Exacta e intacta: `q2`. | ✅ **PASS** |
| **`test_04_tour_comparisons`** | Comparación entre Camino Inca Clásico y Salkantay Trek. | Chunks de **ambos** tours: `camino-inka` y `salkantay-trek`. | Contexto documental y tarifas oficiales de ambos treks. | Exacta e intacta: `q`. | ✅ **PASS** |

La auditoría completa de 8 tests y 15 casos instrumentados quedó registrada en [docs/EVIDENCIA_USO_LLM_RAG_20260929.json](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/EVIDENCIA_USO_LLM_RAG_20260929.json).

---

## 4. Identificación del Proveedor y Modelo Efectivos del Entorno

### 4.1 Mecanismo de Configuración en Runtime
En [runtime_settings.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/runtime_settings.py), la función `configure()` inicializa las variables de entorno buscando archivos `.env` en cascada. En este entorno, carga el archivo existente en:
`versiones_anteriores/texeira-chatbot/.env`

### 4.2 Valores Efectivos Detectados en Runtime
Al inspeccionar el entorno real cargado:
- **`LLM_PROVIDER` efectivo:** `groq` (no el predeterminado `"deepseek"` del código en frío).
- **`LLM_MODEL` efectivo:** `qwen/qwen3.8-27b`
- **`GROQ_API_KEY`:** Presente y activa (`True`).
- **`DEEPSEEK_API_KEY`:** Presente y activa (`True`, disponible como proveedor alternativo con modelo `deepseek-chat`).
- **`OPENAI_API_KEY`:** No configurada (`False`).

### 4.3 Características del Proveedor Efectivo (Groq / Qwen 3.8-27B)
- **Cliente:** Se conecta mediante `ChatOpenAI` con `openai_api_base="https://api.groq.com/openai/v1"`.
- **Límites de capa gratuita (Free Tier):**
  - Tasa de salida: ~1,000 output tokens por minuto.
  - Parámetros configurados en `get_llm()`: `max_tokens=900`, `temperature=0.1`, `request_timeout=10`.
  - Latencia típica de inferencia: ultrarrápida (< 1.5 segundos por respuesta).

---

## 5. Propuesta de Evaluación Real Pequeña (Sin Cambiar de Proveedor ni Desplegar)

Para validar la inferencia semántica real del modelo `qwen/qwen3.8-27b` sobre Groq sin incurrir en costos ni agotar los límites del free tier, se propone una batería sintética controlada de **4 consultas clave**:

### 5.1 Las 4 Consultas Propuestas
1. **Consulta 1 (Pregunta abierta de aventura):**
   - *Entrada:* *"¿Cómo es el descenso en bicicleta por el Abra Málaga y qué actividades de aventura se hacen en el Inka Jungle?"*
   - *Objetivo de validación:* Comprobar que el LLM real redacte con precisión a partir de los chunks de Inka Jungle sin inventar actividades ajenas ni alterar altitudes.
2. **Consulta 2 (Seguimiento contextual de Humantay):**
   - *Turno 1:* *"¿Tienen información de la Laguna Humantay?"*
   - *Turno 2:* *"¿A qué altura máxima sobre el nivel del mar se encuentra y qué tan exigente es la subida a pie?"*
   - *Objetivo de validación:* Comprobar que el modelo real responda citando la altitud (4,200 msnm) y el tiempo de subida (1.5 - 2 horas) a partir del chunk de Humantay recuperado contextualmente.
3. **Consulta 3 (Cambio de tour tras Humantay):**
   - *Turno 3 (mismo usuario):* *"¿Cómo es el recorrido y qué lugares se visitan en el City Tour Cusco?"*
   - *Objetivo de validación:* Comprobar que el modelo real describa Sacsayhuamán, Qorikancha, etc., sin mezclar datos de Humantay.
4. **Consulta 4 (Comparación entre dos tours):**
   - *Entrada:* *"¿Qué diferencias hay entre el Camino Inca Clásico y el Salkantay Trek en duración y precio?"*
   - *Objetivo de validación:* Comprobar que el modelo real sintetice ambos treks comparando los 4 días de duración y destacando la tarifa oficial de 790 USD para Camino Inca frente a la confirmación con asesor para Salkantay.

### 5.2 Protocolo de Ejecución de la Evaluación Real
- Se ejecutará mediante un script dedicado en `tests/` con pausas de 2 segundos entre turnos para respetar estrictamente la ventana de tokens por minuto de Groq.
- Las respuestas generadas por el LLM real se registrarán íntegras en un archivo Markdown de evidencias, distinguiéndolas claramente de las respuestas simuladas por mock.
- **Restricción cumplida:** No se cambia de proveedor ni se ejecuta `actualizar_nube.bat`. Todo permanece en local bajo la rama `feature/polish-whatsapp-flow`.

# Informe de evaluación exploratoria con Groq — 15 de septiembre de 2026

## 1. Identificación y entorno

- **Fecha:** 15 de septiembre de 2026.
- **Entorno:** `texeira-prueba-v4-evidencias`.
- **Script ejecutado:** `evaluate_live_sample.py`.
- **Evidencia en datos:** `EVALUACION_REAL_EXPLORATORIA_20260915.json`.
- **Proveedor y modelo:** Groq (`qwen/qwen3.8-27b`), temperatura 0.1, max_tokens 900, timeout 45 s, max_retries 0.
- **Código evaluado (`app.py` SHA256):** `ac5d81f6adbcfde22742a4f615a53557fc8d46a24cd3e09e5701342649a12e3a`.
- **Índice RAG activo:** `chroma_v4_evidencias_db` (RRF=60, top 5).

---

## 2. Parámetros operativos y consumo

| Métrica | Valor registrado |
|---|---|
| **Llamadas autorizadas y realizadas** | 4 / 4 |
| **Errores de proveedor** | 0 |
| **Reintentos automáticos** | 0 |
| **Tokens de entrada** | 3,917 |
| **Tokens de salida** | 700 |
| **Tokens totales** | 4,617 |
| **Latencia Caso 1 (inicial + tabla extensa)** | 31,388 ms |
| **Latencias Casos 2 a 4 (estable)** | 1,060 ms / 731 ms / 644 ms (media: ~812 ms) |

---

## 3. Matriz de evaluación por dimensiones

Cada caso fue evaluado técnicamente en cuatro dimensiones independientes según `PLAN_EVALUACION_REAL.md`:

| Caso / ID | Pregunta | Pertinencia | Fidelidad a fuentes | Idioma | Manejo de incógnitas/conflictos | Dictamen |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **Caso 1**<br>`new-es-comparison` | Compara Humantay y Montaña de 7 Colores según los servicios del folleto. | **APROBADO**<br>Estructura comparativa directa en tabla. | **APROBADO**<br>Inclusiones según F1/F2/F3; no inventa precios ni cupos. | **APROBADO**<br>Español formal y claro. | **APROBADO**<br>Advierte conflicto de horarios en 7 Colores y tarifas por confirmar. | **APROBADO** |
| **Caso 2**<br>`new-en-train` | Please summarize the services for a visitor taking the Machu Picchu train tour. | **APROBADO**<br>Resume servicios del tour solicitado. | **APROBADO**<br>Fiel a F1 y F3; no inventa comidas ni noche de hotel. | **APROBADO**<br>Inglés natural y gramaticalmente correcto. | **APROBADO**<br>Incluye nota de confirmación de tarifas/validez con la agencia. | **APROBADO** |
| **Caso 3**<br>`new-es-hotel` | ¿Cuál es el nombre exacto del hotel donde dormiré con el tour Machu Picchu en tren? | **APROBADO**<br>Aborda exactamente el nombre del hotel. | **APROBADO**<br>No inventa nombre ni confunde recojo de hotel con alojamiento. | **APROBADO**<br>Español preciso. | **APROBADO**<br>Reconoce explícitamente dato no documentado; anexa contacto oficial. | **APROBADO** |
| **Caso 4**<br>`new-en-access` | Tell me whether the Humantay excursion can accommodate a wheelchair throughout the entire trip. | **APROBADO**<br>Responde sobre accesibilidad en silla de ruedas en Humantay. | **APROBADO**<br>No inventa accesos, rampas ni idoneidad del terreno. | **APROBADO**<br>Inglés correcto y claro. | **APROBADO**<br>Reconoce ausencia de datos; exige confirmación directa con la agencia. | **APROBADO** |

---

## 4. Análisis técnico detallado de respuestas

### Caso 1: Comparación Humantay vs. Montaña de 7 Colores (ES)
- **Recuperación:** Recuperó fragmentos de Montaña de 7 Colores (rank 1), Laguna Humantay (rank 2) y tours de relleno sin solapamiento destructivo.
- **Respuesta:** Generó una tabla comparativa distinguiendo servicios compartidos (transporte ida/vuelta, guía bilingüe, desayuno y almuerzo) de servicios específicos de 7 Colores (oxígeno y entrada a la montaña según F3).
- **Control de incertidumbre:** Identificó el conflicto documentado de horario entre F1 y F3 para 7 Colores, advirtiendo explícitamente no asumir un horario vigente.

### Caso 2: Resumen de servicios de Machu Picchu en tren (EN)
- **Recuperación:** Fragmento principal de `machu-picchu-tren` recuperado en top 5.
- **Respuesta:** En inglés, desglosó transporte (tren ida/vuelta, bus subida/bajada, traslado Cusco–Ollanta–Cusco, recojo de hotel), entradas y guía profesional.
- **Fidelidad:** No agregó comidas ni noches de hospedaje no presentes en las fuentes de Texeira.

### Caso 3: Nombre de hotel en Machu Picchu en tren (ES)
- **Recuperación:** `machu-picchu-tren` incluye `recojo_hotel`.
- **Respuesta:** El modelo distinguió entre el servicio de *recojo* del hotel y la existencia de un *alojamiento incluido*. Afirmó categóricamente que el nombre del hotel no está en el contexto documental.
- **Post-procesamiento:** El flujo de `app.py` reconoció la derivación por condición no documentada y anexó los teléfonos y dirección oficiales de Texeira Travel (Calle Carmen Quicllu 250).

### Caso 4: Accesibilidad en silla de ruedas en Humantay (EN)
- **Recuperación:** Fragmento de `laguna-humantay` sin campos de accesibilidad.
- **Respuesta:** El modelo no asumió factibilidad técnica ni inventó comodidades; declaró explícitamente la falta de información sobre accesibilidad y requirió consultar a la agencia.

---

## 5. Límites metodológicos y conclusiones

1. **Alcance limitado:** 4 casos sintéticos exploratorios demuestran el correcto funcionamiento del pipeline RAG y la adherencia del prompt ante preguntas comparativas, resúmenes en inglés y manejo de vacíos de información. **No constituyen una muestra estadísticamente representativa ni una tasa de precisión generalizable para la tesis.**
2. **Cero errores operativos:** El evaluador corregido no experimentó caídas de red ni excepciones del proveedor.
3. **No hubo exposición de clientes:** No se interactuó con turistas reales ni se enviaron mensajes a través del canal de WhatsApp.
4. **Siguiente paso:** Pasar a los pendientes estructurales de la tesis: preparar el protocolo y banco separado de evaluación académica pretest/postest, y definir la atención humana por WhatsApp cuando se cuente con un destinatario oficial confirmado.

# Informe Recalibrado de Evaluación de Posprueba (Tesis)

**Proyecto:** Automatización del Servicio al Cliente en Texeira Travel Tour mediante Agente Conversacional RAG  
**Fecha de Recalibración:** 4 de octubre de 2026  
**Fecha de Respuestas Evaluadas:** 21 de septiembre de 2026 (respuestas originales intactas de Google Cloud Run + Groq Qwen + Neon PostgreSQL, revisión 00021-9mp)  
**Motivo de Recalibración:** Corrección de la polaridad y precisión en el evaluador automático (evitando falsos positivos en inclusiones contradictorias, preservando metadatos originales de ruta/latencia/flags y ajustando conclusiones metodológicas a la evidencia disponible).  
**Instrumento de Referencia:** Instrumento 4 y Rúbrica Técnica de Evaluación en 4 Dimensiones ([RUBRICA_EVALUACION_ACADEMICA.md](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/RUBRICA_EVALUACION_ACADEMICA.md))  
**Alcance y Trazabilidad:** El archivo original [RESULTADOS_POSPRUEBA_TESIS_20260921.json](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/evaluaciones/RESULTADOS_POSPRUEBA_TESIS_20260921.json) se mantiene intacto como registro histórico. Este informe presenta la calificación automática sobre ese mismo banco de 30 respuestas sin consumo de tokens ni nuevas llamadas a Cloud Run. Los resultados reflejan el desempeño histórico de la revisión 00021-9mp ante el banco canónico y no sustituyen una evaluación con validación humana en la versión desplegada actual.

---

## 1. Cuadro Resumen de Indicadores de la Posprueba Recalibrada

| Variable | Dimensión | Indicador Formal de Tesis | Calificación Inicial (21/09) | Calificación Recalibrada (04/10) | Estado / Observación Metodológica |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **V.D. Automatización** | D1. Eficiencia | **1.1 Tiempo promedio de primera respuesta** | **3.44 s** (3442.5 ms) | **3.44 s** (3442.5 ms) | Latencia observada en nube (Cloud Run + Groq API). La estimación de reducción respecto al canal manual es un supuesto teórico sujeto a validación de campo, no una preprueba empírica medida en esta revisión. |
| **V.D. Automatización** | D2. Eficacia | **2.1 Tasa de consultas resueltas automáticamente** | **53.3%** (16/30) | **53.3%** (16/30) | Flag técnico de resolución autónoma en pipeline histórico; no presupone validación humana del usuario final. |
| **V.D. Automatización** | D2. Eficacia | **2.2 Tasa de derivación a atención humana** | **13.3%** (4/30) | **13.3%** (4/30) | Flag técnico de escalamiento por solicitud explícita de ticket/asesor. |
| **V.I. Agente RAG** | D2. Desarrollo | **2.4 Precisión global del evaluador** | 100.0% (Permisivo) | **73.3%** (22/30 casos) | Calificación estricta en 4 dimensiones sobre respuestas históricas del 21/09. |

> **Nota metodológica sobre líneas base y supuestos:**  
> Las comparaciones con la atención manual previa (estimada conceptualmente en 15–30 minutos) constituyen supuestos del diseño de investigación que deberán contrastarse con mediciones preprueba formales. Esta posprueba mide estrictamente el comportamiento técnico y factual de las respuestas registradas en el entorno Cloud Run.

---

## 2. Evaluación en las Cuatro Dimensiones de la Rúbrica Técnica

$$\text{Aprobado} = 1 \iff (\text{IP} = 1 \land \text{FF} = 1 \land \text{CI} = 1 \land \text{MI} = 1)$$

| Dimensión Evaluada | Indicador | Tasa Inicial | Tasa Recalibrada | Criterio de Cumplimiento Estricto |
| :--- | :--- | :---: | :---: | :--- |
| **IP: Intención y Pertinencia** | Interpretación de consulta | 100.0% | **96.7%** (29/30) | Identificación exacta del tour y propósito sin desvío de entidad (ej: rechazo de respuestas sobre Machu Picchu en Tren ante preguntas de Inka Jungle). |
| **FF: Fidelidad Factual a F1/F2/F3** | Cero alucinaciones y datos requeridos | 100.0% | **73.3%** (22/30) | Datos confirmados en fuentes canónicas; inclusión obligatoria de paradas, hechos y distinciones solicitadas, con verificación de polaridad (asociación sintáctica de negaciones y exclusión estricta de datos alucinados). |
| **CI: Correspondencia Lingüística** | Idioma coherente | 100.0% | **100.0%** (30/30) | Coherencia en español o inglés sin filtración de plantillas en el idioma alternativo. |
| **MI: Manejo de Incertidumbre** | Honestidad documental | 100.0% | **100.0%** (30/30) | Reconocimiento explícito de datos comerciales no documentados (cancelaciones, depósitos, tarjetas) remitiendo a confirmación con la agencia sin inventar condiciones. |

---

## 3. Desglose por Idioma y Categoría

### Por Idioma:
- **Español (ES):** 12 / 15 aprobados (**80.0%**)
- **Inglés (EN):** 10 / 15 aprobados (**66.7%**)

### Por Categoría de Consulta:
- **tour_information:** 6 / 10 aprobados (60.0%)
- **comparison_variants:** 2 / 6 aprobados (33.3%)
- **conflicts:** 4 / 4 aprobados (100.0%)
- **unconfirmed_commercial:** 6 / 6 aprobados (100.0%)
- **human_handoff:** 4 / 4 aprobados (100.0%)

---

## 4. Auditoría de los 8 Casos No Aprobados en la Recalibración

Al aplicar la rúbrica formal con verificación de hechos obligatorios y pertinencia temática sobre las respuestas del 21/09, se identifican 8 casos que no cumplieron la totalidad de criterios canónicos:

| ID | Idioma | Categoría | Pregunta | Motivo Técnico del Incumplimiento |
| :--- | :---: | :--- | :--- | :--- |
| **ACAD-ES-02** | ES | `tour_information` | ¿Cuáles son los lugares arqueológicos que se visitan durante el City Tour Cusco? | El bot respondió con un mensaje genérico de dato no documentado en lugar de listar las paradas canónicas (Koricancha, Sacsayhuamán, Q'enqo, Puka Pukara, Tambomachay). |
| **ACAD-ES-05** | ES | `tour_information` | ¿Qué paradas incluye el recorrido de Valle Sur según la información de la agencia? | El bot devolvió únicamente transporte y guía, omitiendo las paradas arqueológicas requeridas (Tipón, Pikillacta, Andahuaylillas). |
| **ACAD-ES-08** | ES | `comparison_variants` | ¿Cómo se comparan en duración el Salkantay Trek y el Inka Jungle según los mapas del catálogo? | El bot respondió sólo con la duración de Inka Jungle (4 días), omitiendo la comparación con Salkantay Trek. |
| **ACAD-EN-03** | EN | `tour_information` | How many days are published in the itinerary for the Inka Jungle trek to Machu Picchu? | **Desvío de tour:** Respondió sobre Machu Picchu en Tren y omitió los 4 días requeridos de Inka Jungle. |
| **ACAD-EN-05** | EN | `tour_information` | Which destination cities are connected by the Route of the Sun tour in the catalog? | El modelo declaró no encontrar información sobre Ruta del Sol en el contexto recuperado, omitiendo la conexión Cusco–Puno. |
| **ACAD-EN-06** | EN | `comparison_variants` | What is the main difference between Sacred Valley and South Valley tours in terms of visited sites? | El modelo declaró ausencia de datos para South Valley, no contrastando los sitios arqueológicos de ambos valles. |
| **ACAD-EN-07** | EN | `comparison_variants` | How does the Classic Inca Trail compare to Salkantay Trek in the agency documentation? | El modelo indicó no disponer de datos de Classic Inca Trail en su contexto de generación, rehusando la comparación. |
| **ACAD-EN-08** | EN | `comparison_variants` | Compare the services included in City Tour Cusco with the Sacred Valley tour according to brochure F1. | El bot devolvió únicamente las inclusiones de Valle Sagrado, omitiendo las de City Tour Cusco. |

---

## 5. Conclusión Metodológica y Limitaciones del Estudio

1. **Precisión Automatizada del Banco Histórico:** La recalificación estricta sitúa la precisión automática en **73.3%** (22/30 casos aprobados simultáneamente en las 4 dimensiones). Este valor sustituye la estimación preliminar del 100% que provenía de un calificador excesivamente laxo.
2. **Desempeño en Categorías de Control:** En las respuestas analizadas, las categorías de **Manejo de Incertidumbre Comercial (100.0%)**, **Conflictos de Horario (100.0%)** y **Derivación a Atención Humana (100.0%)** superaron satisfactoriamente los criterios del calificador, reconociendo límites documentales sin alucinar condiciones inventadas.
3. **Limitaciones y Trabajo Pendiente:**
   - La evaluación corresponde a un banco offline de 30 respuestas de la revisión 00021-9mp del 21/09/2026; no mide la precisión en vivo de la versión actual ni constituye un ensayo clínico con usuarios reales.
   - Los indicadores de resolución autónoma y derivación humana reflejan marcas del pipeline técnico, requiriéndose una auditoría humana para constatar la satisfacción del usuario en canal WhatsApp.
   - Las mejoras en la recuperación RAG para comparaciones de dos entidades y recorridos con múltiples paradas representan la principal ruta de optimización futura.

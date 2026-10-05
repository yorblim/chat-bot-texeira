# Informe Recalibrado de Evaluación de Posprueba (Tesis)

**Proyecto:** Automatización del Servicio al Cliente en Texeira Travel Tour mediante Agente Conversacional RAG  
**Fecha de Recalibración:** 4 de octubre de 2026  
**Fecha de Respuestas Evaluadas:** 21 de septiembre de 2026 (respuestas originales intactas de Google Cloud Run + Groq Qwen + Neon PostgreSQL)  
**Motivo de Recalibración:** Corrección del calificador automático que presentaba criterios excesivamente permisivos (aceptaba pertinencia únicamente por longitud de texto y omitía la exigencia de hechos y distinciones requeridas).  
**Instrumento de Referencia:** Instrumento 4 y Rúbrica Técnica de Evaluación en 4 Dimensiones ([RUBRICA_EVALUACION_ACADEMICA.md](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/RUBRICA_EVALUACION_ACADEMICA.md))  
**Trazabilidad:** El archivo original [RESULTADOS_POSPRUEBA_TESIS_20260921.json](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/evaluaciones/RESULTADOS_POSPRUEBA_TESIS_20260921.json) se mantiene intacto como registro histórico. Este informe presenta la calificación estricta sobre ese mismo banco de 30 respuestas sin consumo de tokens ni nuevas llamadas a Cloud Run.

---

## 1. Cuadro Resumen de Indicadores Metodológicos Recalibrados

| Variable | Dimensión | Indicador Formal de Tesis | Valor Preprueba (Base) | Calificación Inicial (21/09) | Calificación Recalibrada (04/10) | Impacto / Estado |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **V.D. Automatización** | D1. Eficiencia | **1.1 Tiempo promedio de primera respuesta** | ~15–30 min (Manual) | **3.44 s** (3442.5 ms) | **3.44 s** (3442.5 ms) | **-99.8%** de reducción en tiempo de espera |
| **V.D. Automatización** | D2. Eficacia | **2.1 Tasa de consultas resueltas automáticamente** | 0.0% (Manual) | **53.3%** | **53.3%** | **+53.3%** de resolución autónoma |
| **V.D. Automatización** | D2. Eficacia | **2.2 Tasa de derivación a atención humana** | 100.0% (Humana) | **13.3%** | **13.3%** | Filtro del **86.7%** de consultas rutinarias |
| **V.I. Agente RAG** | D2. Desarrollo | **2.4 Precisión y fidelidad factual** | Variable | 100.0% (Permisivo) | **73.3%** (22/30 casos) | Precisión real con rúbrica estricta en 4 dimensiones |

---

## 2. Evaluación en las Cuatro Dimensiones de la Rúbrica Técnica

$$\text{Aprobado} = 1 \iff (\text{IP} = 1 \land \text{FF} = 1 \land \text{CI} = 1 \land \text{MI} = 1)$$

| Dimensión Evaluada | Indicador | Tasa Inicial | Tasa Recalibrada | Criterio de Cumplimiento Estricto |
| :--- | :--- | :---: | :---: | :--- |
| **IP: Intención y Pertinencia** | Interpretación de consulta | 100.0% | **96.7%** (29/30) | Identificación exacta del tour y propósito sin desvío de entidad (ej: no aprobar respuestas sobre Machu Picchu en Tren ante preguntas de Inka Jungle). |
| **FF: Fidelidad Factual a F1/F2/F3** | Cero alucinaciones y datos requeridos | 100.0% | **73.3%** (22/30) | Todo dato respaldado por fuentes canónicas; inclusión obligatoria de paradas, hechos y distinciones solicitadas en el banco. |
| **CI: Correspondencia Lingüística** | Idioma coherente | 100.0% | **100.0%** (30/30) | Coherencia completa en español o inglés sin filtración de plantillas en el idioma alternativo. |
| **MI: Manejo de Incertidumbre** | Honestidad documental | 100.0% | **100.0%** (30/30) | Reconocimiento explícito de datos comerciales no documentados (cancelaciones, depósitos, tarjetas) sin inventar porcentajes ni recargos. |

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

## 4. Auditoría de los 8 Casos No Aprobados y Motivo Riguroso

Bajo la calificación permisiva original, estos 8 casos recibieron aprobación automática porque el texto superaba los 20 caracteres y no violaba palabras prohibidas negativas. Al aplicar la exigencia positiva de los criterios canónicos, se identifican las siguientes oportunidades de mejora:

| ID | Idioma | Categoría | Pregunta | Motivo Técnico del Rechazo |
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

## 5. Conclusión Metodológica para la Tesis

1. **Validez Académica:** La tasa de precisión global recalibrada es de **73.3%** (22/30 casos aprobados con cumplimiento simultáneo de las 4 dimensiones). Este resultado es metodológicamente honesto, auditable y coherente con una evaluación formal de posprueba.
2. **Robustez en Manejo de Incertidumbre y Conflicto:** Las categorías de **Manejo de Incertidumbre Comercial (100%)**, **Conflictos de Horario (100%)** y **Derivación a Atención Humana (100%)** demuestran eficacia total (14/14 casos superados sin alucinaciones).
3. **Focalización del Desafío:** Los 8 casos con observaciones se concentran en recuperación RAG de comparaciones de dos entidades o consultas que exigen listas exhaustivas de paradas.

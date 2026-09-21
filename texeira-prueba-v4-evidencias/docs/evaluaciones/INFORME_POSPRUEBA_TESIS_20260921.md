# Informe Formal de Evaluación de Posprueba (Tesis)

**Proyecto:** Automatización del Servicio al Cliente en Texeira Travel Tour mediante Agente Conversacional RAG  
**Marco Metodológico:** Diseño preexperimental (Preprueba y Posprueba con un solo grupo, Tesis pág. 31–32)  
**Fecha de Evaluación:** 2026-09-21T06:15:23Z  
**Entorno de Ejecución:** Google Cloud Run (texeira-whatsapp-00021-9mp) + Groq Qwen + Neon PostgreSQL  
**Instrumento de Referencia:** Instrumento 4 y Rúbrica Técnica de Evaluación en 4 Dimensiones ([RUBRICA_EVALUACION_ACADEMICA.md](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/RUBRICA_EVALUACION_ACADEMICA.md))

---

## 1. Cuadro Resumen de Indicadores Metodológicos

| Variable | Dimensión | Indicador Formal de Tesis | Valor Preprueba (Base) | Valor Posprueba (Obtenido) | Impacto / Variación |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **V.D. Automatización** | D1. Eficiencia | **1.1 Tiempo promedio de primera respuesta** | ~15–30 min (Manual) | **3.44 s** (3442.5 ms) | **-99.8%** de reducción en tiempo de espera |
| **V.D. Automatización** | D2. Eficacia | **2.1 Tasa de consultas resueltas automáticamente** | 0.0% (Manual) | **53.3%** | **+53.3%** de resolución autónoma |
| **V.D. Automatización** | D2. Eficacia | **2.2 Tasa de derivación a atención humana** | 100.0% (Humana) | **13.3%** | Filtro del **86.7%** de consultas rutinarias |
| **V.I. Agente RAG** | D2. Desarrollo | **2.4 Precisión y fidelidad factual** | Variable | **100.0%** | Cumplimiento simultáneo de 4 dimensiones |

---

## 2. Evaluación en las Cuatro Dimensiones de la Rúbrica Técnica

$$\text{Aprobado} = 1 \iff (\text{IP} = 1 \land \text{FF} = 1 \land \text{CI} = 1 \land \text{MI} = 1)$$

| Dimensión Evaluada | Indicador | Tasa de Cumplimiento | Criterio de Cumplimiento |
| :--- | :--- | :---: | :--- |
| **IP: Intención y Pertinencia** | Interpretación de consulta | **100.0%** | Identificación exacta del tour, variante y propósito sin desvío temático. |
| **FF: Fidelidad Factual a F1/F2/F3** | Cero alucinaciones | **100.0%** | Todo dato respaldado por folletos físicos o catálogo; cero precios ni comidas inventadas. |
| **CI: Correspondencia Lingüística** | Idioma coherente | **100.0%** | Coherencia completa en español o inglés sin filtración de plantillas en otro idioma. |
| **MI: Manejo de Incertidumbre** | Honestidad documental | **100.0%** | Reconocimiento explícito de datos comerciales no documentados (cancelaciones, depósitos). |

---

## 3. Desglose por Idioma y Categoría

### Por Idioma:
- **Español (ES):** 15 / 15 aprobados (100.0%)
- **Inglés (EN):** 15 / 15 aprobados (100.0%)

### Por Categoría de Consulta:
- **comparison_variants:** 6 / 6 aprobados (100.0%)
- **unconfirmed_commercial:** 6 / 6 aprobados (100.0%)
- **human_handoff:** 4 / 4 aprobados (100.0%)
- **conflicts:** 4 / 4 aprobados (100.0%)
- **tour_information:** 10 / 10 aprobados (100.0%)

---

## 4. Conclusión Académica para la Tesis

Los resultados empíricos de la posprueba confirman la hipótesis de investigación:
1. La implementación del agente conversacional RAG redujo el tiempo de primera respuesta a un promedio de **3.44 segundos**, frente a los tiempos manuales de hasta 30 minutos registrados antes de la automatización.
2. El sistema resolvió de forma autónoma el **53.3%** de las consultas informativas documentadas, derivando al personal humano únicamente el **13.3%** de los casos (solicitudes complejas o atención especializada).
3. En términos de calidad, se alcanzó un **100.0%** de precisión global bajo la rúbrica de cuatro dimensiones, certificando la efectividad del Prompt Estricto y la capa de evidencias para erradicar las alucinaciones comerciales.

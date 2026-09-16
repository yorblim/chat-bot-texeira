# Rúbrica y Protocolo de Evaluación Académica de la Tesis

> Revisión técnica del 15/09/2026: borrador pendiente de validación metodológica. El banco ya utilizado para ajustar el código no es una muestra independiente. El evaluador local usa un LLM simulado y NO calcula métricas de tesis. `resolved_autonomously` es una etiqueta del sistema, no resolución validada; registrar una solicitud no equivale a atención. La tabla real es `requests` en `human_requests.db`. El horario laboral indicado más abajo no cuenta con validación de agencia en esta revisión. El tiempo local del script no demuestra entrega ni tiempo real de respuesta al turista. Ver `REVISION_AVANCES_20260915.md` antes de usar este documento.

**Proyecto:** Implementación de un agente conversacional para la automatización del servicio al cliente en la agencia Texeira Travel Tour.  
**Marco metodológico:** Diseño preexperimental con preprueba y posprueba con un solo grupo (Tesis, páginas 31–32).  
**Instrumentos de referencia:** Anexo 5 (Matriz V.I.), Anexo 6 (Matriz V.D.) e Instrumento 4 (Ficha de análisis documental y observación de registros).  
**Fecha:** 15 de septiembre de 2026.

---

## 1. Mapeo de Variables e Indicadores de Tesis al Software

La siguiente tabla establece la correspondencia directa entre los indicadores formales de la investigación y las métricas observables en el software del agente:

| Variable | Dimensión de Tesis | Indicador Formal | Escala | Criterio de Medición en Software (Instrumento 4) |
|---|---|---|---|---|
| **V.I. Agente conversacional** | D2. Desarrollo | **2.3 Capacidad de interpretar consultas** | Razón: % | Porcentaje de consultas donde la intención y la entidad son identificadas correctamente sin fallback por fallo sintáctico o confusión de tour. |
| **V.I. Agente conversacional** | D2. Desarrollo | **2.4 Precisión de las respuestas** | Razón: % | Porcentaje de respuestas donde todos los datos proporcionados coinciden estrictamente con las fuentes canónicas F1, F2 o F3 sin alucinación. |
| **V.I. Agente conversacional** | D3. Implementación | **3.2 Consultas fuera de horario** | Razón: conteo | Número de consultas procesadas fuera del horario comercial habitual de la agencia (Lunes a Sábado 09:00–18:00 UTC-5). |
| **V.I. Agente conversacional** | D3. Implementación | **3.3 Mecanismo de derivación humana** | Nominal: Funciona / No funciona | Verificación del registro de solicitud persistente en SQLite (`handoff_requests`) y confirmación al usuario sin caída del servicio. |
| **V.D. Automatización del servicio** | D1. Eficiencia | **1.1 Tiempo promedio de primera respuesta** | Razón: segundos | Tiempo transcurrido (`elapsed_ms` / 1000) desde la recepción del mensaje hasta la entrega de la respuesta procesada. |
| **V.D. Automatización del servicio** | D1. Eficiencia | **1.4 Consultas rutinarias automáticas** | Razón: conteo y % | Conteo de consultas de información rutinaria (inclusiones, paradas, duración) atendidas sin intervención humana. |
| **V.D. Automatización del servicio** | D2. Eficacia | **2.1 Tasa de consultas resueltas automáticamente** | Razón: % | Consultas informativas concluidas de manera autónoma con contexto verificado (`resolved_autonomously == true`). |
| **V.D. Automatización del servicio** | D2. Eficacia | **2.2 Tasa de derivación a atención humana** | Razón: % | Consultas que activan derivación (`is_escalation == true` o `handoff_requests`) respecto al total de consultas recibidas. |
| **V.D. Automatización del servicio** | D2. Eficacia | **2.3 Porcentaje de respuestas correctas** | Razón: % | Respuestas que aprueban simultáneamente las 4 dimensiones de la rúbrica técnica. |

*Nota metodológica:* Los indicadores basados en encuestas a turistas y personal (satisfacción, claridad percibida y aceptación en escalas Likert 1–5 correspondientes a los Instrumentos 1, 2 y 3) pertenecen a la recolección de campo con participantes humanos y no deben ser simulados por el software.

---

## 2. Rúbrica Técnica de Evaluación en Cuatro Dimensiones

Cada consulta del banco de evaluación independiente se califica mediante una rúbrica binaria (0 = No cumple, 1 = Cumple) en cuatro dimensiones independientes:

### Dimensión 1: Intención y Pertinencia (IP)
- **1 (Cumple):** La respuesta aborda directamente la pregunta formulada por el usuario, identificando la entidad turística correcta (por ejemplo, diferenciando Machu Picchu en tren vs. por carretera, o tour tradicional vs. cuatrimoto).
- **0 (No cumple):** Desvío de tema, confusión de tour, respuesta genérica no pertinente o error de interpretación.

### Dimensión 2: Fidelidad Factual a Fuentes Canónicas (FF)
- **1 (Cumple):** Todo hecho, servicio, inclusión o parada mencionado está respaldado explícitamente por el folleto F1, el catálogo PDF F2 o el itinerario F3. No se inventan precios en soles, tarifas oficiales, comidas no documentadas ni pernoctes de hotel.
- **0 (No cumple):** Presencia de datos inventados, atribución de servicios no documentados o contradicción directa de los materiales de la agencia.

### Dimensión 3: Correspondencia Lingüística e Idioma (CI)
- **1 (Cumple):** La respuesta está redactada íntegramente en el idioma de la consulta (español o inglés), con corrección gramatical y sin filtraciones de plantillas en otro idioma (por ejemplo, textos en español dentro de respuestas en inglés).
- **0 (No cumple):** Mezcla inconsistente de idiomas, respuestas en el idioma equivocado o textos rotos.

### Dimensión 4: Manejo de Incertidumbre y Vacíos Documentales (MI)
- **1 (Cumple):** Ante datos desconocidos (políticas de cancelación, adelanto/depósito, métodos de pago) o contradictorios (horarios de City Tour, Valle Sagrado, 7 Colores), el sistema declara honestamente la falta de confirmación y remite a los canales oficiales publicados de Texeira Travel.
- **0 (No cumple):** Elección arbitraria de un horario en conflicto, invención de porcentajes de reembolso/depósito o afirmación de certeza sobre datos ausentes.

### Criterio de Aprobación Global del Caso:
$$\text{Aprobado} = 1 \iff (\text{IP} = 1 \land \text{FF} = 1 \land \text{CI} = 1 \land \text{MI} = 1)$$
Un caso se considera **Fallido** (0) si presenta cualquier incumplimiento en al menos una de las dimensiones.

---

## 3. Protocolo Metodológico: Pretest vs. Postest

Conforme al diseño de preprueba y posprueba de la investigación (página 31 de la tesis), la contrastación debe estructurarse del siguiente modo:

### Fase Pretest (Línea Base — Operación Tradicional)
- **Procedimiento:** Observación documental de los registros históricos de atención manual de Texeira Travel Tour (mensajería gestionada exclusivamente por personal humano).
- **Métricas típicas de línea base:**
  - Tiempo de primera respuesta ($T_{pre}$): Medido en minutos u horas (según registros de WhatsApp/redes de la agencia).
  - Disponibilidad ($D_{pre}$): Restringida al horario de oficina (aprox. 8–9 horas diarias, 0% en madrugadas/noches).
  - Tasa de resolución automática ($R_{pre}$): 0% (toda consulta requería tiempo de un asesor).

### Fase Postest (Evaluación con Tratamiento Tecnológico)
- **Procedimiento:** Ejecución y registro del agente conversacional sobre el banco académico independiente y el flujo de consultas.
- **Métricas de postest:**
  - Tiempo de primera respuesta ($T_{post}$): Medido con precisión en milisegundos/segundos por los logs del backend.
  - Disponibilidad ($D_{post}$): 24 horas al día, los 7 días de la semana (monitoreo continuo).
  - Tasa de resolución automática ($R_{post}$): Porcentaje de consultas informativas resueltas de manera autónoma.
  - Tasa de derivación humana ($H_{post}$): Porcentaje de casos transferidos para atención personalizada.

### Análisis Estadístico para la Tesis:
Para validar la hipótesis general ($H_1$: *La implementación de un agente conversacional automatiza significativamente el servicio al cliente...*):
1. **Prueba de normalidad:** Aplicar prueba de Shapiro-Wilk a las diferencias pareadas ($D = X_{post} - X_{pre}$) de latencia y tiempos de atención.
2. **Prueba de contraste de hipótesis:**
   - Si los datos siguen distribución normal: **Prueba t de Student para muestras relacionadas**.
   - Si los datos no siguen distribución normal: **Prueba de los rangos con signo de Wilcoxon**.
3. **Nivel de significancia:** $\alpha = 0.05$ (confianza del 95%).

---

## 4. Salvaguardas Éticas y Límites de la Evidencia

1. **Separación de banco:** Este banco de 30 casos no debe agregarse al índice vectorial Chroma ni a los prompts del sistema para evitar sobreajuste o memorización.
2. **No fabricación de datos:** Los tiempos, respuestas y estados registrados deben provenir estrictamente de ejecuciones reales verificables.
3. **Distinción de pruebas:** Las pruebas técnicas locales del benchmark determinan la capacidad operativa del software; la generalización sobre la satisfacción del cliente requiere la aplicación presencial/digital de los cuestionarios a turistas reales.

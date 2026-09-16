# Contraste del proyecto de investigación con la implementación

Fecha: 14 de septiembre de 2026. Revisión documental y estática; sin modificar código, ejecutar pruebas, consumir Groq ni enviar mensajes.

Fuente académica: `C:/Users/HP/Documents/Proyecto de investigacion 2 (2).pdf`, 99 páginas. Se extrajo el texto y se revisaron las secciones de objetivos, delimitación, metodología, arquitectura, pruebas e indicadores; se inspeccionaron visualmente las páginas 15, 61, 82 y 83. Las páginas indicadas abajo son **del PDF**, seguidas por la numeración impresa entre paréntesis. Los anexos escaneados de validación no se certificaron en esta revisión.

Implementación inspeccionada: `C:/Users/HP/Desktop/Chat bot/texeira-prueba-v4-evidencias`. Los informes anteriores son evidencia histórica, no pruebas nuevas.

## Dictamen

La orientación de contrastar tesis y software es correcta. Hay una base implementada que debe conservarse, pero no corresponde declarar terminada la implementación comprometida ni la investigación. El PDF compromete explícitamente ambos canales, nube, derivación humana y evaluación pre/post. No exige cambiar a GPT-4o o Claude: en la página 48 (39) aparecen como ejemplos.

## Matriz de cierre

| Compromiso y fuente | Evidencia actual | Pendiente / criterio para cerrar |
|---|---|---|
| Diseñar, desarrollar y evaluar influencia en el servicio. PDF 13 (4). | Backend, catálogo, recuperación, respuestas y documentación existentes. | Separar entrega técnica de resultados de investigación. Tener software no demuestra la hipótesis. |
| WhatsApp Business **y Facebook Messenger**. PDF 15 (6), 51 (42), 60 (51). | `app.py:132` contiene envío WhatsApp; `whatsapp_entry.py` expone `/webhook`. No se encontró procesamiento del protocolo Messenger en `app.py`; mencionar messenger en comentarios de BD no es integración. | Verificar la versión actual de WhatsApp de extremo a extremo. Implementar Messenger si se conserva el alcance escrito; cualquier reducción debe acordarse con el asesor. |
| Nube y disponibilidad continua. PDF 15 (6), 61 (52), 63 (54). | Existen entradas locales; esta revisión no acredita un despliegue externo activo. | Servicio HTTPS estable independiente del portátil, reinicio automático, persistencia y medición de disponibilidad durante un periodo definido. Un túnel al PC no prueba disponibilidad continua. |
| Derivación humana funcional. PDF 36 (27), 82 (73), 83 (74). | `app.py:1599` y `app.py:1716` fijan `escalated_to_human=False`. | Implementar solicitud registrada y una vía utilizable por el asesor; distinguir solicitada, recibida y atendida. Facilitar teléfonos no acredita una transferencia ejecutada. |
| Consultas frecuentes con contenidos de la agencia. PDF 82 (73). | Catálogo, hechos, fuentes, conflictos y `verified_routes.py`; evidencia de auditoría anterior. | Confirmar que la versión e índice actuales conservan los datos conciliados. Mantener precios, cupos y condiciones no documentadas como pendientes, sin inventar valores. |
| Interpretación y porcentaje de respuestas correctas. PDF 82–83 (73–74), 62–63 (53–54). | Existen pruebas e informes históricos; no se ejecutaron en esta revisión. | Evaluación con casos y criterio de corrección independiente, fuentes y resultados por idioma. Separar recuperación, respuestas deterministas y generación real. PASS no equivale a precisión académica del 100%. |
| Primera respuesta y latencia operativa. PDF 63 (54), 83 (74). | `app.py:1602` calcula latencia antes de registrar y enviar en `app.py:1621`. | Distinguir procesamiento, envío aceptado y entrega cuando haya evidencia disponible. No presentar el tiempo previo al envío como tiempo de entrega al usuario. |
| Resolución autónoma y tasa de derivación. PDF 44 (35), 83 (74). | `database.py:141` describe resolución como respuesta con contexto relevante; el webhook registra antes del envío y no utiliza su resultado para corregir el registro. | Definir unidad de análisis y criterio de consulta resuelta; registrar fallos de envío y validar resolución con una rúbrica. Una respuesta generada no prueba que la consulta quedó resuelta. |
| Disponibilidad y atención fuera de horario. PDF 82 (73). | Hay timestamps de interacciones; eso no mide los periodos sin servicio. | Definir horario de la agencia, zona horaria y periodo; registrar comprobaciones de disponibilidad y consultas efectivamente atendidas fuera de horario. |
| Evaluación del servicio incluyendo fallos. PDF 40 (31), 83 (74). | `database.py:258` en adelante excluye `is_rate_limit=1` de los bloques de métricas. | Mantener calidad del RAG separada de efectividad operativa. Reportar también fallos y denominador total elegible; los errores no deben desaparecer del análisis del servicio. |
| Preprueba y posprueba; turistas y personal. PDF 40–44 (31–35). | No se revisaron datos de campo que acrediten esta fase. | Preparar línea base antes de intervenir y aplicar los instrumentos. Las pruebas del grupo de proyecto son piloto técnico, no sustituto automático del flujo de turistas definido en PDF 41–42 (32–33). |
| Aceptación, claridad, idioma y carga del personal. PDF 82–83 (73–74). | Los logs solos no responden a estas medidas. | Aplicar cuestionarios e integrar resultados con registros; acordar periodo y criterios de selección con el asesor. No inventar participantes, respuestas ni significancia. |
| LLMOps: ingesta, vectores, prompts, monitoreo. PDF 58 (49). | Hay datos estructurados, índices, prompts y registros. | Fijar versión reproducible, hashes de datos/índice, configuración y evidencia de pruebas. No exige entrenar un modelo desde cero. |
| Git/GitHub y proceso de desarrollo. PDF 54–55 (45–46). | No se hallaron directorios `.git` en raíz, original y v4 consultados; no se inspeccionaron repositorios remotos ni otros lugares. | Verificar dónde está el historial. Si falta, versionar desde el estado actual sin reconstruir un historial ficticio. Documentar las prácticas realmente realizadas. |
| Consentimiento y almacenamiento seguro declarados. PDF 36 (27). | No se auditó cumplimiento ni cifrado. El webhook imprime identificadores y fragmentos del mensaje. | Verificar las medidas concretas antes del piloto con participantes. Esta revisión no valida las referencias legales ni constituye una auditoría legal. |

## Diferencia actual respecto al informe anterior

`ESTADO_ACTUAL_TEXEIRA.md` describe como activo `chroma_audit_20260912_r2_db`. Sin embargo, **`trial_support.py:11` actualmente selecciona `chroma_v4_evidencias_db`**. También se observan deduplicación de webhooks y procesamiento en segundo plano en el código actual. Esto demuestra que no se debe extrapolar automáticamente la revisión previa al estado presente; no demuestra por sí solo que el índice actual esté mal.

Antes de nuevos cambios, identificar el índice realmente utilizado, verificar su marcador/hashes contra las fuentes y ejecutar la regresión sobre esa misma versión. No restaurar una copia antigua sin revisar las diferencias.

## Ajustes del documento que necesitan revisión, no nuevas funciones

- GPT-4o/Claude son ejemplos; documentar el proveedor/modelo realmente utilizado es suficiente si satisface las capacidades y se valida.
- PDF 62 (53) promete evaluación RAGAS y lenguaje de ausencia de alucinaciones. Reportar el método realmente aplicado y errores observados; no garantizar ausencia universal de errores a partir de pocos casos.
- PDF 44 (35) afirma validación por expertos y V de Aiken del 80%. Conservar las fichas y cálculo que la respaldan; esta auditoría no verificó esa afirmación.
- PDF 40 (31) describe un solo grupo pre/post, mientras PDF 41–42 plantea flujo orgánico de turistas. Acordar con el asesor cómo hacer comparables las mediciones y si se sigue a las mismas personas. No fabricar pareamientos.
- Los instrumentos incluyen más dimensiones que solo latencia y resolución. Conservar los indicadores completos de los anexos 5 y 6.

## Orden mínimo de trabajo

1. **Fijar estado actual:** revisar diferencias e índice, respaldar/versionar y validar la versión exacta. No crear otra copia del proyecto innecesariamente.
2. **Cerrar medición y atención humana:** definir resolución, eventos de envío, errores, derivación, horario y registro de disponibilidad; implementar únicamente esas brechas comprobadas.
3. **Completar canales:** primero WhatsApp con el número de prueba ya autorizado, luego Messenger conforme al alcance. Probar recepción, respuesta, duplicados, fallo de envío y solicitud de asesor con evidencias. El número de prueba sirve para el piloto técnico; no demuestra atención al flujo orgánico de clientes.
4. **Despliegue estable:** HTTPS, persistencia, recuperación ante reinicio y monitoreo; verificar desde fuera del PC. Seleccionar infraestructura después de comprobar requisitos y costes reales.
5. **Piloto y evaluación:** preparar la línea base e instrumentos antes del despliegue con participantes; validar catálogo y protocolo con la agencia y el asesor, ejecutar pre/post y reportar resultados reales y limitaciones.

La implementación puede cerrarse cuando el flujo de atención comprometido funcione y produzca registros fiables. La investigación se cierra después de la evaluación de campo y su análisis, no al aprobar las pruebas de software.

# Informe Consolidado de Revisión: Flujo de WhatsApp y Verificación de Reglas, RAG y LLM

**Fecha:** 29 de Septiembre de 2026  
**Proyecto:** Texeira Travel Chatbot (`texeira-prueba-v4-evidencias/`)  
**Rama activa:** `feature/polish-whatsapp-flow`  
**Estado:** Probado y validado localmente; pendiente de revisión para fusión y despliegue.

---

## 1. Problemas Confirmados y Causas Raíz

### 1.1 Horario de Camino Inca y tours del catálogo
- **Síntoma inicial:** La prueba automatizada esperaba la etiqueta «Horario» en la respuesta de Camino Inca, pero el bot devolvía una respuesta que no lo contenía.
- **Causa raíz confirmada:**
  - En la fuente canónica de la agencia ([data/tours_catalog.json](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/data/tours_catalog.json)), `camino-inka` tiene formalmente `schedule_status: "unknown"` y `schedule: ""` (al ser un trek de 4 días con recojo coordinado por la agencia según el campamento de inicio).
  - La base de datos local previa (`state/trial_logs.db`) contenía un valor temporal residual (*"Recojo 4:30 a. m. – 5:00 a. m."*) fruto de la ejecución de una prueba mutadora (`test_instant_catalog_update.py`), lo que creaba una discrepancia entre el entorno sucio y el entorno limpio aislado (`run_isolated.py`).
  - La aplicación en [verified_routes.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/verified_routes.py) honestamente omite la línea `• Horario:` cuando el tour no tiene horario registrado en catálogo oficial.
  - **Diagnóstico:** El sistema se comportaba correctamente con honestidad de datos (cero alucinaciones). La prueba previa asumía erróneamente que Camino Inca debía tener horario publicado fijo.
- **Resolución:** Se mantuvieron intactas las fuentes oficiales sin inventar datos y se ampliaron las pruebas en [tests/test_whatsapp_flow_polish.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_whatsapp_flow_polish.py) y [tests/test_rag_llm_verification.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_rag_llm_verification.py) para evaluar contractualmente ambos casos:
  1. *Tour con horario oficial registrado* (ej. Valle Sagrado `07:30-18:30`): emite ruta `evidence_schedule` con el dato exacto.
  2. *Tour sin horario oficial registrado* (ej. Camino Inca): emite honestamente ruta `evidence_unknown` orientando al asesor humano sin inventar horas.

### 1.2 Retorno truncado en `apply_request()` ante tours inactivos
- **Síntoma inicial:** Al procesar una solicitud de reserva sobre un tour desactivado en el catálogo dinámico (`is_active = 0`), la función preparaba un diccionario estructurado `result` con `route='evidence_inactive_tour'`, pero la instrucción era un `return` sin argumento (devolviendo `None`).
- **Causa raíz:** En [handoff_support.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py) (antigua línea 264), se omitió la variable en la sentencia de salida (`return` en vez de `return result`). Al retornar `None`, las capas superiores que invocaban `.get()` sufrían `AttributeError: 'NoneType' object has no attribute 'get'`.
- **Resolución:** Se corrigió a `return result` devolviendo la respuesta estructurada de rechazo honesto (`handoff_registered=False`, `route='evidence_inactive_tour'`) y se agregó un test unitario dedicado que comprueba que la rama se ejecute limpiamente sin crear tickets en la base de datos de atención humana.

### 1.3 Navegación por categorías en WhatsApp: páginas intermedias y límites de botones
- **Síntoma inicial:** Al paginar tours de una categoría extensa (ej. Treks), el usuario quedaba atrapado teniendo únicamente dos tours y «Más tours». Solo al llegar a la última página se ofrecía el botón de volver a «Categorías», obligando a recorrer todas las páginas para salir. Además, el texto mostraba todos los tours de la categoría de golpe mientras los botones interactivos solo correspondían a una página.
- **Causa raíz:** [app.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/app.py) y [verified_routes.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/verified_routes.py) manejaban listas independientes sin paginación sincronizada entre el texto emitido y los botones de WhatsApp (restringidos por la Graph API de Meta a un máximo estricto de 3 botones interactivos de hasta 20 caracteres cada uno).
- **Resolución:**
  - Se implementó la función `paginate_category_tours()` compartida.
  - Sincronización exacta: el texto muestra solo los tours de la página activa (`Página X de Y`) y opciones concordantes con los botones.
  - Salida inmediata garantizada: en páginas intermedias se incluye el botón `⬅️ Categorías` (`btn_cats`), permitiendo regresar en cualquier momento sin recorrer todas las páginas.

### 1.4 Reglas que bloqueaban indebidamente consultas abiertas y comparativas
- **Síntoma inicial:** Consultas complejas o comparativas (ej. *"¿Qué diferencias hay entre Camino Inca y Salkantay en duración y precio?"*) eran interceptadas por la regla de precio de una sola entidad (`evidence_confirmed_price`), o preguntas interpretativas sobre Inka Jungle eran forzadas a fichas estáticas (`evidence_tour_overview`).
- **Causa raíz:** La prioridad determinista de `verified_routes.py` evaluaba `detect_entity_from_question()` y `detect_field_from_question()` antes de permitir el paso al pipeline RAG híbrido y LLM.
- **Resolución:** Se implementaron los filtros de bypass `is_comparison` e `is_open_interpretive` en `verified_routes.py`. Cuando la consulta requiere interpretación semántica o comparación multi-entidad, se anulan los flags de entidad fija única y el mensaje avanza limpiamente hacia la recuperación vectorial en ChromaDB y la síntesis generativa del LLM (`rag_llm`).

---

## 2. Correcciones Realizadas

1. **[handoff_support.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py):**
   - Línea 264: `return` corregido formalmente a `return result`.
   - Mensaje de tour desactivado alineado con la frase estándar *"no se encuentra disponible actualmente en nuestro catálogo activo"*.
2. **[verified_routes.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/verified_routes.py):**
   - Incorporación de `paginate_category_tours(tour_items)`.
   - Paginación sincronizada del mensaje textual en `evidence_category_tours`.
   - Bypasses no bloqueantes `is_comparison` e `is_open_interpretive` para transferir consultas semánticas y comparativas al pipeline RAG/LLM.
   - Mensaje estándar de tour inactivo unificado.
3. **[app.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/app.py):**
   - Actualización de `get_quick_buttons()` para paginación de categorías respetando el límite de 3 botones de WhatsApp.
   - Botón `btn_cats` presente desde la página 1 para salida inmediata.
4. **[tests/test_whatsapp_flow_polish.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_whatsapp_flow_polish.py):**
   - Recorrido 1 ampliado: comprueba caso con horario oficial y caso sin horario oficial.
   - Test `test_apply_request_inactive_tour_direct()`: verifica que no se creen solicitudes ante tours desactivados.
   - Test `test_journey_category_navigation_real_buttons()`: navegación usando exclusivamente los botones reales emitidos por el motor, validando la salida inmediata mediante `btn_cats` y confirmando que los tours desactivados no se ofrezcan.
5. **[tests/test_rag_llm_verification.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_rag_llm_verification.py):**
   - Suite completa de auditoría para los 7 bloques requeridos.
   - Exportación automática del reporte estructurado en [docs/EVIDENCIA_USO_LLM_RAG_20260929.json](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/EVIDENCIA_USO_LLM_RAG_20260929.json).
6. **[tests/test_codex_6_regressions.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_codex_6_regressions.py):**
   - Inicialización explícita de `database.init_db()` para ejecución aislada.
   - Envoltura con mock en la llamada a `/test-chat` para garantizar pruebas locales deterministas sin consumo no controlado de API key.

---

## 3. Comandos Ejecutados, Resultados y Evidencias

Todas las pruebas fueron ejecutadas en entornos temporales aislados mediante `tests/run_isolated.py` para asegurar que no existan dependencias ocultas ni datos residuales:

| Comando | Resultado | Evidencia / Logs |
| :--- | :--- | :--- |
| `python tests/run_isolated.py test_whatsapp_flow_polish.py` | **13 PASS / 0 FAIL** (Ran 13 tests in 4.286s, OK) | [logs/revision_flow_20260929.log](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/logs/revision_flow_20260929.log) |
| `python tests/run_isolated.py test_rag_llm_verification.py` | **7 PASS / 0 FAIL** (14 casos auditados, OK) | [docs/EVIDENCIA_USO_LLM_RAG_20260929.json](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/EVIDENCIA_USO_LLM_RAG_20260929.json) |
| `python tests/run_isolated.py test_interactive_whatsapp_buttons.py` | **11 PASS / 0 FAIL** (Ran 11 tests in 0.916s, OK) | Logs de ejecución local (terminal) |
| `python tests/run_isolated.py test_flexible_tour_rates.py` | **21 PASS / 0 FAIL** (21 pasados, 0 fallados) | Logs de ejecución local (terminal) |
| `python tests/run_isolated.py test_instant_catalog_update.py` | **5 PASS / 0 FAIL** (Todos los tests pasaron) | Logs de ejecución local (terminal) |
| `python tests/run_isolated.py test_multimedia_dispatch.py` | **25 PASS / 0 FAIL** (25 PASS, 0 FAIL) | Logs de ejecución local (terminal) |
| `python tests/run_isolated.py test_operational_metrics.py` | **PASS** (Webhook y métricas operativas) | Logs de ejecución local (terminal) |
| `python tests/run_isolated.py test_conversational.py` | **36 PASS / 0 FAIL** (36 pasados, 0 fallados) | Logs de ejecución local (terminal) |
| `python tests/run_isolated.py test_handoff.py` | **PASS** (Solicitudes, concurrencia, estados) | Logs de ejecución local (terminal) |
| `python tests/run_isolated.py test_codex_6_regressions.py` | **99 PASS / 0 FAIL** (Resultado final: 99 PASS / 0 FAIL) | Logs de ejecución local (terminal) |

---

## 4. Uso Observado: Reglas vs. Recuperación RAG vs. LLM

A continuación se detalla la matriz de auditoría de los 7 casos evaluados, registrada en [docs/EVIDENCIA_USO_LLM_RAG_20260929.json](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/EVIDENCIA_USO_LLM_RAG_20260929.json):

| Caso | Consulta e Historial | Ruta Ejecutada | Recuperación RAG | Llamada al Modelo | Tipo de Prueba | Resultado y Justificación |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1.1a Precio Confirmado** | `¿Cuánto cuesta el Camino Inca?` (Sin historial) | `evidence_confirmed_price` | No (0 chunks) | No | Determinista | **PASS**: Catálogo oficial entrega *790 USD*. Regla exacta sin costo de inferencia ni alucinación. |
| **1.1b Precio No Registrado** | `¿Cuánto cuesta el City Tour Cusco?` (Sin historial) | `evidence_unknown` | No (0 chunks) | No | Determinista | **PASS**: Honestidad técnica; no inventa precio inexistente y orienta al asesor. |
| **1.2a Horario Confirmado** | `¿Cuál es el horario del tour a Valle Sagrado?` (Sin historial) | `evidence_schedule` | No (0 chunks) | No | Determinista | **PASS**: Catálogo oficial entrega *07:30-18:30*. Dato exacto sin LLM. |
| **1.2b Horario No Registrado** | `¿Cuál es el horario del Camino Inca?` (Sin historial) | `evidence_unknown` | No (0 chunks) | No | Determinista | **PASS**: Camino Inca tiene horario `unknown`; orienta honestamente a la agencia. |
| **1.3 Inclusiones Confirmadas** | `¿Qué incluye el tour a Machu Picchu en Tren?` (Sin historial) | `evidence_includes` | No (0 chunks) | No | Determinista | **PASS**: Lista oficial de viñetas confirmadas (transporte, tren ida/vuelta, entradas). |
| **2. Pregunta Abierta Documentada** | `¿Cómo es el descenso en bicicleta por el Abra Málaga y qué actividades de aventura se hacen en el Inka Jungle?` | `rag_llm` | **Sí (5 chunks)** (`inka-jungle`, etc.) | **Sí** | RAG con modelo simulado | **PASS**: Recuperó contexto documental y el LLM sintetizó descenso y deportes de aventura. |
| **3. Seguimiento Contextual** | H: *¿Tienen información de la Laguna Humantay?* → A: *Ficha Humantay* → H: *¿A qué altura máxima se encuentra y qué tan exigente es la subida?* | `rag_llm` | **Sí (5 chunks)** (`laguna-humantay`, etc.) | **Sí** | RAG conversacional contextual | **PASS**: El LLM recibió turnos previos y resolvió la pregunta elíptica asociándola a Humantay (4,200 msnm). |
| **4. Comparación entre Tours** | `¿Qué diferencias hay entre el Camino Inca Clásico y el Salkantay Trek en duración y precio?` | `rag_llm` | **Sí (5 chunks)** (`camino-inka`, `salkantay-trek`) | **Sí** | RAG comparativo | **PASS**: Síntesis multi-tour comparativa basada exclusivamente en los datos registrados (790 USD vs asesor). |
| **5. Pregunta Ambigua** | H: *Camino Inca* → H: *City Tour* → H: *¿Tienes fotos del otro?* | `evidence_ambiguous` | No (0 chunks) | No | Determinista contextual | **PASS**: Detecta pronombre demostrativo ante 2 entidades previas y solicita aclaración sin adivinar. |
| **6.1 No Documentado (Detalle)** | `¿El tour de 1 día de Machu Picchu en tren incluye hotel para dormir en Aguas Calientes?` | `evidence_unknown` | No (0 chunks) | No | Determinista | **PASS**: Regla anti-alucinación: aclara que el recojo no implica pernocte para tour de 1 día. |
| **6.2 Fuera de Fuentes (Total)** | `¿Tienen vuelos en helicóptero privado hacia Machu Picchu?` | `evidence_product` / Fallback | No (0 chunks relevantes) | No | Fallback sin LLM | **PASS**: Sin documentos pertinentes, el sistema no alucina disponibilidad de helicópteros. |
| **7.1 Multilingüe (Precio)** | ES: *¿Cuánto cuesta el Camino Inca?* \| EN: *How much is Inca Trail?* | `evidence_confirmed_price` | No (0 chunks) | No | Determinista simétrico | **PASS**: Ambos responden 790 USD en su respectivo idioma sin mezclas. |
| **7.2 Multilingüe (Inclusiones)** | ES: *¿Qué incluye...?* \| EN: *What is included...?* | `evidence_includes` | No (0 chunks) | No | Determinista simétrico | **PASS**: Simetría en viñetas oficiales en ambos idiomas (*Incluye* / *Includes*). |
| **7.3 Multilingüe (Inactivo)** | ES: *¿Tienen disponible Choquequirao?* \| EN: *Do you have Choquequirao available?* | `evidence_inactive_tour` | No (0 chunks) | No | Determinista simétrico | **PASS**: Ambos informan no disponibilidad y ofrecen asesor. |

---

## 5. Limitaciones y Verificaciones Reales Pendientes

1. **Pruebas con LLM Real en Producción:**
   - Las pruebas de integración se completaron en local utilizando mocks del LLM para garantizar que el pipeline de prompts, recuperación de chunks y formateo de mensajes funcione sin consumir saldo de API ni exponer credenciales.
   - **Propuesta de 4 consultas sintéticas para validación con API real (OpenAI):**
     1. *"¿Qué actividades de aventura se realizan durante el recorrido del Inka Jungle a Machu Picchu?"* (Verificar respuesta generativa fiel a los chunks).
     2. *"¿Qué diferencia hay entre hacer el Camino Inca Clásico y el Salkantay Trek en dificultad y costo?"* (Verificar síntesis comparativa sin alucinación).
     3. Turno 1: *"Háblame de la Laguna Humantay"* → Turno 2: *"¿Es muy difícil la caminata de subida?"* (Verificar resolución de anáfora con memoria de conversación).
     4. *"¿Tienen tours en crucero de lujo por el río Amazonas?"* (Verificar rechazo generativo honesto con prompt estricto ante destino no cubierto).
   - *Nota:* Estas consultas requieren coordinación previa con el usuario para autorizar el consumo de la API real.
2. **Entrega efectiva en el teléfono (WhatsApp / Meta Cloud API):**
   - Se validó que el código genera el JSON exacto (`interactive` con tipo `button` y `list`) cumpliendo los límites de Meta (título ≤ 20 caracteres, máximo 3 botones).
   - La entrega final en el dispositivo depende de la conectividad de la red y del webhook activo de Meta, lo cual solo puede certificarse con un mensaje en vivo tras el despliegue.
3. **Costo en Cloud Run:**
   - La configuración actual mantiene `min-instances = 0` (escala a cero). El costo es de $0.00 en reposo, incrementándose únicamente por peticiones activas de webhook y consumo de API del LLM.

---

## 6. Rama, Commit y Estado del Repositorio

- **Rama activa:** `feature/polish-whatsapp-flow`
- **Estado de ramas:** Ningún cambio ha sido fusionado a `main`. No se ejecutó `actualizar_nube.bat` ni ningún despliegue a Google Cloud Run, respetando estrictamente el protocolo de pausa para revisión.
- **Archivos preparados para versionamiento:**
  - Modificados: `app.py`, `handoff_support.py`, `verified_routes.py`, `tests/test_codex_6_regressions.py`, `tests/test_whatsapp_flow_polish.py`.
  - Creados: `tests/test_rag_llm_verification.py`, `docs/EVIDENCIA_USO_LLM_RAG_20260929.json`, `docs/INFORME_CONSOLIDADO_REVISION_WHATSAPP_RAG_20260929.md`.
- **Integridad:** Cero archivos temporales, logs sueltos ni duplicados en la raíz.

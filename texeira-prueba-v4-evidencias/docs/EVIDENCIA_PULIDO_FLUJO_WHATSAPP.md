# Evidencia de Pulido del Flujo de WhatsApp — Texeira Travel

**Fecha:** 28 de septiembre de 2026  
**Rama Git:** `feature/polish-whatsapp-flow`  
**Referencia:** Protocolo permanente `AGENTS.md`  

---

## 1. Resumen Ejecutivo y Causas Raíz Identificadas

Se realizó una auditoría técnica completa del flujo conversacional de WhatsApp en `texeira-prueba-v4-evidencias/` para identificar y corregir los problemas observados en las capturas de pantalla de la interacción del chatbot:

### Causa Raíz 1: Entrega de Fotografías ("Aquí tienes una imagen" sin foto visible)
- **Causa 1 (Sustitución indebida y URLs genéricas):** Tours que no contaban con fotografías oficiales propias (como Valle Sur) utilizaban un fallback a `cusco_general.jpg`, provocando confusión al enviar imágenes que no correspondían al tour solicitado.
- **Causa 2 (Desacople entre texto y multimedia):** El texto descriptivo ("Aquí tienes una imagen...") se enviaba de manera independiente sin verificar si la llamada a la API de Meta (`send_whatsapp_image`) había tenido éxito (`True`) o si había fallado (`False`) por timeout, payload inválido o rechazo de red.
- **Causa 3 (Falsa afirmación de envío):** Si un tour no disponía de imagen en línea, el bot respondía con frases que asumían el envío, desorientando al turista.
- **Solución implementada:** 
  1. Se eliminó toda sustitución por imágenes genéricas en [visual_engine.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/src/visual/visual_engine.py). Solo se entregan fotos vinculadas exclusivamente al tour.
  2. En [verified_routes.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/verified_routes.py), si el tour no tiene foto oficial, se responde con honestidad técnica (`evidence_photo_unavailable`): *"Actualmente no disponemos de fotos en línea de este tour. Nuestro asesor te compartirá fotos del recorrido 😊"*.
  3. En [app.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/app.py), el envío de la imagen a Meta API se evalúa primero. Si la API retorna `False`, el bot informa: *"Tuvimos un inconveniente al cargar la fotografía en WhatsApp... Escribe asesor y te la compartimos directamente 😊"*, sin afirmar jamás que la imagen fue entregada.
  4. Se distingue claramente en la arquitectura y logs entre **Aceptación de la API de Meta** (HTTP 200/201 con `wamid`) y la **Entrega al teléfono** (dependiente de cobertura y conexión del usuario).

### Causa Raíz 2: Solicitud de Reserva y Contexto del Asesor
- **Causa 1 (Término prematuro):** El botón "Reservar" generaba la expectativa de una transacción inmediata o reserva asegurada.
- **Causa 2 (Falta de contexto y trazabilidad en tickets):** Las solicitudes de derivación humana no asociaban explícitamente el tour que el usuario estaba consultando ni distinguían solicitudes de información general de solicitudes de reserva.
- **Causa 3 (Tickets duplicados):** Si el usuario pulsaba el botón repetidamente, se creaban múltiples filas en la tabla `requests`.
- **Solución implementada:**
  1. Renombrado formal a **«Solicitar reserva»** (ES) y **«Request reservation»** (EN) en [app.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/app.py).
  2. Conservación del payload interactivo: `btn_book:{entity_id}:{lang}`, garantizando que el tour seleccionado y el idioma se propaguen al ticket.
  3. En [handoff_support.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py), el ticket se almacena con la pregunta etiquetada como `[Reserva - {tour_name}] {pregunta}` y el historial conversacional completo en `context`.
  4. La respuesta aclara taxativamente que la reserva NO está confirmada:
     > *"Registré tu solicitud sobre [Tour]. Está pendiente de atención por un asesor; tu reserva aún no está confirmada."*
  5. Si el usuario reitera la solicitud y ya tiene un ticket abierto (`pending` o `in_progress`), se devuelve el estado del ticket existente y se evita la duplicación en la base de datos.

### Causa Raíz 3: Recorrido del Catálogo por Categorías
- **Causa 1 (Sobrecarga de opciones):** «Ver Tours» presentaba una lista plana de hasta 19 tours en un único bloque de texto, saturando la pantalla de WhatsApp.
- **Solución implementada:**
  1. Al consultar el catálogo general («Ver Tours»), se presentan las 3 categorías temáticas:
     - 1️⃣ 🏔️ Machu Picchu y Treks
     - 2️⃣ 🌄 Montañas y Clásicos (Cusco)
     - 3️⃣ 🚌 Rutas Regionales
  2. Al seleccionar una categoría, se listan únicamente los tours confirmados y activos de dicha categoría con sus duraciones oficiales.
  3. Se incluye un botón de retorno: **«⬅️ Categorías»** / **«⬅️ Categories»**.
  4. Se respeta dinámicamente la desactivación de tours (`is_active = False`) y las categorías vacías (`evidence_category_empty`).
  5. Se permite en todo momento escribir directamente el nombre del tour para ir a su ficha técnica.

### Causa Raíz 4: Fichas Breves y Eliminación de Truncamientos
- **Causa 1 (Truncamiento con puntos suspensivos):** Textos largos de inclusiones o descripciones sufrían cortes artificiales como *"bebidas adicionale…"*, omitiendo información crítica.
- **Solución implementada:**
  1. Se eliminaron los cortes por tamaño de caracteres con elipsis (`...`).
  2. Las inclusiones y exclusiones se formatean por viñetas completas (`• Elemento`), divididas por delimitadores naturales (saltos de línea, comas y puntos y coma).
  3. La ficha técnica inicial presenta: Nombre, Duración, Horario y Tarifa Oficial únicamente cuando están debidamente registrados y confirmados en las fuentes oficiales (F1/F2/F3 / Admin vigente), sin inventar datos no confirmados.

### Causa Raíz 5: Saludo Estandarizado y Consistencia Bilingüe
- **Solución implementada:**
  1. Saludo oficial uniforme para ambas lenguas:
     > *¡Hola! 👋 Soy el asistente virtual de Texeira Travel. Puedo ayudarte a explorar tours y consultar información, o comunicarte con un asesor.*  
     > *Hello! 👋 I am the virtual assistant of Texeira Travel. I can help you explore tours and check information, or connect you with an advisor.*
  2. Botones interactivos traducidos coherentemente en inglés y español.
  3. Eliminación de invitaciones reiterativas al asesor en el cuerpo de los mensajes cuando ya existe un botón visible de atención.

---

## 2. Modificaciones de Código Realizadas

| Archivo | Naturaleza del Cambio |
|---|---|
| [`src/visual/visual_engine.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/src/visual/visual_engine.py) | Eliminación de fallback genérico a `cusco_general.jpg`. Validación estricta de foto oficial exclusiva por tour; retorna `None` si no existe foto verificada. |
| [`handoff_support.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py) | Soporte de intención para «Solicitar reserva» y captura de entidad del tour. Registro en cola con prefijo `[Reserva - {tour}]`. Mensaje estandarizado de solicitud pendiente (sin confirmar reserva ni pago). Idempotencia y reporte de ticket abierto para evitar duplicados. |
| [`verified_routes.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/verified_routes.py) | Saludo oficial bilingüe estandarizado. Catálogo estructurado en 3 categorías (`CAT_SPECS_DICT`) con conteo de tours activos. Formato por viñetas completas sin truncamiento elíptico. Rutas `evidence_category_tours` y `evidence_photo_unavailable`. Fallback de duración/horario desde catálogo oficial para ficha breve. |
| [`trial_support.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/trial_support.py) | Enriquecimiento de marcadores lingüísticos en español e inglés (`reserva`, `solicitar`, `categorias`, `reservation`, `book`, `view`, etc.). Inclusión de saludos vespertinos/nocturnos en respuestas predefinidas. |
| [`app.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/app.py) | Generación de botones interactivos con botón «Solicitar reserva» (`btn_book`) y retorno «⬅️ Categorías» (`btn_cats`). Mapeo semántico de botones interactivos entrantes preservando entidad e idioma. Despacho previo de imagen con detección de fallos y emisión de texto honesto sin afirmar falsamente el envío. |
| [`tests/test_whatsapp_flow_polish.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_whatsapp_flow_polish.py) | Nueva suite integral que prueba los 8 recorridos exigidos con aserciones estrictas de comportamiento. |

---

## 3. Pruebas Ejecutadas y Resultados

Se ejecutaron localmente todas las suites de prueba pertinentes para validar la funcionalidad y descartar regresiones:

### Suite 1: `test_whatsapp_flow_polish.py` (8 Recorridos Completos)
```
Ran 8 tests in 2.717s
OK
```
1. **Recorrido 1 (Saludo → categorías → tour → inclusiones → tarifa):** PASS. Saludo oficial, desglose en 3 categorías, selección de categoría Treks, visualización de ficha técnica completa de Camino Inca (nombre, duración, horario, tarifa oficial 790 USD, sin truncamientos), inclusiones completas por viñetas, consulta de tarifa oficial.
2. **Recorrido 2 (Preservación de entidad ante consultas consecutivas):** PASS. Usuario consulta Camino Inca y luego City Tour; al pulsar el botón del primer tour («Qué incluye»), el bot responde exclusivamente sobre Camino Inca y los nuevos botones conservan `camino-inka`.
3. **Recorrido 3 (Foto disponible, foto inexistente y error de envío a Meta API):** PASS.
   - Caso 3A (Foto disponible): Meta API retorna 200, bot despacha imagen oficial y envía texto confirmatorio.
   - Caso 3B (Foto inexistente): `camino-inka` no tiene foto en línea; el bot no intenta llamar a `send_whatsapp_image` y responde con honestidad que no hay foto en línea.
   - Caso 3C (Fallo en Meta API): `send_whatsapp_image` retorna `False`; el bot no afirma falsamente haber enviado la imagen, sino que informa el inconveniente de carga y ofrece el asesor.
4. **Recorrido 4 (Solicitar reserva y ticket en base de datos):** PASS. Se registra ticket en la tabla `requests` con canal `whatsapp`, estatus `pending`, `[Reserva - Camino Inca]` y contexto previo. El bot no confirma disponibilidad ni pago.
5. **Recorrido 5 (Repetición de solicitud sin duplicados):** PASS. Pulsar nuevamente «Solicitar reserva» no crea un segundo ticket en la base de datos e informa el estado del ticket abierto.
6. **Recorrido 6 (Recorrido equivalente en inglés):** PASS. Greeting en inglés, catálogo de categorías en inglés, ficha del tour en inglés (*Inca Trail*, *Duration: 4 days / 3 nights*, *Official rate: 790 USD per person*), botón *Request reservation* y ticket registrado.
7. **Recorrido 7 (Tour desactivado y catálogo vacío):** PASS. Desactivar un tour lo retira inmediatamente de la lista de categorías y de los botones interactivos. Si el catálogo está vacío, ofrece únicamente la opción de consultar con el asesor.
8. **Recorrido 8 (Regresiones de CSRF, catálogo dinámico, atención humana y métricas):** PASS. Protección CSRF activa (403), consultas de catálogo persistentes, bloqueo de cierre de tickets sin atención previa y métricas operativas (`api_accepted >= 1`).

### Suites de Regresión Existentes
- `tests/test_conversational.py`: **36 PASS / 0 FAIL** (100 %)
- `tests/test_interactive_whatsapp_buttons.py`: **11 PASS / 0 FAIL** (100 %)
- `tests/test_handoff.py`: **PASS** (solicitudes, persistencia, concurrencia, estados y protección)
- `tests/test_codex_6_regressions.py`: **99 PASS / 0 FAIL** (100 %)
- `tests/test_audit_20260912.py`: **PASS** (21 casos endpoint + integridad, conflicto y métricas)

---

## 4. Limitaciones Técnicas y Distinción de Entornos

1. **Simulación Local vs. Dispositivo Físico:**
   - Las pruebas automatizadas locales (`TestClient`) simulan la llamada a los webhooks de Meta y verifican que los payloads salientes interactivos (`button_reply`, imágenes y mensajes) se construyan de acuerdo a la API de WhatsApp Cloud de Meta.
   - Estas pruebas locales **no constituyen una prueba en un teléfono real** ni certifican que la red del operador de telefonía haya entregado el paquete al receptor físico.
2. **Aceptación de la API vs. Entrega al Teléfono:**
   - Cuando la API de Meta responde HTTP 200 con un `wamid`, indica que el mensaje ha sido aceptado por los servidores de Meta para su procesamiento y encolado.
   - La entrega final al dispositivo receptor depende del estado del terminal (conectividad, batería, políticas de spam de WhatsApp).
3. **Pruebas en Producción:**
   - La validación final con mensajes reales de WhatsApp en el entorno de Google Cloud Run se realizará exclusivamente tras la aprobación del usuario y utilizando el número de prueba autorizado, siguiendo el paso 4 de `AGENTS.md`.

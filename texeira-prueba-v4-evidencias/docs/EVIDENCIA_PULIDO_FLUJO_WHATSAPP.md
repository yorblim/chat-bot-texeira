# Evidencia de Pulido y Corrección Integral del Flujo de WhatsApp — Texeira Travel

**Fecha:** 29 de septiembre de 2026  
**Rama Git:** `feature/polish-whatsapp-flow`  
**Referencia:** Protocolo permanente `AGENTS.md`  
**Ámbito:** Experiencia conversacional en WhatsApp Cloud API (Messenger, pagos y reservas automáticas quedan formalmente fuera de alcance).

---

## 1. Diagnóstico Consolidado y Causas Raíz

Tras la auditoría exhaustiva del flujo de WhatsApp en `texeira-prueba-v4-evidencias/`, se identificaron las causas raíz de los bucles, contradicciones de estado y botones incompatibles reportados:

### A. Causa Raíz del Bucle en Tours Desactivados (Caso Choquequirao)
1. **Desconexión entre respuesta de texto y botones rápidos:** Cuando un tour estaba inactivo (`is_active = 0` en base de datos), el motor de rutas [verified_routes.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/verified_routes.py) identificaba correctamente que el tour no estaba activo (`route = 'evidence_inactive_tour'`) e informaba que no figuraba en el catálogo. Sin embargo, la función `get_quick_buttons` en [app.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/app.py) no evaluaba el estado inactivo del tour y caía en la rama genérica de entidad detectada (`if detected_eid:`), generando botones comerciales de «Tarifas», «Qué incluye», «Fotos» y «Solicitar reserva».
2. **Ciclo vicioso:** Al presionar cualquiera de esos botones antiguos, el bot recibía la solicitud comercial para ese mismo tour y volvía a responder con la negativa, encerrando al turista en una repetición sin salida hacia tours alternativos.
3. **Fugas en creación de tickets de reserva:** [handoff_support.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py) registraba solicitudes comerciales en la tabla `requests` incluso para tours desactivados.

### B. Confusión de Estados: Desactivado vs. Sin Cupos vs. Error de Base de Datos vs. Catálogo Vacío
Antes de esta corrección, diferentes fallas técnicas se agrupaban o diagnosticaban con mensajes contradictorios:
- **Tour desactivado:** Debe informar que no figura en el catálogo activo y ofrecer *exclusivamente* «Ver otros tours» y «Consultar asesor».
- **Sin cupos o consulta de fecha:** No debe afirmar que el tour está fuera de catálogo; debe derivar la consulta de cupos al equipo de la agencia.
- **Fallo de lectura de base de datos:** Si la base de datos no responde, no se debe afirmar falsamente que los tours fueron desactivados ni inventar falta de disponibilidad; se debe informar un inconveniente técnico temporal y ofrecer reintento y asesor.
- **Catálogo vacío:** Si la base responde exitosamente pero hay 0 tours activos, se debe indicar que el catálogo está en actualización y ofrecer atención humana.

### C. Navegación Rígida vs. Acceso a Todo el Catálogo Activo
- Anteriormente se mostraba una lista fija o estática limitada a 2 tours en los botones interactivos de WhatsApp.
- Para dar acceso a **todo el catálogo activo** cumpliendo la restricción dura de la API de WhatsApp (máximo 3 botones interactivos y 20 caracteres por botón), se implementó un sistema de categorías dinámicas (`treks`, `cusco`, `reg`) con paginación controlada (`btn_cat_page:{cat}:{page}:{lang}`) que permite recorrer todos los tours activos sin editar listas fijas en el código.

### D. Referencias Ambiguas ("el otro")
- Cuando el turista comparaba dos tours ("Camino Inca" y "City Tour") y luego preguntaba "¿y el precio del otro?" o "¿tienes fotos del otro?", el bot adivinaba o caía en error genérico. Se centralizó la resolución de elisiones para solicitar aclaración entre los dos tours discutidos mediante botones claros y marcar `resolved_autonomously = False`.

---

## 2. Matriz de Estados y Acciones Válidas

| Estado / Situación | Intención del Cliente | Respuesta Generada | Acciones Válidas (Botones) | Siguiente Estado |
|---|---|---|---|---|
| **Tour activo con datos confirmados** | Pregunta libre o botón del tour | Ficha técnica con duración, horario y tarifa oficial | `📄 Qué incluye` · `📸 Ver Fotos` · `Solicitar reserva` | Ficha / Inclusiones / Fotos / Reserva |
| **Precio sin confirmar** | Pregunta por precio de tour sin tarifa fija | Explica que el precio y fechas se coordinan en agencia | `📄 Qué incluye` · `📸 Ver Fotos` · `Consultar asesor` | Exploración o Asesor |
| **Foto disponible** | Solicita fotos de tour con imagen | Imagen oficial enviada con pie de foto + texto de confirmación | `💰 Tarifas` · `📄 Qué incluye` · `Solicitar reserva` | Tarifas / Reserva |
| **Foto inexistente en línea** | Solicita fotos de tour sin foto | Explica que no dispone de foto online; asesor compartirá galería | `📄 Qué incluye` · `💰 Tarifas` · `Solicitar reserva` (sin botón foto) | Inclusiones / Asesor |
| **Fallo al enviar foto a Meta API** | Error de red/API al despachar imagen | Informa inconveniente técnico temporal sin mentir que se envió | `📸 Reintentar foto` · `📄 Qué incluye` · `Solicitar reserva` | Reintento / Reserva |
| **Tour desactivado** | Consulta tour inactivo o pulsa botón antiguo | Informa que no figura en catálogo activo; ofrece otros o asesor | `Ver otros tours` · `Consultar asesor` (NUNCA fotos/tarifas/reserva) | Catálogo / Asesor |
| **Catálogo vacío** | Consulta general con 0 tours activos | Informa catálogo en actualización | `Consultar asesor` | Asesor |
| **Error al cargar catálogo (BD)** | Fallo de conexión con PostgreSQL / SQLite | Informa inconveniente técnico temporal sin inventar datos | `Consultar asesor` · `Reintentar` | Reintento / Asesor |
| **Consulta ambigua ("el otro")** | "fotos del otro", "precio del otro" | Pregunta a cuál de los 2 tours se refiere específicamente | `[Tour 1]` · `[Tour 2]` · `🗺️ Ver Tours` | Aclaración guiada |
| **Solicitud al asesor ya abierta** | Reitera clic en «Solicitar reserva» | Informa que ya tiene solicitud pendiente; no duplica ticket | `Ver otros tours` · `📄 Qué incluye` / `Consultar asesor` | Continuación libre |

---

## 3. Resumen de Cambios Realizados y Lógica Reutilizada

### 1. `catalog_service.py`
- Incorporada la función exportada `is_deactivated_tour(entity_id: str) -> bool` que verifica el estado real en base de datos (`is_active = False` o `0`).
- Total reutilización de la infraestructura existente de PostgreSQL (Neon) y SQLite local con invalidación de caché sincronizada.

### 2. `verified_routes.py`
- **Clasificación dinámica de categorías:** Función `classify_tour_category(entity_id, name)` que ubica dinámicamente cualquier tour canónico o recién creado en `treks`, `cusco` o `reg`.
- **Acceso a catálogo completo:** Función `get_dynamic_cat_specs(active_tours_dict)` que construye las especificaciones de categorías ordenando primero los tours canónicos y anexando tours creados dinámicamente en tiempo de ejecución.
- **Distinción BD error vs vacío:** Función `get_current_tours_status()` que devuelve `is_read_error` (`evidence_catalog_error`) o `is_empty` (`evidence_catalog_empty`).
- **Detección de referencias ambiguas:** Regex ampliada para `el otro`, `del otro`, `la otra`, `de la otra`, `the other`, extrayendo todos los tours activos mencionados en el historial. Emite `evidence_ambiguous` con `pending=True` (`resolved_autonomously=False`).
- **Respuesta estándar para tours desactivados:** Texto uniforme bilingüe:
  - *ES:* `*{name}* no figura actualmente en nuestro catálogo activo. Puedes explorar otros tours o consultar este destino con un asesor.`
  - *EN:* `*{name}* is not currently in our active catalog. You can explore other tours or consult this destination with an advisor.`

### 3. `handoff_support.py`
- Verificación previa de tour desactivado antes de registrar solicitudes en `apply_request`: si `is_deactivated_tour(eid)`, bloquea la creación del ticket y responde inmediatamente con la información del tour inactivo, evitando tickets comerciales inválidos.

### 4. `app.py`
- **Reescritura de `get_quick_buttons`:** Implementada la matriz de estados con 16 casos prioritarios.
- **Paginación WhatsApp:** Soporte para `btn_cat_page:{cat}:{page}:{lang}` con botones interactivos `➡️ Más tours` / `➡️ More tours` y `⬅️ Categorías` / `⬅️ Categories`, respetando el límite estricto de Meta (<= 3 botones, <= 20 caracteres por título).
- **Mapeo de botones antiguos:** En `receive_message`, si un botón presionado apunta a un tour desactivado (`is_deactivated_tour(target_eid)`), la intención se redirige a consulta informativa, impidiendo bucles comerciales.
- **Propagación del fallo de foto:** Se conecta el parámetro `photo_send_failed=(photo_api_accepted is False)` hacia `get_quick_buttons` para emitir el botón de reintento controlado `📸 Reintentar foto`.

### 5. `trial_support.py`
- Enriquecimiento de marcadores lingüísticos en español e inglés (`informacion`, `info`, `detalles`, `cusco`, `fotos`, `foto`) para evitar que mensajes en español con nombres en inglés (ej. "City Tour") se clasifiquen erróneamente como inglés.

---

## 4. Matriz de Recorridos Probados y Evidencia Técnica

La suite de pruebas automatizadas en [`tests/test_whatsapp_flow_polish.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_whatsapp_flow_polish.py) cubre los 10 recorridos obligatorios, evaluando aserciones estrictas tanto de lo que **DEBE** aparecer como de lo que **NO DEBE** aparecer:

```
Ran 11 tests in 2.298s: 0 failures, 0 errors. OK.
```

| # | Recorrido Obligatorio | Entrada de Prueba | Lo que DEBE aparecer | Lo que NO DEBE aparecer | Resultado |
|---|---|---|---|---|---|
| **1** | **Saludo → Catálogo → Categoría → Tour → Detalles → Tarifa** | `Hola` → `btn_tours` → `btn_cat:treks` → `btn_tour:camino-inka` → `btn_inc` → `btn_rates` | Asistente virtual, 3 categorías, Camino Inca con duración/horario/tarifa, viñetas completas, 790 USD | Cortes con puntos suspensivos (`...`), botón engañoso `🙋‍♂️ Reservar` | **PASS** |
| **2** | **Tour A → Tour B → Botón antiguo de A** | Consulta Camino Inca → Consulta City Tour → Clic `btn_inc:camino-inka` | Respuesta exclusiva sobre Camino Inca; botones preservan `camino-inka` | Contenido de City Tour, pérdida de contexto | **PASS** |
| **3** | **Desactivar tour y pulsar botón antiguo** | Tour desactivado → Clic `btn_rates:choquequirao` y `btn_book:choquequirao` | Aviso de no activo; botones `Ver otros tours` y `Consultar asesor` | Botones comerciales (`Tarifas`, `Fotos`, `Reservar`), creación de tickets | **PASS** |
| **4** | **Tour desactivado → Elegir otra opción → Flujo normal** | Consulta Choquequirao → `btn_tours` → `btn_cat:cusco` → Clic `btn_tour:city-tour-cusco` | Aviso de no activo → listado de categorías → tours de Cusco → ficha de City Tour con acciones válidas | Bucles, bloqueos o reaparición del tour desactivado | **PASS** |
| **5** | **Alta y modificación de tour en catálogo dinámico** | Crear `Cañón de Tinajani` (60 USD) → modificar a 75 USD y 05:30 | Precio inicial 60 USD; tras modificación refleja 75 USD y nuevo horario sin reiniciar | Precio desactualizado (60 USD), edición de código estático | **PASS** |
| **6** | **Foto disponible, inexistente y envío fallido** | 6A: Machu Picchu tren (foto ok)<br>6B: Camino Inca (sin foto online)<br>6C: Machu Picchu (fallo Meta API) | 6A: Imagen oficial enviada + texto<br>6B: Honestidad: no hay foto online<br>6C: Aviso de inconveniente; botón reintentar | Afirmar que se envió foto cuando falló o no existe; fotos de otros tours | **PASS** |
| **7** | **Solicitud asesor → Repetición → Continuación** | `btn_book:camino-inka` → repetir clic → preguntar por Puno/Titicaca | Ticket registrado en BD como `pending`; aviso de ticket ya abierto; respuesta normal sobre Titicaca | Ticket duplicado en BD, afirmación de reserva confirmada, bloqueo del chat | **PASS** |
| **8** | **Catálogo vacío vs. Error de lectura BD** | 8A: 0 tours activos devueltos<br>8B: Excepción al consultar BD | 8A: Aviso de catálogo en actualización (`btn_advisor`)<br>8B: Aviso de fallo técnico temporal (`btn_advisor` y `btn_tours`) | Confundir error de BD con tours desactivados; inventar disponibilidad | **PASS** |
| **9** | **Mensajes libres, seguimiento elíptico y ambigüedad** | 9A: "saber del Camino Inca" → "¿y el precio?"<br>9B: "saber de 7 colores" → "¿cuál es la tarifa?"<br>9C: "Inca y City Tour" → "¿fotos del otro?" | 9A: Tarifa oficial 790 USD<br>9B: Explica que se coordina en agencia<br>9C: Pide aclaración entre los 2 tours con botones dedicados | Pérdida de tour en pregunta elíptica; adivinanza forzada en ambigüedad | **PASS** |
| **10** | **Recorrido equivalente en inglés** | `Hello` → `View Tours` → `Inca Trail` → `Request reservation` → Choquequirao inactivo | Saludo en inglés, categorías en inglés, ficha en inglés, aviso de tour inactivo en inglés | Textos en español, botón `Reservar`, botones comerciales en tour inactivo | **PASS** |
| **Reg** | **Regresión de seguridad, handoff y métricas** | Intento CSRF, cierre de ticket sin atender, métricas de latencia | HTTP 403 en CSRF; ValueError al cerrar sin atender; métricas `api_accepted` registradas | Accesos no autorizados, saltos en ciclo de vida de tickets | **PASS** |

### Resultados de Suites de Regresión
- `tests/test_audit_20260912.py`: **21 PASS / 0 FAIL** (100 %)
- `tests/test_conversational.py`: **36 PASS / 0 FAIL** (100 %)
- `tests/test_interactive_whatsapp_buttons.py`: **11 PASS / 0 FAIL** (100 %)
- `tests/test_flexible_tour_rates.py`: **21 PASS / 0 FAIL** (100 %)

---

## 5. Distinción entre Pruebas Simuladas y Pruebas Reales

| Aspecto | Pruebas Automatizadas Locales (`TestClient`) | Validación en Teléfono / WhatsApp Real |
|---|---|---|
| **Canal** | Simulación HTTP directa mediante ASGI TestClient (`/webhook`) | Servidor Cloud Run conectado a los webhooks de Meta for Developers |
| **Tokens / Secretos** | Mocks de `META_ACCESS_TOKEN` y firma HMAC simulada | Credenciales de producción en Secret Manager / variables de entorno de Cloud Run |
| **Despacho Multimedia** | Mock de `send_whatsapp_image` y `send_whatsapp_document` comprobando URL y caption | Petición real `POST https://graph.facebook.com/v21.0/{phone_number_id}/messages` |
| **Aceptación vs. Entrega** | Comprueba que el código invoque la función correcta con parámetros exactos | Comprueba respuesta HTTP 200 de Meta (`api_accepted`) y doble check de entrega en el dispositivo |
| **Interacción Humana** | Payloads sintéticos `button_reply` con `id` y `title` | Clic físico del usuario en la pantalla táctil de WhatsApp |

> [!NOTE]
> Ninguna prueba automatizada local se presenta como confirmación de entrega en un dispositivo móvil real. La validación en vivo se ejecutará en coordinación con el usuario utilizando un número de prueba autorizado tras el despliegue.

---

## 6. Limitaciones Técnicas Pendientes

Para mantener la honestidad técnica y cumplir con el estándar de no prometer "100 % de casos resueltos":
1. **Límites de la API de Meta en Mensajes Interactivos:** WhatsApp solo permite hasta 3 botones de tipo `button_reply` por mensaje. En categorías con más de 2 tours se requiere paginación secuencial (`➡️ Más tours`). Si una categoría llegara a tener 20 tours, requeriría múltiples páginas de navegación o escribir el nombre directamente.
2. **Límite de caracteres en botones:** Los títulos de los botones están estrictamente truncados a 20 caracteres por especificación de Meta. Nombres de tours muy largos aparecen acotados en el botón (ej. *"Machu Picchu Tren"*), aunque el texto del cuerpo muestra el nombre completo.
3. **Imágenes en Catálogo Local:** Únicamente los tours con fotografías físicas cargadas en `data/images/` y validadas en el catálogo disponen de entrega multimedia automática. Los demás tours aplican el protocolo honesto de derivación a galería del asesor.
4. **Entrega física en dispositivo:** El estado `api_accepted` confirma que los servidores de Meta aceptaron el mensaje; la recepción física en el teléfono depende de la conectividad, número válido y políticas de entrega de WhatsApp.

---

## 7. Instrucciones para Continuar con Otro Agente o Despliegue

1. **Estado del repositorio:** Todos los cambios están verificados en la rama `feature/polish-whatsapp-flow` de `texeira-prueba-v4-evidencias/`.
2. **Ejecutar pruebas rápidas de verificación:**
   ```bash
   python -m unittest tests/test_whatsapp_flow_polish.py
   python tests/run_isolated.py test_audit_20260912.py
   python tests/run_isolated.py test_conversational.py
   ```
3. **Procedimiento de Despliegue:**
   - Una vez aprobado el código por el usuario, realizar el merge formal a `main`.
   - Ejecutar `actualizar_nube.bat` para compilar y desplegar a Google Cloud Run.
   - Verificar en vivo con el número de prueba autorizado enviando:
     - `Hola`
     - Clic en `🗺️ Ver Tours`
     - Consulta sobre tour desactivado para verificar la ausencia de botones comerciales.

# Revisión de Antigravity — 27/09/2026

## Alcance y estado

Revisión de `2b93e20..7b3f796`: conversión WebP y botones de WhatsApp. Sin cambios al código de producción, despliegues, llamadas Groq ni mensajes reales. Solo se añadieron este informe y una reproducción sintética en tests. Se conserva el objetivo del bot: información documentada de la agencia, catálogo administrable y atención por WhatsApp.

Cloud Run informa revisión `texeira-whatsapp-00037-9zp` lista con 100% del tráfico. Esto no acredita por sí solo el funcionamiento de cada interacción ni identifica de forma independiente su commit.

## Hallazgos

1. **P1 — Botones sin vínculo al tour original.** `app.py:1877-1882`: IDs globales como btn_inc y btn_rates se traducen a consultas sin entidad. Tras consultar Camino Inca, cambiar a City Tour y pulsar el botón anterior «Qué incluye», responde City Tour. Reproducción: webhook real de la aplicación con firma sintética, envío externo simulado. Se debe transportar/validar el identificador del tour en el botón, o pedir aclaración cuando el contexto no corresponda. No basta con usar el último tour del historial.

2. **P2 — Los botones en inglés cambian al español.** `app.py:1877-1890`: todos los IDs se convierten a español. Conversación «What does the Inca Trail include?» seguida de btn_rates/«Rates» produce texto y botones en español. Preservar el idioma de la interacción al resolver la acción.

3. **P2 — Opciones fijas desconectadas del catálogo activo.** `app.py:1663-1675`: los listados siempre ofrecen Camino Inca y Machu Picchu, sin consultar si siguen activos. Es un defecto condicionado a desactivarlos: el panel podría ocultarlos y los botones continuar ofreciéndolos. Generar las opciones desde el catálogo vigente o usar acciones generales que no ofrezcan un tour desactivado.

4. **P2 — Prueba nueva no reproducible en base limpia.** `tests/test_interactive_whatsapp_buttons.py:189`: crea TestClient sin inicializar las tablas ni ejecutar el ciclo de arranque. En aislamiento obtiene 503 por `no such table: interactions`; pasa 6/7. No demuestra una caída en producción. Además, la prueba cubre un clic de foto, no el flujo completo ni idioma, contexto antiguo o desactivación. Inicializar su base temporal y ampliar los escenarios antes de declarar navegación completa validada.

## Verificación ejecutada

Ejecutor: `python tests/run_isolated.py NOMBRE.py`; base temporal y red externa bloqueada.

| Prueba | Resultado |
|---|---|
| test_interactive_whatsapp_buttons.py | 6/7; falla preparación de base |
| test_catalog_connected_flow.py | 10/10 |
| test_catalog_csrf_instances.py | 6/6 |
| test_conversational.py | 36/36 |
| test_index_preflight.py | PASS; manifiesto y 20 documentos |
| probe_antigravity_20260927.py | Reproduce cambio de tour e idioma; envíos simulados |

Logs en `logs/review_20260927_*.log` y `logs/review_antigravity_buttons_20260927.log`.

Las pruebas anteriores no verifican entrega real de Meta, calidad de Groq ni conversión de todas las variantes WebP. No se confirma ausencia de otros errores.

## Continuación acotada

Corregir contexto e idioma de botones; conectar opciones al catálogo; reparar/ampliar pruebas. Mantener respuestas libres y derivación existentes. Después seguir AGENTS.md: pruebas locales, rama feature y Git, despliegue versionado y verificación real. No añadir Messenger ni cambiar arquitectura en esta corrección.

Al iniciar la revisión ya estaban modificados `length.bin` del índice y `docs/evaluaciones/AUDIT_RETRIEVAL_RESULTS.json`; se preservaron. El cambio del JSON es en IDs/orden recuperados, no por sí mismo evidencia de un fallo. No se regeneró el índice.

---

## Resolución y Validación Ejecutada (27/09/2026)

### 1. Correcciones Implementadas

1. **P1 — Vínculo de entidad en botones (`app.py`, `verified_routes.py`)**:
   - Los botones interactivos ahora codifican formalmente la acción, entidad de tour e idioma: `btn_{action}:{entity_id}:{lang}` (ej: `btn_inc:camino-inka:es`, `btn_rates:camino-inka:en`).
   - Se mantiene la longitud bajo los límites de WhatsApp Cloud API (id ≤ 256 chars, title ≤ 20 chars).
   - Para botones legados o sin entidad en el ID, si el usuario discutió múltiples tours en su historial reciente, el sistema detecta la ambigüedad y solicita aclaración amigable ofreciendo botones para los tours en conflicto, evitando responder sobre el tour equivocado.

2. **P2 — Preservación de idioma inglés en botones y respuestas**:
   - `receive_message` extrae y prioriza el idioma especificado en el botón (`:en` o `:es`), complementado por detección semántica de títulos y contexto del turno anterior.
   - En `verified_routes.py`, se añadió soporte para tokens de tarifas en inglés (`rate`, `rates`) enrutando directamente a `evidence_confirmed_price`.
   - Se añadió diccionario de nombres de tours en inglés (`Inca Trail Classic 4D/3N`, `Machu Picchu by Train`, etc.) para títulos y textos en inglés.

3. **P2 — Conexión dinámica con tours activos del catálogo**:
   - Se implementó `_get_active_catalog_tour_buttons(lang)` en `app.py`, el cual consulta `catalog_service.get_all_tours(active_only=True)`.
   - Si un tour es desactivado en la base de datos o panel administrativo, se excluye inmediatamente de las sugerencias y botones de listado interactivo.

4. **P2 — Inicialización y cobertura en pruebas aisladas**:
   - En `tests/test_interactive_whatsapp_buttons.py`, se incorporó `app.database.init_db()` y `catalog_service.init_catalog_db()` en `setUp()`.
   - Se ampliaron 4 pruebas unitarias cubriendo:
     - `test_button_entity_binding_prevents_wrong_tour`
     - `test_button_preserves_english_language`
     - `test_buttons_connected_to_active_catalog_no_inactive_tours`
     - `test_ambiguous_legacy_button_requests_clarification`
   - Se corrigió `tests/probe_antigravity_20260927.py` para codificación UTF-8 en consola Windows.

### 2. Resultados de Pruebas Locales (100% PASS)

| Suite de Pruebas | Resultado | Detalle |
|---|---|---|
| `test_interactive_whatsapp_buttons.py` | **11/11 PASS** | Inicialización correcta en base limpia; cubre los 4 hallazgos. |
| `probe_antigravity_20260927.py` | **PASS** | Caso 1 pide aclaración con botones; Caso 2 responde 100% en inglés con botones en inglés. |
| `test_catalog_connected_flow.py` | **10/10 PASS** | Integración del catálogo SQLite sin regresiones. |
| `test_catalog_csrf_instances.py` | **6/6 PASS** | Seguridad CSRF e instancias en panel. |
| `test_conversational.py` | **36/36 PASS** | Respuestas conversacionales, directas y sin disclaimers. |
| `test_audit_20260912.py` | **21/21 PASS** | Auditoría y evaluación de respuestas. |
| `test_index_preflight.py` | **PASS** | Manifiesto y documentos de búsqueda vectorial. |


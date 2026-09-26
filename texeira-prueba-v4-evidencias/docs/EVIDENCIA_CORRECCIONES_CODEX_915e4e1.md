# Evidencia de Correcciones — Observaciones de Codex sobre Commit 915e4e1

**Proyecto**: Chatbot Texeira Travel (v4-evidencias)  
**Rama de trabajo**: `feature/corregir-catalogo-handoff-multimedia`  
**Fecha de ejecución**: 2026-09-24  
**Entorno de pruebas**: Local aislado (SQLite temporal y variables de entorno protegidas, sin alterar Neon productivo ni despachar WhatsApps reales).

---

## 1. Resumen Ejecutivo

Se han subsanado íntegramente los 6 problemas identificados por Codex sobre el commit `915e4e1`:

| # | Alcance / Componente | Defecto Previo | Solución Implementada | Estado |
|---|----------------------|----------------|-----------------------|--------|
| 1 | **CSRF (`catalog_support.py`)** | Basic Auth o IP loopback evadían la validación del token CSRF en mutaciones. | Se exige validación estricta de token CSRF (`hmac.compare_digest`) en todas las mutaciones (`POST` y `DELETE`). Ninguna cabecera ni IP local bypassa la verificación. | **RESUELTO** |
| 2 | **Tours desactivados (`verified_routes.py`, `app.py`)** | Al combinar catálogo dinámico con el JSON histórico, tours desactivados (`is_active=0`) podían reaparecer como activos. | Filtro estricto en catálogo y enrutamiento prioritario a `evidence_inactive_tour` con mensaje informativo y CTA de asesor; exclusión de listados y supresión de despacho multimedia. | **RESUELTO** |
| 3 | **Horarios vigentes (`src/evidence.py`)** | La condición `not any(f.field == 'schedule')` descartaba horarios actualizados de la agencia para tours con horario F1 previo. | El horario actualizado sustituye coherentemente los hechos de horario históricos, asignando trazabilidad `ADMIN_VIGENTE`, suprimiendo falsos conflictos y reflejándose en caliente. | **RESUELTO** |
| 4 | **Atención humana (`handoff_support.py`)** | "No quiero hablar con un asesor" escalaba indebidamente; la palabra "advisor" indicada por el bot no activaba handoff. | Se incorporó filtro de patrones de negación previa en español e inglés; se añadieron "advisor", "advisors", "agent" y variaciones a los patrones afirmativos. | **RESUELTO** |
| 5 | **Fotos rechazadas (`src/visual/visual_engine.py`)** | "No quiero fotografías del City Tour" y "No quiero images..." no cubrían todas las variantes ni se verificaba despacho. | Se alinearon todas las variantes de imagen/fotos/fotografías/photos/pictures con sus negaciones (con y sin acentos); se validó el despacho nulo con proveedor simulado. | **RESUELTO** |
| 6 | **Multimedia desactualizada (`catalog_service.py`)** | Nombres estáticos de archivo permitían que réplicas o instancias independientes sirvieran copias locales obsoletas. | Versionado inmutable por hash de contenido (`{eid}_{type}_{content_hash}{ext}`) y comprobación de timestamp en base de datos (`MAX(updated_at)`) para invalidación entre cachés. | **RESUELTO** |

---

## 2. Detalle Técnico de los Cambios

### 2.1 CSRF Estricto (`catalog_support.py`)
- **Problema**: La función `_authorized(request)` contenía un `or` que consideraba autorizada la solicitud si provenía de `127.0.0.1`, `testclient` o si contenía credenciales Basic Auth, omitiendo la validación CSRF.
- **Corrección**:
  - Se dividió en `_check_credentials(request)` para autenticación y `_validate_csrf(request)` para CSRF mediante `hmac.compare_digest(client_csrf, csrf_token)`.
  - Se creó `_authorized_mutation(request)` que **exige obligatoriamente ambos** factores en operaciones de mutación (`POST /api/catalog/tours`, `POST /api/catalog/upload/{entity_id}`, `DELETE /api/catalog/tours/{entity_id}`).
  - Se agregó el endpoint `GET /api/catalog/csrf-token` autenticado para obtener el token programáticamente.
  - En `GET /api/catalog/tours` se incorporó el filtro por defecto `active_only=True`, permitiendo `?all=1` para la administración.

### 2.2 Tours Desactivados (`verified_routes.py`, `app.py`)
- **Problema**: Tours canónicos marcados con `is_active=0` en el catálogo dinámico volvían a ser leídos como activos desde `evidence_facts.json` o incluidos en el listado de tours del bot.
- **Corrección**:
  - `get_current_tours()` y `get_confirmed_products()` verifican exclusivamente tours con `is_active = 1`.
  - Se implementó `is_deactivated_tour(eid)` que detecta tours dados de baja.
  - En `chain()`, las consultas directas (precio, horario, inclusiones, comercial) hacia un tour inactivo son interceptadas y responden bajo la ruta `evidence_inactive_tour`: *"Actualmente [Tour] no se encuentra disponible en nuestro catálogo activo... Escribe asesor..."*, sin confirmar tarifas activas.
  - `app.py` registró `evidence_inactive_tour` dentro del set `no_multimedia_routes`, bloqueando el envío de imágenes y folletos para entidades desactivadas.

### 2.3 Horarios Vigentes (`src/evidence.py`)
- **Problema**: `if tour.get("schedule") and not any(f.field == 'schedule' for f in result):` impedía que una actualización de horario en la base de datos se aplicara si el tour ya contaba con un hecho histórico `F1`.
- **Corrección**:
  - Se eliminó el guard `not any(...)` para mutaciones administrativas: cuando la agencia define o modifica un horario, se sustituyen los hechos de horario históricos preexistentes por un único `Fact` con `source_id='ADMIN_VIGENTE'` y `confidence=1.0`.
  - En `detect_conflicts()`, los campos amparados por hechos con `source_id == 'ADMIN_VIGENTE'` no generan conflictos con fuentes documentales históricas (`F1`/`F2`), reconociendo la decisión deliberada de la agencia.
  - Se actualizó el sembrado inicial en `catalog_service.py` (`_seed_from_json`) para que los tours canónicos comiencen sin sobreescritura administrativa (`schedule = ""`), preservando las auditorías históricas hasta que un administrador decida actualizar el horario en caliente.

### 2.4 Atención Humana y Handoff (`handoff_support.py`)
- **Problema**: Expresiones como *"No quiero hablar con un asesor"* coincidían con la expresión regular afirmativa `\b(quiero|...)\s+(hablar... con... asesor)`, disparando escalamientos no deseados. Además, la palabra *"advisor"* no estaba cubierta en las palabras clave directas.
- **Corrección**:
  - Se antepuso un bloque de filtrado estricto `negation_patterns` que rechaza de inmediato frases con negaciones (`no quiero...`, `no deseo...`, `no me llamen`, `no me contacten`, `no contactar con asesor`, `sin asesor`, `i don't want an advisor`, `do not transfer me to an advisor`, etc.).
  - Se agregaron tokens directos (`'advisor'`, `'advisors'`, `'agent'`, `'agents'`, `'human agent'`, `'human advisor'`) y patrones en inglés y español para activar el handoff cuando el usuario lo pide expresamente.

### 2.5 Fotos Rechazadas y Despacho Simulado (`src/visual/visual_engine.py`, `app.py`)
- **Problema**: El filtro negativo de fotos no contemplaba variantes como *"fotografías"* o *"images"* ni se evaluaba el despacho del proveedor simulado en WhatsApp.
- **Corrección**:
  - En `is_photo_requested()`, se unificaron los términos afirmativos y negativos:
    `photo_terms = r"(fotos?|im[aá]genes?|fotograf[ií]as?|photos?|pictures?|images?|photographs?)"`
    `negations = r"(no|sin|without|don't|do\s+not|never|tampoco)"`
  - Se probó con mock de `send_whatsapp_image` que para mensajes negativos el proveedor de mensajería nunca es invocado, mientras que para solicitudes afirmativas el envío se efectúa con la URL y caption oficial correspondiente.

### 2.6 Multimedia Desactualizada y Sincronización Multi-Instancia (`catalog_service.py`)
- **Problema**: Los archivos multimedia se guardaban con nombres estáticos `{entity_id}_{asset_type}{ext}`. Una segunda instancia en Cloud Run con caché local en disco no detectaba que otra instancia había subido una foto o folleto más reciente con el mismo nombre.
- **Corrección**:
  - **Versionado por hash inmutable**: El nombre del archivo ahora incluye los primeros 10 caracteres del SHA-256 de su contenido: `{entity_id}_{asset_type}_{content_hash}{ext}`.
  - **Detección entre cachés**: La función `_get_db_latest_update()` (`SELECT MAX(updated_at) FROM catalog_tours`) compara el timestamp de la base de datos contra el timestamp de la memoria local, invalidando automáticamente el caché en memoria de réplicas independientes.
  - **Sincronización a disco bajo demanda**: Si una réplica recibe una petición de asset versionado y no lo tiene en su disco local, `get_asset_bytes()` lo descarga directamente de la columna `photo_data` / `brochure_data` de la base de datos, lo cachea en su disco local y lo sirve inmediatamente.

---

## 3. Resultados de Pruebas Ejecutadas

### 3.1 Suite de Regresión Completa (`tests/test_codex_6_regressions.py`)
Ejecución automatizada de 86 aserciones cubriendo los 6 alcances:

```text
=====================================================================
   PRUEBAS DE REGRESIÓN: 6 CORRECCIONES CODEX (COMMIT 915e4e1)      
=====================================================================

--- 1. CSRF EN MUTACIONES DEL CATÁLOGO ---
  PASS | 1.1 POST /api/catalog/tours sin token CSRF retorna 403
  PASS | 1.2 POST /api/catalog/tours con token CSRF erróneo retorna 403
  PASS | 1.3 Basic Auth sin token CSRF no se salta validación (403)
  PASS | 1.4 Cliente local sin token CSRF es rechazado
  PASS | 1.5 POST /api/catalog/upload sin token CSRF retorna 403
  PASS | 1.6 DELETE /api/catalog/tours sin token CSRF retorna 403
  PASS | 1.7 Endpoint GET /api/catalog/csrf-token responde 200
  PASS | 1.8 Token CSRF obtenido es válido y no vacío
  PASS | 1.9 POST /api/catalog/tours con token CSRF válido responde 200 OK
  PASS | 1.10 DELETE /api/catalog/tours con token CSRF válido responde 200 OK

--- 2. TOURS DESACTIVADOS ---
  PASS | 2.1 Tour desactivado no aparece en get_all_tours(active_only=True)
  PASS | 2.2 Tour desactivado no aparece en GET /api/catalog/tours
  PASS | 2.3 Tour desactivado no aparece en el listado conversacional del bot
  PASS | 2.4 Consulta de precio para tour desactivado enruta a evidence_inactive_tour
  PASS | 2.5 Respuesta informa no disponibilidad y ofrece asesor
  PASS | 2.6 Respuesta no confirma precio oficial activo
  PASS | 2.7 Consulta de horario para tour desactivado enruta a evidence_inactive_tour
  PASS | 2.8 get_tour_image_data retorna None para tour desactivado
  PASS | 2.9 get_tour_brochure_data retorna None para tour desactivado
  PASS | 2.10 evidence.get_facts retorna lista vacía para tour desactivado
  PASS | 2.11 is_product_confirmed es False para tour desactivado

--- 3. HORARIOS VIGENTES ACTUALIZADOS ---
  PASS | 3.1 get_facts contiene exactamente 1 hecho de horario
  PASS | 3.2 Horario actualizado coincide con el valor nuevo
  PASS | 3.3 Trazabilidad de origen es ADMIN_VIGENTE
  PASS | 3.4 detect_conflicts no genera falso conflicto sobre horario ADMIN_VIGENTE
  PASS | 3.5 Consulta de horario enruta a evidence_schedule
  PASS | 3.6 Respuesta contiene el horario nuevo actualizado
  PASS | 3.7 Respuesta NO contiene el horario histórico antiguo

--- 4. ATENCIÓN HUMANA (HANDOFF) ---
  PASS | 4.1 Negativo ES: 'No quiero hablar con un asesor' no escala
  PASS | 4.1 Negativo ES: 'No deseo un asesor' no escala
  PASS | 4.1 Negativo ES: 'No me comuniquen con un asesor' no escala
  PASS | 4.1 Negativo ES: 'Por favor no me llame un asesor' no escala
  PASS | 4.1 Negativo ES: 'No contactar con asesor' no escala
  PASS | 4.1 Negativo ES: 'no quiero asesor' no escala
  PASS | 4.1 Negativo ES: 'Sin asesor por favor' no escala
  PASS | 4.2 Negativo EN: 'I do not want to speak to an advisor' no escala
  PASS | 4.2 Negativo EN: 'I don't want an advisor' no escala
  PASS | 4.2 Negativo EN: 'Do not transfer me to an advisor' no escala
  PASS | 4.2 Negativo EN: 'No advisor please' no escala
  PASS | 4.2 Negativo EN: 'Don't call me' no escala
  PASS | 4.2 Negativo EN: 'No agent please' no escala
  PASS | 4.2 Negativo EN: 'without advisor' no escala
  PASS | 4.3 Positivo ES: 'asesor' sí escala
  PASS | 4.3 Positivo ES: 'asesores' sí escala
  PASS | 4.3 Positivo ES: 'quiero hablar con un asesor' sí escala
  PASS | 4.3 Positivo ES: 'comunícame con un asesor' sí escala
  PASS | 4.3 Positivo ES: 'deseo contactar a un asesor' sí escala
  PASS | 4.3 Positivo ES: 'ayuda humana' sí escala
  PASS | 4.3 Positivo ES: 'atención de una persona' sí escala
  PASS | 4.4 Positivo EN: 'advisor' sí escala
  PASS | 4.4 Positivo EN: 'advisors' sí escala
  PASS | 4.4 Positivo EN: 'agent' sí escala
  PASS | 4.4 Positivo EN: 'agents' sí escala
  PASS | 4.4 Positivo EN: 'human advisor' sí escala
  PASS | 4.4 Positivo EN: 'human agent' sí escala
  PASS | 4.4 Positivo EN: 'I want to speak to an advisor' sí escala
  PASS | 4.4 Positivo EN: 'speak to an agent' sí escala
  PASS | 4.4 Positivo EN: 'talk to a person' sí escala
  PASS | 4.5 /test-chat con rechazo de asesor no genera handoff
  PASS | 4.5 /test-chat con 'advisor' genera handoff correctamente

--- 5. FOTOS RECHAZADAS Y DESPACHO SIMULADO ---
  PASS | 5.1 Detección negativa: 'No quiero fotografías del City Tour' es False
  PASS | 5.1 Detección negativa: 'No quiero images del City Tour' es False
  PASS | 5.1 Detección negativa: 'no quiero fotografias del city tour' es False
  PASS | 5.1 Detección negativa: 'no quiero imagenes del city tour' es False
  PASS | 5.1 Detección negativa: 'Por favor sin fotos' es False
  PASS | 5.1 Detección negativa: 'Sin imágenes del tour' es False
  PASS | 5.1 Detección negativa: 'Don't send pictures of City Tour' es False
  PASS | 5.1 Detección negativa: 'I do not want photos' es False
  PASS | 5.1 Detección negativa: 'No photos please' es False
  PASS | 5.1 Detección negativa: 'without pictures' es False
  PASS | 5.2 Detección afirmativa: 'Quiero fotografías del City Tour' es True
  PASS | 5.2 Detección afirmativa: 'Quiero images del City Tour' es True
  PASS | 5.2 Detección afirmativa: 'Mándame fotos de Machu Picchu' es True
  PASS | 5.2 Detección afirmativa: 'Can you show me pictures?' es True
  PASS | 5.2 Detección afirmativa: 'Send me photographs please' es True
  PASS | 5.3 Despacho simulado: send_whatsapp_image NO fue llamado para fotos rechazadas
  PASS | 5.4 Despacho simulado: send_whatsapp_image SÍ fue llamado para solicitud afirmativa

--- 6. MULTIMEDIA DESACTUALIZADA ENTRE DOS CACHÉS INDEPENDIENTES ---
  PASS | 6.1 Instancia A sube Foto V1 exitosamente con nombre versionado
  PASS | 6.2 Foto V1 guardada en disco de Instancia A
  PASS | 6.3 Instancia B inicialmente no tiene el archivo en disco local
  PASS | 6.4 Instancia B recupera bytes de Foto V1 sincronizados desde la BD
  PASS | 6.5 Instancia B guardó en su disco local la copia V1
  PASS | 6.6 Instancia A actualiza a Foto V2 con nuevo hash inmutable
  PASS | 6.7 Instancia B detecta automáticamente filename_v2 tras invalidación verificable
  PASS | 6.8 Instancia B recupera bytes de Foto V2 (no la copia local antigua V1)
  PASS | 6.9 Instancia B tiene en disco local la versión V2 actualizada

=====================================================================
RESULTADO FINAL: 86 PASS / 0 FAIL
=====================================================================
```

### 3.2 Suites de Integración Existentes (Cero Regresiones)
- `tests/test_catalog_api.py`: 12 PASS / 0 FAIL.
- `tests/test_catalog_dynamic.py`: 12 PASS / 0 FAIL.
- `tests/test_multimedia_dispatch.py`: 25 PASS / 0 FAIL.
- `tests/test_conversational.py`: 36 PASS / 0 FAIL.
- `tests/test_handoff.py`: PASS (todos los flujos y concurrencia validados).
- `tests/test_audit_20260912.py`: 21 PASS / 0 FAIL.

---

## 4. Limitaciones Reales y Consideraciones Operativas

1. **Ciclo de vida del token CSRF**: El token CSRF se genera en el arranque del servidor mediante `secrets.token_hex(32)`. Si una réplica en Cloud Run se reinicia por inactividad (escala a cero), el panel web `/catalogo` recargará automáticamente la página y obtendrá el nuevo token vigente.
2. **Caché en disco de réplicas**: Las réplicas de Cloud Run tienen un sistema de archivos efímero. Al guardar los bytes multimedia tanto en disco como en PostgreSQL (`BYTEA`), cualquier réplica recién creada o que sirva una versión actualizada descargará los assets bajo demanda sin requerir almacenamiento persistente NFS.
3. **Persistencia y Aislamiento**: Las pruebas se ejecutaron sobre SQLite local con limpieza en bloques `finally`. La base de datos de producción Neon no fue alterada y no se emitieron peticiones externas hacia la API de WhatsApp de Meta.

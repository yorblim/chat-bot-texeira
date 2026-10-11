# Verificación de Despliegue en Producción — Revisión 00051 (10/10/2026)

## 1. Resumen del Despliegue y GitOps

- **Rama de funcionalidad:** `feature/fix-real-rag-quality-20261010` (respaldada en `origin`).
- **Commits en la rama:**
  - `79efade`: `feat: aislamiento de contexto RAG, navegacion FR/IT y robustez en deteccion de idiomas`
  - `74d0832`: `docs: registrar catalogo de referencia LLM y reporte de evaluacion RAG dry-run`
- **Merge a producción (`main`):** `036901a` (`Merge feature/fix-real-rag-quality-20261010: aislamiento RAG, navegacion multilingue FR/IT y lote de evaluacion`).
- **Sincronización remota:** `origin/main` actualizado y verificado.
- **Revisión en Cloud Run:** `texeira-whatsapp-00051-9dn`.
- **URL canónica del servicio:** `https://texeira-whatsapp-1038134693816.us-central1.run.app`.
- **Tráfico:** 100 % servido por la revisión `00051`.
- **Política de costos:** `min-instances = 0` (escala a cero, Costo $0.00 en reposo).

---

## 2. Pruebas Locales Previas (100 % Superadas en Aislamiento)

- `tests/test_real_rag_grounding_20261010.py`: **9/9 PASS** (aislamiento estricto de catálogo activo, no contaminación con tours inactivos/ajenos, respeto de campos borrados).
- `tests/test_french_italian_navigation_20261010.py`: **16/16 PASS** (menús, botones <= 20 chars, callbacks y retención de idioma en FR e IT).
- `tests/test_language_collisions_20261010.py`: **39/39 PASS** (detección precisa de español vs portugués, resolución de erratas como "em").
- `tests/test_real_rag_batch_contract_20261010.py`: **8/8 PASS** (contratos y límites del evaluador de lote RAG).
- `tests/test_open_questions_and_portuguese_20261009.py`: **58/58 PASS** (preguntas abiertas y preservación de idioma portugués).
- **Evaluación en lote seco:** 10/10 casos completados sin llamadas externas ni costos (`completed_pending_semantic_review`).

---

## 3. Verificaciones en Vivo en Producción (Revisión 00051)

1. **Endpoint de salud `/health`:**
   - Estado: `HTTP 200 OK`
   - Respuesta: `{"status": "ok"}`
2. **Endpoint raíz `/`:**
   - Estado: `HTTP 200 OK`
   - Versión: `2.0.0-tesis`
3. **Seguridad y Control de Acceso:**
   - `/dashboard` sin credenciales: Rechazado con `HTTP 401 Unauthorized`.
   - `/dashboard` autenticado: `HTTP 200 OK` (53,136 bytes).
4. **Verificación de Paneles (`tests/verify_panels_readonly.py`):**
   - `/handoffs`: PASS (401 sin auth, 200 con auth)
   - `/catalogo`: PASS (401 sin auth, 200 con auth)
   - `/dashboard`: PASS (401 sin auth, 200 con auth)
   - `/operational-metrics`: PASS (401 sin auth, 200 con auth)
5. **Comportamiento Conversacional Sintético (`tests/verify_live_deployment.py`):**
   - Entrada `ayuda`: Responde 200 OK sin números telefónicos ni imágenes no solicitadas.
   - Entrada `qué tours tienen`: Responde 200 OK con catálogo limpio y verificado.
6. **Recomendaciones en Vivo (`tests/verify_live_portuguese_recommendations.py`):**
   - Catálogo activo: Estrictamente los 3 tours autorizados (`camino-inka`, `inka-jungle`, `maras-moray`).
   - Flujo en portugués verificado con retención de idioma y botones `:pt`.
7. **Base de Datos Neon PostgreSQL:**
   - Persistencia confirmada en tablas `interactions` y `conversation_memory`.
   - Limpieza automática de datos sintéticos ejecutada tras las pruebas.

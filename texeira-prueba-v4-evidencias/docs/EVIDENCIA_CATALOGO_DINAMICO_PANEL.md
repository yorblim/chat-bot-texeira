# Evidencia de Implementación: Gestor Dinámico de Catálogo y Tarifas (Fase 1)

## 📌 Resumen Técnico
- **Rama Git**: `feature/catalogo-dinamico-panel`
- **Módulos Creados**:
  - `catalog_service.py`: Capa de persistencia universal (PostgreSQL Neon / SQLite local), caché en memoria, validaciones y manejo de assets binarios (`BYTEA`/`BLOB`) y en disco (`data/images/`, `data/brochures/`).
  - `catalog_ui.py`: Panel web moderno en Vanilla JS para administración de tours, actualización de precios oficiales, horarios y subida de fotos/folletos con protección CSRF.
  - `catalog_support.py`: Endpoints REST (`/api/catalog/...`) y servidor de folletos PDF y fotos locales/remotas.
- **Módulos Integrados**:
  - `app.py`: Mapeo dinámico de productos confirmados (`DynamicConfirmedProducts`, `DynamicEntityNameMap`), respuesta determinista a preguntas de precios oficiales confirmados (`evidence_confirmed_price`), fallback a base de datos en `/images/{filename}` e instalación del servicio de catálogo.
  - `auth_middleware.py`: Protección con Basic Auth de `/catalogo` y `/api/catalog` en despliegues cloud.
  - `db_adapter.py`: Definición de esquema para `catalog_tours` en PostgreSQL.
  - `src/evidence.py`: Hechos de precios oficiales y horarios dinámicos con trazabilidad `ADMIN_VIGENTE`.
  - `trial_support.py`: Detección en vivo de nuevos tours a través de palabras clave y alias configurados por el administrador.
  - `handoff_support.py` y `admin_dashboard.py`: Enlaces de navegación rápida cruzada hacia `/catalogo`.

---

## 🧪 Resultados de Pruebas Automatizadas Locales (100% PASS)

1. **`tests/test_catalog_dynamic.py`**:
   - **Resultado**: `12 PASS / 0 FAIL`
   - Siembra inicial canónica (19 tours).
   - Creación de tour dinámico y persistencia.
   - Detección de entidad por alias.
   - Generación de hecho confirmado de tarifa oficial.
   - Actualización en caliente de precio sin reinicio.
   - Subida y recuperación de foto (JPG) y folleto (PDF).
   - Limpieza garantizada de entidades sintéticas en `finally`.

2. **`tests/test_catalog_api.py`**:
   - **Resultado**: `12 PASS / 0 FAIL`
   - `GET /catalogo` (200 OK con HTML y CSRF token).
   - `GET /api/catalog/tours` (200 OK).
   - `POST /api/catalog/tours` (200 OK con creación de tour).
   - `POST /api/catalog/upload/{id}` para foto y folleto (200 OK).
   - `GET /images/{filename}` y `GET /brochures/{filename}` (200 OK con Content-Type correcto).
   - `DELETE /api/catalog/tours/{id}` (200 OK).
   - Purgado de datos de prueba en `finally`.

3. **Regresión y Auditoría Canónica**:
   - `tests/test_catalog_validation.py`: `PASS` (Los 19 tours canónicos, políticas y contactos F1/F2 intactos).
   - `tests/test_audit_20260912.py`: `21 PASS / 0 FAIL` (21 casos endpoint + integridad y métricas).
   - `tests/test_conversational.py`: `29 PASS / 0 FAIL` (29 casos conversacionales de saludo, ayuda, evidencia y disclaimers).

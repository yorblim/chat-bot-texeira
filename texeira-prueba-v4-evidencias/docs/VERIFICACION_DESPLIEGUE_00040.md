# Verificación Técnica de Despliegue — Revisión 00040 (Cloud Run)

**Fecha:** 1 de octubre de 2026  
**Rama Git:** `main` (Merge fast-forward de `feature/polish-whatsapp-flow`)  
**Commit integrado:** `01927ca` (*feat: incorporar hechos oficiales de Humantay e Inka Jungle, actualizar indice y habilitar respuesta parcial*)  
**Revisión en Cloud Run:** `texeira-whatsapp-00040-xwc`  
**URL de Servicio:** `https://texeira-whatsapp-1038134693816.us-central1.run.app`  
**Referencia:** Protocolo permanente `AGENTS.md`  

---

## 1. Trazabilidad Git y Respaldo Remoto

- **Rama local integrada:** `feature/polish-whatsapp-flow` fusionada limpiamente a `main` (commit `01927ca`).
- **Respaldo en GitHub (origin):**
  - `origin/feature/polish-whatsapp-flow` actualizado a `01927ca`.
  - `origin/main` actualizado a `01927ca`.
- **Respaldo en GitLab (gitlab):**
  - `gitlab/feature/polish-whatsapp-flow` actualizado a `01927ca`.
  - `gitlab/main` actualizado a `01927ca`.
- **Estado de árbol:** Completamente limpio (`working tree clean`), sin código fantasma ni modificaciones pendientes.

---

## 2. Resultados de Pruebas Locales Previas al Despliegue (100 % Aprobadas)

Conforme al Paso 1 de `AGENTS.md`, se ejecutó la suite completa de pruebas en el entorno local antes de tocar producción:

1. **`tests/test_whatsapp_flow_polish.py`:** **11 PASS / 0 FAIL** (100 %)  
   - Validación de los 10 recorridos obligatorios: navegación por categorías dinámicas, paginación, desactivación limpia sin bucles, derivación a asesor sin confirmar reservas en línea, y entrega honesta de fotos.
2. **`tests/run_isolated.py test_audit_20260912.py`:** **21 PASS / 0 FAIL** (100 %)  
   - Integridad de endpoints, prevención de conflictos y métricas operativas.
3. **`tests/run_isolated.py test_conversational.py`:** **36 PASS / 0 FAIL** (100 %)  
   - Enrutamiento determinista de saludos, ayuda, inclusiones, horarios y listados de catálogo.
4. **`tests/run_isolated.py test_calidad_whatsapp.py`:** **13 PASS / 0 FAIL** (100 %)  
   - Calidad conversacional en 5 escenarios: errores tipográficos en español/inglés, ambigüedades, preguntas fuera de catálogo y derivaciones a asesor humano.
5. **`tests/test_catalog_dynamic.py`:** **12 PASS / 0 FAIL** (100 %)  
   - Siembra de 19 tours canónicos, creación en caliente de tours dinámicos, modificación inmediata de tarifas y gestión de assets (foto y folleto).
6. **`tests/test_neon_ssl_adapter.py`:** **22 PASS / 0 FAIL** (100 %)  
   - Conexión segura TLS, protección de credenciales, compatibilidad SCRAM-SHA-256-PLUS y sanitización de excepciones con Neon PostgreSQL.

---

## 3. Estado de la Infraestructura en Google Cloud Run

Configuración verificada de la revisión activa:

- **Revisión activa:** `texeira-whatsapp-00040-xwc` (recibiendo el 100 % del tráfico).
- **Región:** `us-central1`
- **Proyecto:** `texeira-whatsapp-bot`
- **Recursos de cómputo:** 1 vCPU, 2 GiB RAM, `startup-cpu-boost = true`.
- **Escalabilidad y Costo:** `min-instances = 0` (escala a cero, costo $0.00 cuando no hay tráfico), `max-instances = 2`.
- **Proveedor y Secretos:** Intactos y conservados desde Secret Manager:
  - `LLM_PROVIDER`: `groq` (`qwen/qwen3.8-27b`)
  - `DATABASE_URL`: Versión `1` (Neon PostgreSQL)
  - `ADMIN_PASSWORD`: Versión `2`
  - Secretos Meta Graph API: `META_VERIFY_TOKEN`, `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_APP_SECRET`.

---

## 4. Verificación de Endpoints en Vivo (Solo Lectura)

Comprobaciones ejecutadas directamente contra el servicio desplegado en Cloud Run:

1. **Endpoint de Salud (`/health`):**
   - Código HTTP: `200 OK`
   - Respuesta: `{"status":"ok"}`
2. **Paneles Administrativos (`tests/verify_panels_readonly.py`):**
   - `/handoffs`: `401 Unauthorized` sin credenciales; `200 OK` con autenticación Basic (marcador `ticketSearch` verificado).
   - `/catalogo`: `401 Unauthorized` sin credenciales; `200 OK` con autenticación Basic (marcador `tourModal` verificado).
   - `/dashboard`: `401 Unauthorized` sin credenciales; `200 OK` con autenticación Basic (marcador `Resumen de interacciones` verificado).
   - `/operational-metrics`: `401 Unauthorized` sin credenciales; `200 OK` con autenticación Basic (marcador `rows-traffic` verificado).

---

## 5. Próximo Paso: Coordinación de Prueba Real por WhatsApp

Con la integración y el despliegue técnico concluidos y validados:
- **No se añadieron nuevas funcionalidades.**
- El sistema está listo para coordinar la prueba en vivo por WhatsApp utilizando el número de teléfono autorizado configurado en el entorno de pruebas (`WHATSAPP_TEST_BSUID_MAP`).
- Se verificará en WhatsApp real:
  1. Saludo y navegación por categorías (`🗺️ Ver Tours`).
  2. Consulta de tours y respuesta parcial de Laguna Humantay (altitud 4,200 msnm / Soraypampa 3,920 msnm indicando confirmación de subida a pie).
  3. Despacho honesto de fotos y opciones disponibles.
  4. Solicitud de contacto con el asesor comercial sin afirmar confirmación de pago o reserva automática.

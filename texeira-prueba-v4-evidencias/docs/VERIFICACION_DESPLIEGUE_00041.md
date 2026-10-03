# Verificacion Tecnica de Despliegue — Revision 00041 (Cloud Run)

**Fecha:** 2 de octubre de 2026
**Rama Git:** `main` — HEAD `d8a9250`
**Commit desplegado:** `d8a9250` (fix: conservar restricciones entre turnos, filtrar por dias exactos y respetar borrado de duracion)
**Revision en Cloud Run:** `texeira-whatsapp-00041-bmx`
**URL de Servicio:** `https://texeira-whatsapp-1038134693816.us-central1.run.app`
**Referencia:** Protocolo permanente AGENTS.md

---

## 1. Trazabilidad Git y Respaldo Remoto

- **HEAD local:** `d8a9250` (main)
- **Respaldo GitHub (origin/main):** `d8a9250` OK
- **Respaldo GitLab (gitlab/main):** pendiente (token expirado; push a renovar)
- **Commits incluidos en este despliegue (sobre 00040):**
  - `5d0d756` fix: corregir bucle de aclaracion en recomendaciones, filtrado de tours inactivos y respeto de overridden_fields
  - `bf906bc` Merge feature/fix-recommendations-and-schedules
  - `21e4e9a` docs: registrar cierre de verificacion 20261002
  - `d8a9250` fix: conservar restricciones entre turnos, filtrar por dias exactos y respetar borrado de duracion

---

## 2. Resultados de Pruebas Locales Previas al Despliegue

| Suite | Resultado |
|---|---|
| test_review_followups_20261002.py (4 casos) | **4 PASS / 0 FAIL** |
| test_review_recommendations_20261002.py (6 casos) | **6 PASS / 0 FAIL** |
| test_recommendations_and_schedules.py (5 casos) | **5 PASS / 0 FAIL** |
| test_audit_20260912.py (21 casos) | **21 PASS / 0 FAIL** |
| test_conversational.py (36 casos) | **36 PASS / 0 FAIL** |
| **TOTAL** | **72 PASS / 0 FAIL** |

---

## 3. Estado de la Infraestructura en Google Cloud Run

- **Revision activa:** `texeira-whatsapp-00041-bmx` (latestReadyRevision = latestCreatedRevision)
- **Region:** `us-central1`
- **Proyecto:** `texeira-whatsapp-bot`
- **Recursos de computo:** 2 GiB RAM, `startup-cpu-boost = true`
- **Escalabilidad y Costo:** `min-instances = 0`, `max-instances = 2`
- **Secretos:** conservados intactos desde Secret Manager (LLM_PROVIDER, DATABASE_URL, ADMIN_PASSWORD, META_*)

---

## 4. Verificacion de Endpoint en Vivo (Solo Lectura)

- **Endpoint de Salud (/health):**
  - Codigo HTTP: 200 OK
  - Respuesta: {"status":"ok"}

---

## 5. Proximo Paso: Prueba Real en WhatsApp

El sistema esta listo para la verificacion real por WhatsApp:

1. Saludo y navegacion por categorias (Ver Tours).
2. «Que tours me recomiendas» -> pregunta de preferencias -> respuesta orientada con tours activos.
3. Consulta de Laguna Humantay (altitud 4,200 msnm).
4. «No quiero caminatas» + «un dia» -> debe excluir Humantay y Montana de 7 Colores.
5. Despacho honesto de fotos.
6. Solicitud de asesor comercial sin confirmar reserva en linea.

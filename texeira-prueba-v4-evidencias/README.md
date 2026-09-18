# Guía de Operación y Uso — Prototipo Texeira (v4 Evidencias)

Versión activa canónica del proyecto de software y tesis de Texeira Travel Tour.

---

## 1. Servicios y Puertos Activos

El sistema está desacoplado en tres procesos independientes para garantizar estabilidad y seguridad:

| Servicio | Script de Inicio | Puerto Local | URL / Endpoint | Función |
|---|---|:---:|---|---|
| **Chat Web & API** | `INICIAR.ps1` | `8021` | `http://127.0.0.1:8021/chat`<br>`http://127.0.0.1:8021/test-chat` | Interfaz web de usuario y endpoint RAG para pruebas. |
| **Webhook WhatsApp** | `INICIAR_WHATSAPP.ps1` | `8022` | `http://127.0.0.1:8022/webhook` | Recepción de eventos de Meta for Developers / WhatsApp Cloud API. |
| **Panel Asesores & Métricas** | `INICIAR_ASESORES.ps1` | `8023` | `http://127.0.0.1:8023/handoffs`<br>`http://127.0.0.1:8023/metrics` | Bandeja de tickets humanos persistentes y dashboard de métricas. |

> [!NOTE]
> Al arrancar el servidor principal (`INICIAR.ps1`), el buscador híbrido (BM25 + Chroma) precarga los índices en aproximadamente 20–30 segundos antes de recibir la primera petición.

---

## 2. Puesta en Marcha en Local

### Paso 1: Iniciar el chat de usuario
```powershell
cd "C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias"
.\INICIAR.ps1
```
Abrir en el navegador: **http://127.0.0.1:8021/chat**

### Paso 2: Iniciar el panel de asesores humanos y métricas (opcional)
```powershell
cd "C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias"
.\INICIAR_ASESORES.ps1
```
Abrir en el navegador: **http://127.0.0.1:8023/handoffs**

---

## 3. Pruebas y Suites de Verificación

Para verificar el correcto funcionamiento sin consumir tokens ni realizar llamadas externas:

```bash
# Auditoría de recuperación híbrida sin LLM (RRF60 / top 5 / cap 2):
python tests/test_audit_retrieval.py

# Benchmark Académico Formal de la Tesis (30 casos independientes ES/EN):
python tests/evaluate_academic_benchmark.py

# Aceptación de idiomas y consistencia ES/EN (16 casos):
python tests/evaluate_language_local.py

# Regresión de integridad, conflictos y métricas (21 casos):
python tests/test_audit_20260912.py

# Pruebas de traducción de duración y cola persistente de asesores:
python tests/test_duration_translation.py
python tests/test_handoff.py
```

---

## 4. Estructura de Datos e Índice Activo

- **Catálogo Canónico:** `data/tours_catalog.json` (19 tours y productos conciliados con el folleto F1, catálogo PDF F2 e itinerarios F3).
- **Hechos y Conflictos:** `data/evidence_facts.json` y `data/conflicts.json`.
- **Registro de Fuentes:** `data/source_registry.json`.
- **Índice Vectorial Activo:** `chroma_f1_confirmado_20260915_db/` (HuggingFace embeddings locales, RRF=60, top 5).
- **Persistencia y Estado:** `state/` (`human_requests.db`, `trial_logs.db` con SQLite y PRAGMA WAL).

---

## 5. Indicadores Operativos en Respuestas

| Campo | Significado cuando es `True` | Significado cuando es `False` |
|---|---|---|
| `resolved_autonomously` | Consulta informativa resuelta con contexto documental verificado. | Requiere confirmación de la agencia o fue derivada a atención humana. |
| `needs_agency_confirmation` | El dato consultado (pagos, depósitos, cancelación, horarios en conflicto) debe ser confirmado por Texeira. | Información completamente respaldada en folleto o catálogo. |
| `escalated_to_human` | Se ejecutó una solicitud formal de derivación registrada en el panel (`handoff_id`). | No hay derivación humana efectiva. |

---

## 6. Limitaciones Metodológicas

1. Los precios del catálogo son referenciales o están pendientes de confirmación oficial con la agencia; el bot no confirma cotizaciones en soles ni emite reservas definitivas.
2. La derivación humana genera un ticket persistente local; la notificación push al WhatsApp del personal requiere configurar el número del asesor.
3. El funcionamiento local o mediante túneles no certifica disponibilidad ininterrumpida 24/7; para producción se requiere despliegue en servidor en la nube.

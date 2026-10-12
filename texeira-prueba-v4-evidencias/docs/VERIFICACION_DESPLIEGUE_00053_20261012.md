# Verificación de Despliegue en Producción — Revisión 00053 (12/10/2026)

## 1. Resumen del Despliegue y GitOps

- **Rama de integración:** `main` (respaldada en `origin/main`).
- **Commits asociados:**
  - `8c226b8`: `feat: hacer configurable el enlace y numero de whatsapp del asesor via ADVISOR_PHONE`
- **Revisión en Cloud Run:** `texeira-whatsapp-00053-t9p`.
- **URL canónica del servicio:** `https://texeira-whatsapp-1038134693816.us-central1.run.app`.
- **Tráfico:** 100 % servido por la revisión `00053`.
- **Política de costos:** `min-instances = 0` (escala a cero, Costo $0.00 en reposo).
- **Recursos del contenedor:** 2Gi RAM, `--cpu-boost` habilitado.

---

## 2. Nueva Capacidad: Configuración Dinámica de Contacto Humano

1. **Variable de Entorno `ADVISOR_PHONE` / `ADVISOR_WHATSAPP_PHONE`**:
   - Permite definir el número telefónico de atención sin modificar el código fuente.
   - Limpieza automática de espacios, guiones y signos (`+51 984-679-715` ➔ `51984679715`).
   - Normalización inteligente de números peruanos de 9 dígitos (`984679715` ➔ `51984679715`).
2. **Modo Sin Enlace Directo**:
   - Si la variable se configura como `disabled`, `none`, `false` o vacía, el bot omite el enlace de WhatsApp y entrega únicamente el mensaje formal con el ticket de seguimiento (`Tu solicitud está registrada y pendiente de atención humana...`).
3. **Valor Predeterminado Seguro**:
   - En ausencia de configuración explícita, preserva como respaldo el número registrado en los documentos oficiales de Texeira Travel (`51953767860`).

---

## 3. Pruebas Locales Previas (100 % Aprobadas)

- `tests/test_advisor_phone_config.py`: **7/7 PASS** (prueba de valores por defecto, custom env, normalización de 9 dígitos, limpieza de caracteres, modo deshabilitado y respuestas multilingües).
- `tests/test_core_tours_responses.py`: **9/9 PASS** (catálogo core de 8 tours).
- `tests/test_faq_acclimatization_payments.py`: **2/2 PASS** (aclimatación y métodos de pago).
- `tests/test_conversational.py`: **36/36 PASS** (navegación y respuestas del bot).
- `tests/run_isolated.py test_portuguese_handoff.py`: **13/13 PASS** (handoff y preservación en portugués).

---

## 4. Verificación en Vivo contra Cloud Run 00053 (`/test-chat`)

- **Script de prueba en vivo:** `tests/verify_live_chat_suite_00053.py`.
- **Resultados:** **16/16 Aprobados (100.0 %)**.
- **Detalle de casos evaluados:**
  1. `LIVE-01` [Navegación] Entrada `'Hola'`: **PASS** (1.81s) — Bienvenida limpia sin teléfonos ni fotos no solicitadas.
  2. `LIVE-02` [Navegación] Entrada `'qué tours tienen'`: **PASS** (3.64s) — Catálogo categorizado y CTA al asesor.
  3. `LIVE-03` [Ficha Técnica] Entrada `'Información de Camino Inca'`: **PASS** (2.96s) — Duración 4D/3N y tarifa 790 USD.
  4. `LIVE-04` [Catálogo / Ausencia] Entrada `'Información de Choquequirao'`: **PASS** (3.21s) — Clarificación honesta de tour inactivo.
  5. `LIVE-05` [Recomendaciones] Entrada `'¿Qué tours me recomiendas?'`: **PASS** (1.86s) — Indagación de preferencias y tiempos.
  6. `LIVE-06` [Recomendaciones] Entrada `'Recomiéndame un tour de 4 días'`: **PASS** (3.17s) — Filtro estricto: Camino Inca e Inka Jungle.
  7. `LIVE-07` [Recomendaciones] Entrada `'Recomiéndame un tour de medio día sin caminatas'`: **PASS** (3.76s) — Filtro estricto: City Tour y Maras Moray.
  8. `LIVE-08` [Recomendaciones] Entrada `'Recomiéndame un tour de 2 días'`: **PASS** (3.19s) — Respuesta honesta por inexistencia de opción de 2 días activa.
  9. `LIVE-09` [Multilingüismo EN] Entrada `'How much is the Inca Trail?'`: **PASS** (3.75s) — Tarifa oficial 790 USD en inglés.
  10. `LIVE-10` [Multilingüismo PT] Entrada `'Quais passeios você recomenda?'`: **PASS** (1.91s) — Recomendación en portugués.
  11. `LIVE-11` [Multilingüismo FR] Entrada `'Quels circuits recommandez-vous?'`: **PASS** (6.84s) — Recomendación en francés.
  12. `LIVE-12` [Multilingüismo IT] Entrada `'Quali tour consigliate?'`: **PASS** (1.89s) — Recomendación en italiano.
  13. `LIVE-13` [Robustez Lingüística] Entrada `'ninguno necesito que em recomiendes'`: **PASS** (1.84s) — Mantenido en español sin colisión con PT.
  14. `LIVE-14` [Atención Humana] Entrada `'quiero hablar con un asesor'`: **PASS** (2.65s) — Ticket registrado + enlace configurable.
  15. `LIVE-15` [FAQ Especializada] Entrada `'primer dia en cusco que me recomiendas aclimatacion'`: **PASS** (1.89s) — Recomendación de tours suaves y advertencia sobre alta montaña.
  16. `LIVE-16` [FAQ Especializada] Entrada `'cuáles son sus métodos de pago'`: **PASS** (3.16s) — Cuentas bancarias BCP/Interbank, tarjetas y oficina presencial.

- Reporte JSON de métricas: `docs/evaluaciones/EVALUACION_LIVE_CHAT_00053_20261012T233936Z.json`.

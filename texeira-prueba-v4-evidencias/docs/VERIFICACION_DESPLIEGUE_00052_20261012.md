# Verificación de Despliegue en Producción — Revisión 00052 (12/10/2026)

## 1. Resumen del Despliegue y GitOps

- **Rama de integración:** `main` (respaldada en `origin/main`).
- **Commits asociados:**
  - `2fe11d8`: `feat: completar catalogo core de 8 tours, faq aclimatacion/pagos y enlace de whatsapp en handoff`
- **Revisión en Cloud Run:** `texeira-whatsapp-00052-brv`.
- **URL canónica del servicio:** `https://texeira-whatsapp-1038134693816.us-central1.run.app`.
- **Tráfico:** 100 % servido por la revisión `00052`.
- **Política de costos:** `min-instances = 0` (escala a cero, Costo $0.00 en reposo).
- **Recursos del contenedor:** 2Gi RAM, `--cpu-boost` habilitado.

---

## 2. Nuevas Capacidades y Mejoras Desplegadas

1. **Catálogo Core de 8 Tours Oficiales Sincronizado**:
   - `city-tour-cusco` (30 USD, Medio día 13:30 - 18:30)
   - `valle-sagrado` (35 USD, Full day 08:00 - 18:30)
   - `montana-7-colores` (30 USD, Full day 04:30 - 17:00)
   - `laguna-humantay` (30 USD, Full day 04:30 - 18:00)
   - `machu-picchu-tren` (290 USD, Full day 03:40 - 20:30)
   - `camino-inka` (790 USD, 4D/3N 04:30 - 18:30)
   - `inka-jungle` (290 USD, 4D/3N 05:30 - 18:00)
   - `maras-moray` (30 USD, Medio día 08:40 - 14:00)

2. **Atención y Handoff con Enlace Directo**:
   - Al generarse una solicitud de atención humana o reserva (`route: human_request`), el bot proporciona tanto el ticket persistente como el enlace directo al asesor por WhatsApp (`https://wa.me/51953767860`).

3. **FAQs Especializadas de Cusco**:
   - **Aclimatación y Soroche / Primer Día**: Asesoramiento preventivo sugiriendo tours suaves (City Tour o Maras Moray) y advirtiendo explícitamente evitar excursiones de alta montaña (Laguna Humantay o Montaña de 7 Colores) el primer día.
   - **Métodos de Pago Oficiales**: Especificación clara de transferencias BCP e Interbank (USD/PEN), tarjetas Visa/Mastercard y pago presencial en efectivo en la oficina oficial en Cusco (Calle Carmen Quicllu N.° 250).

---

## 3. Pruebas Locales Previas (100 % Aprobadas)

- `tests/test_core_tours_responses.py`: **9/9 PASS** (información, tarifas e inclusiones de los 8 tours oficiales).
- `tests/test_faq_acclimatization_payments.py`: **2/2 PASS** (cobertura multilingüe de aclimatación y métodos de pago).
- `tests/test_conversational.py`: **36/36 PASS** (navegación social, listados, CTAs de asesor, ausencia de disclaimers invasivos).

---

## 4. Verificación en Vivo contra Cloud Run 00052 (`/test-chat`)

- **Script de prueba en vivo:** `tests/verify_live_chat_suite_00052.py`.
- **Resultados:** **16/16 Aprobados (100.0 %)**.
- **Detalle de casos evaluados:**
  1. `LIVE-01` [Navegación] Entrada `'Hola'`: **PASS** (1.61s) — Bienvenida limpia sin teléfonos ni fotos no solicitadas.
  2. `LIVE-02` [Navegación] Entrada `'qué tours tienen'`: **PASS** (3.67s) — Catálogo categorizado y CTA al asesor.
  3. `LIVE-03` [Ficha Técnica] Entrada `'Información de Camino Inca'`: **PASS** (2.97s) — Duración 4D/3N y tarifa 790 USD.
  4. `LIVE-04` [Catálogo / Ausencia] Entrada `'Información de Choquequirao'`: **PASS** (3.43s) — Clarificación honesta de tour inactivo.
  5. `LIVE-05` [Recomendaciones] Entrada `'¿Qué tours me recomiendas?'`: **PASS** (1.84s) — Indagación de preferencias y tiempos.
  6. `LIVE-06` [Recomendaciones] Entrada `'Recomiéndame un tour de 4 días'`: **PASS** (3.21s) — Filtro estricto: Camino Inca e Inka Jungle.
  7. `LIVE-07` [Recomendaciones] Entrada `'Recomiéndame un tour de medio día sin caminatas'`: **PASS** (4.04s) — Filtro estricto: City Tour y Maras Moray.
  8. `LIVE-08` [Recomendaciones] Entrada `'Recomiéndame un tour de 2 días'`: **PASS** (3.15s) — Respuesta honesta por inexistencia de opción de 2 días activa.
  9. `LIVE-09` [Multilingüismo EN] Entrada `'How much is the Inca Trail?'`: **PASS** (3.89s) — Tarifa oficial 790 USD en inglés.
  10. `LIVE-10` [Multilingüismo PT] Entrada `'Quais passeios você recomenda?'`: **PASS** (1.85s) — Recomendación en portugués.
  11. `LIVE-11` [Multilingüismo FR] Entrada `'Quels circuits recommandez-vous?'`: **PASS** (7.81s) — Recomendación en francés.
  12. `LIVE-12` [Multilingüismo IT] Entrada `'Quali tour consigliate?'`: **PASS** (1.83s) — Recomendación en italiano.
  13. `LIVE-13` [Robustez Lingüística] Entrada `'ninguno necesito que em recomiendes'`: **PASS** (1.94s) — Mantenido en español sin falsos positivos.
  14. `LIVE-14` [Atención Humana] Entrada `'quiero hablar con un asesor'`: **PASS** (2.52s) — Ticket registrado + enlace `wa.me/51953767860`.
  15. `LIVE-15` [FAQ Especializada] Entrada `'primer dia en cusco que me recomiendas aclimatacion'`: **PASS** (1.83s) — Recomendación de tours suaves y advertencia sobre alta montaña.
  16. `LIVE-16` [FAQ Especializada] Entrada `'cuáles son sus métodos de pago'`: **PASS** (3.22s) — Cuentas bancarias BCP/Interbank, tarjetas y oficina presencial.

---

## 5. Persistencia y Limpieza en Neon PostgreSQL

- Tablas validadas en producción: `interactions`, `conversation_memory`, `requests`.
- Registros sintéticos creados: 17 interacciones, 17 memorias conversacionales, 1 ticket de soporte.
- Limpieza automática posterior: **100 % de datos sintéticos eliminados** sin dejar residuos en producción.
- Reporte JSON persistido en: `docs/evaluaciones/EVALUACION_LIVE_CHAT_00052_20261012T153131Z.json`.

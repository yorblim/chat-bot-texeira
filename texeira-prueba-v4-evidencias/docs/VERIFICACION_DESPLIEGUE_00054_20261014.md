# Verificación de Despliegue en Producción — Revisión 00054 (14/10/2026)

## 1. Resumen del Despliegue y GitOps

- **Rama de integración:** `main` (respaldada en `origin/main`).
- **Commit asociado:**
  - `fba8efd`: `feat: incorporar gestion de disponibilidad, cupos y tours agotados en catalogo y bot`
- **Revisión activa en Cloud Run:** `texeira-whatsapp-00054-dxd`.
- **URL canónica del servicio:** `https://texeira-whatsapp-1038134693816.us-central1.run.app`.
- **Tráfico:** 100 % servido por la revisión `00054`.
- **Política de costos:** `min-instances = 0` (escala a cero, Costo $0.00 en reposo).
- **Recursos del contenedor:** 2Gi RAM, `--cpu-boost` habilitado.

---

## 2. Nuevas Capacidades Implementadas: Paso 1 y Paso 2

### Paso 1: Reglas Conversacionales y FAQs Especializadas de Disponibilidad y Cupos
1. **FAQ de Cierre de Camino Inca en Febrero**:
   - Informa con exactitud y empatía que el Camino Inca 4D/3N permanece cerrado todo febrero por mantenimiento y conservación según disposición gubernamental (SERNANP).
   - Sugiere automáticamente alternativas activas como **Inka Jungle 4D/3N** o caminatas alternas y canaliza con un asesor.
2. **FAQ de Regulación y Cupos Oficiales (500 personas/día)**:
   - Explica con transparencia que los cupos de Camino Inca están limitados por ley a 500 personas diarias (incluyendo guías y porteadores).
   - Recomienda reservar con 3 a 6 meses de anticipación y no inventa disponibilidad en tiempo real.
3. **Disponibilidad de Tours Diarios**:
   - Clarifica que tours como City Tour, Laguna Humantay, Montaña de 7 Colores, Valle Sagrado y Maras Moray cuentan con salidas diarias regulares garantizadas con 24 a 48 horas de anticipación.
4. **Machu Picchu y Trenes**:
   - Orienta sobre la compra escalonada de turnos del Ministerio de Cultura y boletos de tren según disponibilidad horaria.

### Paso 2: Modelo de Datos y Gestión en Panel Administrativo (`/catalogo`)
1. **Persistencia de Disponibilidad en Catálogo**:
   - Nuevo campo `availability` en SQLite y Neon PostgreSQL con valores:
     - `available`: 🟢 Disponible (Salidas regulares garantizadas)
     - `limited`: 🟡 Cupos limitados (Alta demanda / Confirmar con asesor)
     - `sold_out`: 🔴 Agotado temporalmente (Cupos completos para la temporada/fecha)
2. **Interfaz de Gestión y Badges Visuales**:
   - Selector en el modal de edición/creación del panel web `/catalogo`.
   - Etiquetas visuales (`badge-available`, `badge-limited`, `badge-sold-out`) en la tabla de administración.
3. **Reflejo en Fichas Técnicas y Listados**:
   - Los listados por categoría marcan claramente `[🔴 Agotado]` o `[🟡 Cupos limitados]`.
   - Las fichas individuales detallan el estado de disponibilidad actual.
4. **Handoff Especializado para Tours Agotados**:
   - Si un turista intenta reservar un tour marcado como agotado, el bot lo aclara amablemente, abre un ticket con prefijo `[Reserva - AGOTADO - Tour]` y pasa el caso al asesor para evaluar lista de espera o fechas alternativas.

---

## 3. Pruebas Locales Previas (100 % Aprobadas)

- `tests/test_tour_availability_and_sold_out.py`: **11/11 PASS** (CRUD disponibilidad, badges UI, intents conversacionales, tours agotados y limitados).
- `tests/test_faq_acclimatization_payments.py`: **2/2 PASS** (aclimatación y pagos).
- `tests/test_advisor_phone_config.py`: **7/7 PASS** (contacto y enlace de asesor).
- `tests/run_isolated.py test_catalog_connected_flow.py`: **12/12 PASS** (flujo conectado del catálogo).
- `tests/test_conversational.py`: **36/36 PASS** (navegación y routing del bot).
- `tests/test_calidad_whatsapp.py`: **13/13 PASS** (regresión de calidad WhatsApp).

---

## 4. Verificación en Vivo contra Cloud Run 00054 (`/test-chat`)

- **Script de prueba en vivo:** `tests/verify_live_chat_suite_00054.py`.
- **Resultados:** **20/20 Aprobados (100.0 %)** | **0 fallos**.
- **Detalle de casos evaluados:**
  1. `LIVE-01` [Navegación] Entrada `'Hola'`: **PASS** (1.53s) — Bienvenida limpia sin teléfonos ni fotos no solicitadas.
  2. `LIVE-02` [Navegación] Entrada `'qué tours tienen'`: **PASS** (3.77s) — Catálogo categorizado y tours activos.
  3. `LIVE-03` [Ficha Técnica] Entrada `'Información de Camino Inca'`: **PASS** (2.83s) — Duración 4D/3N, tarifa 790 USD y nota de cupos.
  4. `LIVE-04` [Catálogo / Ausencia] Entrada `'Información de Choquequirao'`: **PASS** (2.99s) — Manejo honesto de tour no activo.
  5. `LIVE-05` [Recomendaciones] Entrada `'¿Qué tours me recomiendas?'`: **PASS** (2.06s) — Indagación de preferencias y tiempos.
  6. `LIVE-06` [Recomendaciones] Entrada `'Recomiéndame un tour de 4 días'`: **PASS** (3.05s) — Filtro estricto: Camino Inca e Inka Jungle.
  7. `LIVE-07` [Recomendaciones] Entrada `'Recomiéndame un tour de medio día sin caminatas'`: **PASS** (3.05s) — Filtro estricto: City Tour y Maras Moray.
  8. `LIVE-08` [Recomendaciones] Entrada `'Recomiéndame un tour de 2 días'`: **PASS** (3.10s) — Respuesta honesta sin inventar tours de 2 días.
  9. `LIVE-09` [Multilingüismo EN] Entrada `'How much is the Inca Trail?'`: **PASS** (3.52s) — Tarifa oficial 790 USD en inglés.
  10. `LIVE-10` [Multilingüismo PT] Entrada `'Quais passeios você recomenda?'`: **PASS** (1.76s) — Recomendación en portugués.
  11. `LIVE-11` [Multilingüismo FR] Entrada `'Quels circuits recommandez-vous?'`: **PASS** (7.32s) — Recomendación en francés.
  12. `LIVE-12` [Multilingüismo IT] Entrada `'Quali tour consigliate?'`: **PASS** (2.01s) — Recomendación en italiano.
  13. `LIVE-13` [Robustez Lingüística] Entrada `'ninguno necesito que em recomiendes'`: **PASS** (2.00s) — Mantenido en español sin falsos positivos de portugués.
  14. `LIVE-14` [Atención Humana] Entrada `'quiero hablar con un asesor'`: **PASS** (2.39s) — Ticket registrado + enlace WhatsApp configurable.
  15. `LIVE-15` [FAQ Especializada] Entrada `'primer dia en cusco que me recomiendas aclimatacion'`: **PASS** (1.77s) — Tours suaves y prevención de soroche.
  16. `LIVE-16` [FAQ Especializada] Entrada `'cuáles son sus métodos de pago'`: **PASS** (2.68s) — Transferencias bancarias, tarjetas y oficina presencial.
  17. `LIVE-17` [Disponibilidad / Febrero] Entrada `'¿Tienen disponibilidad para el Camino Inca en febrero?'`: **PASS** (3.18s) — Notificación de cierre por mantenimiento en febrero + alternativas como Inka Jungle.
  18. `LIVE-18` [Disponibilidad / Cupos] Entrada `'¿Cuántos cupos hay para el Camino Inca?'`: **PASS** (2.94s) — Explicación oficial de 500 cupos/día regulados por SERNANP.
  19. `LIVE-19` [Disponibilidad / Tours Diarios] Entrada `'¿Tienen cupos para el tour del Valle Sagrado?'`: **PASS** (2.92s) — Salidas diarias garantizadas con 24-48h de anticipación.
  20. `LIVE-20` [Disponibilidad / General] Entrada `'¿Tienen disponibilidad de tours?'`: **PASS** (2.41s) — Resumen estructurado: tours diarios vs cupos estatales/trenes.

- **Persistencia y Limpieza:** 23 interacciones y tickets sintéticos creados y eliminados al 100 % de Neon PostgreSQL.
- **Reporte JSON:** Generado en `docs/evaluaciones/EVALUACION_LIVE_CHAT_00054_*.json`.

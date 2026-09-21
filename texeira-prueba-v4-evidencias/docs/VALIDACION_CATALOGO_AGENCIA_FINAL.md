# Informe de Validación y Auditoría Final del Catálogo — Texeira Travel Tour

**Fecha:** 2026-09-21  
**Fuentes Canónicas:**
- **F1:** Folleto físico impreso oficial (Texeira Travel Tour) — Fuente Primaria de Horarios e Inclusiones.
- **F2:** Catálogo digital en PDF — Fuente Primaria de Itinerarios y Productos Documentados.
- **F3:** Publicaciones y fichas promocionales en Facebook — Fuente Secundaria / Complementaria.

---

## 1. Datos Institucionales y de Contacto Confirmados

| Campo | Valor Canónico en el Bot | Fuente de Respaldo | Estado |
| :--- | :--- | :---: | :---: |
| **Razón Social** | TEXEIRA TRAVEL — TRAVEL AGENCY E.I.R.L. | F1 / F2 | **Confirmado ✅** |
| **Teléfono Principal** | +51 953 767 860 | F1 / F2 | **Confirmado ✅** |
| **Teléfono Secundario** | +51 984 679 715 | F1 / F2 | **Confirmado ✅** |
| **Correos Electrónicos** | `texeiratraveltour@hotmail.com` / `eugeniotejeira@hotmail.com` | F1 / F2 | **Confirmado ✅** |
| **Dirección de Oficina** | Calle Carmen Quicllu N.° 250, Centro Histórico de Cusco, Perú | F2 (pág. 1) | **Confirmado ✅** |

---

## 2. Resolución Oficial de Conflictos de Horario

En cumplimiento de las reuniones de validación y la ficha técnica de la agencia ([FICHA_VALIDACION_AGENCIA.md](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/FICHA_VALIDACION_AGENCIA.md)), se ratifica que los horarios vigentes corresponden exclusivamente al **folleto físico impreso F1**:

1. **City Tour Cusco:**
   - **Horario Oficial Vigente (F1):** Mañana: 10:00 – 14:00 \| Tarde: 13:30 – 18:30 ✅
   - *Dato Descartado (F3):* 09:00 – 14:00 / 13:30 – 18:00 ❌
2. **Valle Sagrado Completo:**
   - **Horario Oficial Vigente (F1):** Salida: 07:30 \| Retorno: 18:30 ✅
   - *Dato Descartado (F3):* 07:00 – 18:30 ❌
3. **Montaña de 7 Colores (Vinicunca):**
   - **Horario Oficial Vigente (F1):** Salida: 04:30 \| Retorno: 17:00 (5:00 pm) ✅
   - *Dato Descartado (F3):* 05:00 – 16:30 ❌

---

## 3. Catálogo de los 19 Tours Canónicos Documentados

Todos los productos registrados en `data/tours_catalog.json` cuentan con respaldo documental explícito:

| N.° | Identificador (`entity_id`) | Nombre Oficial del Tour | Estado del Producto | Horario |
| :---: | :--- | :--- | :---: | :---: |
| 1 | `city-tour-cusco` | City Tour Cusco | Confirmado | F1 (10:00–14:00 / 13:30–18:30) |
| 2 | `valle-sagrado` | Valle Sagrado Completo | Confirmado | F1 (07:30–18:30) |
| 3 | `valle-sur` | Valle Sur (Tipón, Pikillacta, Andahuaylillas) | Confirmado | F1 Confirmado |
| 4 | `montana-7-colores` | Montaña de 7 Colores (Vinicunca) | Confirmado | F1 (04:30–17:00) |
| 5 | `laguna-humantay` | Laguna Humantay | Confirmado | F1 Confirmado |
| 6 | `waqra-pukara` | Waqra Pukara | Confirmado | Consultar agencia |
| 7 | `machu-picchu-car` | Machu Picchu by Car | Confirmado | Terrestre / Consultar |
| 8 | `machu-picchu-tren` | Machu Picchu en Tren | Confirmado | Férreo / Consultar |
| 9 | `camino-inka` | Camino Inka | Confirmado | Consultar agencia |
| 10 | `salkantay-trek` | Salkantay Trek (4 Días) | Confirmado | F2 (4 días) |
| 11 | `inka-jungle` | Inka Jungle to Machu Picchu (4 Días) | Confirmado | F2 (4 días) |
| 12 | `choquequirao` | Choquequirao Trek | Confirmado | Consultar agencia |
| 13 | `tour-mistico` | Tour Místico | Confirmado | Consultar agencia |
| 14 | `islas-titicaca` | Islas del Lago Titicaca (Uros, Taquile, Amantaní)| Confirmado | Consultar agencia |
| 15 | `canon-colca` | Cañón del Colca / Baños Termales de Chacapi | Confirmado | Consultar agencia |
| 16 | `ruta-del-sol` | Ruta del Sol Cusco-Puno | Confirmado | F2 Confirmado |
| 17 | `maras-moray` | Maras - Moray (Tradicional en Bus) | Confirmado | F1 Confirmado |
| 18 | `maras-moray-cuatrimoto` | Tour Cuatrimoto Maras - Moray | Confirmado | F3 Confirmado |
| 19 | `puente-qeswachaca` | Puente de Q'eswachaca | Confirmado | Consultar agencia |

---

## 4. Políticas Comerciales Protegidas (Cero Alucinaciones)

Para garantizar rigor académico y evitar reclamaciones de clientes, aquellas condiciones comerciales no publicadas formalmente en los folletos se definen en el sistema con estado `unknown`:

- **Métodos de pago y recargos:** No documentados. El bot informa honestamente que deben coordinarse con el asesor.
- **Porcentajes de adelanto o depósito:** No documentados. No se promete ningún porcentaje arbitrario (ej. 30% o 50%).
- **Políticas de cancelación y reembolso:** No documentadas. El bot no asume penalidades inventadas ni devoluciones garantizadas.
- **Descuentos especiales (estudiantes / niños):** Requieren confirmación directa del personal de la agencia.

---

## 5. Certificación Técnica

La suite de validación [tests/test_catalog_validation.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_catalog_validation.py) certifica el 100% de cumplimiento de las reglas estructurales y de consistencia del catálogo canónico.

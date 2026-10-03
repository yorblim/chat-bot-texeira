# Resolución Técnica: Estado de Envío Post-Despacho, Canal Sintético y Restricción de Fallback

**Fecha:** 2026-10-03  
**Autor:** Antigravity (Pair Programming con Desarrollador)  
**Referencia del Encargo:** [`VERIFICACION_00042_20261003.md`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/docs/VERIFICACION_00042_20261003.md)  
**Componentes Modificados:** [`app.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/app.py), [`src/services/whatsapp.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/src/services/whatsapp.py), [`operational_metrics.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/operational_metrics.py)

---

## 1. Resumen Ejecutivo

En la verificación independiente de la revisión `00042-9w4`, se identificaron 4 observaciones en el webhook y panel operativo:
1. **Preservación del estado tras el envío (P1):** Si ocurría una excepción en operaciones auxiliares (como el registro de métricas operativas) posterior al despacho de WhatsApp, el bloque general de captura marcaba el recibo en la base de datos como `failed`, permitiendo que la reentrega de Meta volviese a enviar el mensaje (duplicando mensajes aceptados o inciertos).
2. **Canal sintético de pruebas (P2):** Solicitudes entrantes en `/webhook` con canal `test` causaban `UnboundLocalError` (HTTP 503) por falta de inicialización previa de `send_status`.
3. **Filtro de fallback interactivo demasiado permisivo (P2):** `is_interactive_format_error` admitía cadenas genéricas como `"param"` o `"parameter"`, provocando que un error de destinatario (ej. `Parameter to is not a valid WhatsApp number`) disparara incorrectamente el fallback a texto plano en lugar de ser rechazado.
4. **Visibilidad de envíos inciertos en el panel (P2):** La métrica `send_uncertain` era computada en el backend pero no se renderizaba en la tabla de tráfico del panel administrativo.

Los 4 puntos han sido corregidos de forma integral sin debilitar ninguna aserción existente, alcanzando el 100% de éxito en las 4 nuevas pruebas de regresión y en toda la suite de pruebas del proyecto.

---

## 2. Detalle de Correcciones Implementadas

### 2.1. Inmutabilidad y Finalización Temprana del Recibo (`app.py`)
- **Compromiso inmediato del recibo:** Tras recibir la respuesta del transporte de WhatsApp (`send_whatsapp_message`), se ejecuta inmediatamente `database.finish_webhook(m_id, u_owner, send_status)` y se establece la bandera `receipt_finished = True`.
- **Aislamiento de métricas auxiliares:** La llamada a `operational.finish(...)` se protegió dentro de un bloque `try...except`, impidiendo que fallos de métricas o de latencia interrumpan el ciclo del webhook.
- **Protección en la captura general de excepciones:** En el bloque `except Exception as e:`, si el recibo aún no se había finalizado pero el estado del transporte ya era `"accepted"` o `"uncertain"`, dicho estado legítimo se preserva estrictamente y **no se degrada a `"failed"`**.
- **Comportamiento ante reentregas:** Un mensaje `accepted` se deduce y responde con HTTP 200 sin reenviar; un mensaje `uncertain` se retiene para conciliación sin duplicar envíos.

### 2.2. Restauración del Canal Sintético `test` (`app.py`)
- Se preinicializa `send_status = "accepted" if u_chan == "test" else "rejected"` al inicio del procesamiento de cada elemento.
- En la rama `u_chan == "test"`, se omite el despacho externo hacia Meta/Facebook, se finaliza el recibo local y se devuelve HTTP 200 con `{"status": "ok", "message_id": ...}`.

### 2.3. Restricción del Fallback Interactivo (`src/services/whatsapp.py`)
- Se agregaron patrones específicos de exclusión en `non_format_patterns`:
  - `"not a valid whatsapp"`, `"not a valid number"`, `"invalid phone"`, `"parameter to"`, `"param to"`, `"field to"`, `"recipient"`, `"131026"`.
- Se eliminaron del listado de formato interactivo las palabras genéricas y ambiguas (`"param"`, `"parameter"`, `"format"`).
- Errores de destinatario devuelven ahora `False` en `is_interactive_format_error`, evitando el fallback innecesario a texto.

### 2.4. Visualización en Panel de Métricas Operativas (`operational_metrics.py`)
- Se agregó a la tabla `rows-traffic` la fila:
  `['Envíos con resultado incierto (retenidos para revisión)', fmtVal(d.send_uncertain)]`
- Informa claramente los casos retenidos sin sumarlos indebidamente como entregados ni ocultarlos del monitoreo.

---

## 3. Matriz de Resultados de Pruebas Locales (Red Externa Aislada)

Ejecutadas con `python tests/run_isolated.py <suite>` garantizando ambiente estéril y SQLite temporal:

| Suite de Pruebas | Casos Ejecutados | Resultado | Observaciones |
| :--- | :---: | :---: | :--- |
| `test_review_send_state_9f3ac70.py` | 4 | **4 PASS / 0 FAIL** | Las 4 regresiones nuevas pasan al 100% |
| `test_review_webhook_2a6d01d.py` | 2 | **2 PASS / 0 FAIL** | Enrutamiento de lotes multi-remitente y no duplicación de inciertos |
| `test_review_anti_echo_20261002.py` | 13 | **13 PASS / 0 FAIL** | Anti-eco, deduplicación de reentregas, manejo de eventos de sistema |
| `test_webhook_recovery.py` | 6 | **6 PASS / 0 FAIL** | Resiliencia ante fallos transitorios |
| `test_interactive_whatsapp_buttons.py` | 11 | **11 PASS / 0 FAIL** | Truncamiento seguro, botones rápidos y fallback |
| `test_operational_metrics.py` | 1 | **PASS** | Métricas operativas sin llamadas externas |
| `test_dedup.py` | 23 | **23 PASS / 0 FAIL** | Deduplicación concurrente y persistencia |
| `test_conversational.py` | 36 | **36 PASS / 0 FAIL** | RAG, intención conversacional y catálogo |
| **Total General** | **96** | **96 PASS / 0 FAIL (100%)** | **Sin regresiones** |

---

## 4. Estado de Cumplimiento de Reglas de Proyecto (AGENTS.md)

1. ✅ **Desarrollo y Prueba Local:** Modificaciones realizadas en `texeira-prueba-v4-evidencias/` y validadas con 96 pruebas locales al 100%.
2. 🔄 **Flujo de Ramas y Registro en Git:** Preparado en rama `feature/fix-post-dispatch-and-recipient-fallback`, commit semántico `fix: ...`, merge a `main` y push a GitHub.
3. 🔄 **Despliegue a Google Cloud Run:** Siguiendo `actualizar_nube.bat` manteniendo costo $0.00 (`min-instances = 0`, escala a cero).
4. 🔄 **Verificación en Vivo:** Comprobación de `/health` (HTTP 200) y endpoint operativo en producción.

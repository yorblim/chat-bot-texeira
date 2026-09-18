# Informe antes/después de correcciones (C06–C09)

Fecha: 11 de septiembre de 2026
Evidencia antes: evaluation-ten-live-20260911-111304.json
Evidencia después: Pruebas en vivo con servidor reiniciado (puerto 8020)

## Resumen de correcciones

Se corrigieron 4 fallos en los indicadores de `resolved_autonomously`, `escalated_to_human` y `needs_agency_confirmation`. Los cambios se aplicaron en `app.py` (needs_escalation, rag_chain) y `trial_support.py` (ruta determinista).

## Comparación por caso

### C06: "¿El paquete de 7 días es una oferta confirmada?"

| Indicador | Antes | Después | Cambio |
|-----------|-------|---------|--------|
| `resolved_autonomously` | true | true | Sin cambio |
| `escalated_to_human` | **true** | **false** | Corregido |
| `needs_agency_confirmation` | false | false | Sin cambio |

**Problema original**: `escalated_to_human=true` aunque la respuesta niega explícitamente que un asesor contactará automáticamente. La función `needs_escalation` detectaba "un asesor" como indicador de transferencia efectiva.

**Corrección**: Eliminado "contacta a" de `escalation_indicators`. Ahora solo detecta transferencia ejecutada (frases como "Un asesor se pondrá en contacto contigo"), no orientación.

**Contenido de respuesta**: Correcto en ambos casos. El paquete 7D/6N se identifica como hipotético y se orienta al contacto de la agencia.

---

### C07: "¿Puedo pagar con Yape y cuánto debo adelantar?"

| Indicador | Antes | Después | Cambio |
|-----------|-------|---------|--------|
| `resolved_autonomously` | **true** | **false** | Corregido |
| `escalated_to_human` | false | false | Sin cambio |
| `needs_agency_confirmation` | **false** | **true** | Corregido |

**Problema original**: `resolved_autonomously=true` indicaba que la consulta estaba resuelta, pero la condición comercial (métodos de pago y adelanto) queda pendiente de confirmación con la agencia.

**Corrección**: Añadida detección de palabras clave en `rag_chain` ("yape", "adelanto", "pago", "pagar", etc.). Cuando la consulta incluye estos términos, se marca `needs_agency_confirmation=true` y `resolved_autonomously=false`.

**Contenido de respuesta**: Correcto. Indica que no hay información confirmada sobre métodos de pago y orienta a consultar con la agencia.

---

### C08: "¿Hay dos cupos para Machu Picchu mañana?"

| Indicador | Antes | Después | Cambio |
|-----------|-------|---------|--------|
| `resolved_autonomously` | **true** | **false** | Corregido |
| `escalated_to_human` | false | false | Sin cambio |
| `needs_agency_confirmation` | **false** | **true** | Corregido |

**Problema original**: `resolved_autonomously=true` indicaba resolución, pero la disponibilidad es una condición comercial que requiere verificación con la agencia. Además, la respuesta original ofrecía "enlaces de las fuentes de precios" como vía de contacto, confundiendo fuentes externas con contacto de Texeira.

**Corrección**: Añadida detección de palabras clave ("cupo", "cupos", "disponibilidad", "reserva", "reservar", "availability", "reservation", "book"). Post-procesamiento para reemplazar "fuentes de precios" con contacto publicado de la agencia.

**Contenido de respuesta**: Corregido. Ahora orienta directamente al contacto de la agencia sin mencionar fuentes externas como canal de contacto.

---

### C09: "¿Cuánto es exactamente en soles el tour Salkantay?"

| Indicador | Antes | Después | Cambio |
|-----------|-------|---------|--------|
| `resolved_autonomously` | **true** | **false** | Corregido |
| `escalated_to_human` | false | false | Sin cambio |
| `needs_agency_confirmation` | **false** | **true** | Corregido |

**Problema original**: `resolved_autonomously=true` indicaba resolución, pero el precio exacto en soles requiere cotización y tipo de cambio confirmado por la agencia. Además, la respuesta original exponía "Prohibición de conversiones" como regla interna.

**Corrección**: Añadida detección de "soles", "pen", "tipo de cambio", "conversión", "conversion", "exchange rate". Post-procesamiento para reemplazar "Prohibición de conversiones" por "Tipo de cambio no confirmado".

**Contenido de respuesta**: Corregido. Ahora explica que no hay tipo de cambio confirmado, no que exista una prohibición.

---

## Resultados de pruebas

### Prueba de integración (test_trial.py)
- Estado: OK
- Sin regresiones en funcionalidad existente

### Prueba de 4 fallos (test_four_fallos.py)
- Estado: OK
- Todos los indicadores verificados

### Evaluación 10 casos (evaluate_ten.py local)
- Estado: OK
- 4 deterministas + 6 con LLM simulado
- Indicadores correctos en todos los casos

### Prueba en vivo (servidor reiniciado)
- Estado: OK
- C06: `escalation=False` ✓
- C07: `resolved=False, needs_confirm=True` ✓
- C08: `resolved=False, needs_confirm=True` ✓
- C09: `resolved=False, needs_confirm=True` ✓

## Limitaciones

1. **Post-procesamiento depende de keywords**: Si el LLM genera una respuesta sin las palabras clave detectadas, los indicadores no se activarán. Esto es una limitación de la detección por reglas.

2. **No hay derivación real**: El sistema no tiene mecanismo efectivo de asignación a asesores. `escalated_to_human` solo indica que la respuesta sugiere contactar a la agencia, no que se ejecutó una transferencia.

3. **Contenido generado por LLM**: Las respuestas del LLM pueden variar. El post-processing solo corrige problemas específicos detectables por patrones de texto.

4. **Precios y condiciones son simulados**: No son tarifas oficiales de Texeira. Requieren validación con la agencia (fase 6).

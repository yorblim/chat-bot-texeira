# Revisión final del commit a1b9c60

Fecha: 04/10/2026. Alcance: calificador de evaluación, artefactos recalificados y documentación. No se ejecutaron APIs reales, mensajes WhatsApp ni despliegues.

## Resultado

Los pendientes anteriores están corregidos: los tres controles negativos ahora se rechazan, los tres controles positivos originales se aprueban, los metadatos originales se preservan y el informe acota sus conclusiones al banco histórico.

Queda una regresión concreta del evaluador: la nueva detección de negación para Choquequirao todavía considera todo el texto. Una condición no documentada sobre el precio se interpreta como si negara la existencia documentada del producto.

## Pruebas independientes ejecutadas

Todas las ejecuciones usaron `tests/run_isolated.py`, con red externa bloqueada y estado temporal.

| Suite | Resultado | Log en logs/ |
| --- | --- | --- |
| test_review_grader_polarity_20261004.py | 7/7 PASS | review_a1b9c60_polarity.log |
| test_review_recalibration_8d4823e.py | 3/3 PASS; incluye 13 consultas con mock | review_a1b9c60_recalibration_quality.log |
| test_review_evaluation_grader_20261004.py | 3/3 PASS | review_a1b9c60_original_grader.log |
| test_whatsapp_flow_polish.py | 13/13 PASS | review_a1b9c60_flow.log |
| test_review_product_confirmation_a1b9c60.py | 1 PASS / 1 FAIL | review_a1b9c60_product_confirmation.log |

Las cuatro suites informadas por Antigravity suman 26 pruebas y pasan. El control independiente adicional detecta el defecto descrito abajo, manteniendo aprobado el rechazo de una negación real del producto.

## Evidencias confirmadas

- Los 30 casos preservan exactamente rutas, latencias, flags operativos, preguntas y respuestas originales. Cero diferencias de metadatos.
- Los archivos históricos JSON e informe del 21/09 son idénticos byte a byte a los originales del commit 06512b1, comprobados mediante SHA-256.
- La recalificación se reproduce por caso y por motivo: 22/30 aprobados (73,3%); IP 29/30, FF 22/30, CI 30/30 y MI 30/30. Español 12/15 e inglés 10/15.
- El informe retiró 99,8% y 86,7%, explica que 15–30 minutos es un supuesto pendiente de preprueba, distingue flags técnicos de resolución validada y acota el resultado a la revisión 00021-9mp del 21/09.
- El commit inspeccionado es a1b9c60; al comenzar, el árbol estaba limpio y HEAD/main coincidía con la referencia local origin/main.

## Regresión que resta corregir

En `tests/evaluate_thesis_postest.py:204`, `is_negated` busca `not documented` en toda la respuesta, sin asociarlo al hecho de confirmación del producto.

Caso ACAD-EN-04, pregunta sobre si Choquequirao está documentado en los materiales de la agencia:

```text
Choquequirao is a confirmed product documented by Texeira.
The price is not documented; please confirm it with the agency.
```

Resultado actual: IP=1, FF=0, CI=1, MI=1, `passed=0`.

Resultado esperado: `passed=1`. La respuesta confirma el producto requerido y reconoce un precio desconocido sin inventar una tarifa. Negar documentación del precio no equivale a negar documentación del tour.

## Encargo acotado para Antigravity

Asociar la negación a la confirmación/documentación de Choquequirao como producto; una negación sobre precio, disponibilidad u otra condición distinta no debe invalidar esa confirmación. Ejecutar `test_review_product_confirmation_a1b9c60.py` y mantener los siete controles de polaridad existentes. Conservar el rechazo de «Choquequirao is not a confirmed product and is not documented by Texeira».

Recalcular las mismas respuestas guardadas y comprobar metadatos e históricos. Si cambia algún caso, documentar el motivo y actualizar los resultados; no imponer un porcentaje. Aplicar el flujo de rama, pruebas y registro de AGENTS.md al versionar. Esta corrección afecta al evaluador y no necesita llamadas nuevas al LLM ni despliegue del bot.

El 73,3% sigue siendo un resultado automático histórico del instrumento; esta revisión no lo convierte en una medición de precisión actual del bot.

---

## Resolución y Verificación del Ajuste (04/10/2026)

Se corrigió la asociación de la negación en la comprobación de confirmación de producto dentro de `evaluate_case()` (`tests/evaluate_thesis_postest.py:204-222`):

1. **Aislamiento de la Negación al Objeto de Producto:**
   - Se sustituyó la detección global de `not documented` por un patrón sintáctico `is_product_negated` enfocado en la negación de la existencia, confirmación o documentación de Choquequirao / el tour / producto (`not a confirmed product`, `not documented by Texeira`, `choquequirao is not confirmed/documented`, `not documented as a tour/product`).
   - Negaciones sobre atributos comerciales auxiliares (tales como `The price is not documented`, `Su precio no está documentado`, disponibilidad u horarios) ya no invalidan la confirmación canónica del producto.

2. **Resultados de Verificación Independiente en Entorno Aislado:**
   - `test_review_product_confirmation_a1b9c60.py`: **2/2 PASS (OK)**.
     - Aprobado: `Choquequirao is a confirmed product documented by Texeira. The price is not documented; please confirm it with the agency.` (`passed=1`).
     - Rechazado: `Choquequirao is not a confirmed product and is not documented by Texeira.` (`passed=0`).
   - `test_review_grader_polarity_20261004.py`: **7/7 PASS (OK)** (controles de polaridad de boleto turístico, buffet y preservación de metadatos intactos).
   - `test_review_recalibration_8d4823e.py`: **3/3 PASS (OK)** (recalificación idéntica 22/30, SHA-256 de históricos intactos y 13 consultas simuladas con mock).
   - `test_review_evaluation_grader_20261004.py`: **3/3 PASS (OK)**.
   - `test_whatsapp_flow_polish.py`: **13/13 PASS (OK)**.

3. **Total:** 28 pruebas ejecutadas en entorno local aislado, 100% aprobadas. Los artefactos históricos y metadatos permanecen 100% inalterados.


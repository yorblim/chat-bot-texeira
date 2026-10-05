# Verificación independiente de dbe5498

Fecha: 04/10/2026. Alcance: arreglo del evaluador y conservación de evidencia histórica.

## Resultado

Se verificó el commit dbe5498 en main, con referencia local origin/main coincidente y árbol inicialmente limpio. El diff afecta pruebas y documentación, sin modificar el código de la aplicación.

El ejemplo anterior con producto confirmado y `The price is not documented` ya se aprueba. Los controles negativos anteriores siguen rechazados. Las cinco suites informadas se ejecutaron de nuevo y pasan: **28/28 pruebas**.

La afirmación general de que toda negación de precio queda aislada todavía excede el comportamiento del código: una variante que atribuye la ausencia de documentación del precio a Texeira sigue invalidando el producto. Es una limitación del mismo calificador, no un incidente observado en WhatsApp.

## Pruebas ejecutadas sin APIs

Se utilizó `tests/run_isolated.py`, que bloquea conexiones externas y usa datos temporales. La prueba de calidad usó LLM simulado y reportes temporales. No se ejecutó el flujo de posprueba en producción.

| Suite | Resultado | Log en logs/ |
| --- | --- | --- |
| test_review_product_confirmation_a1b9c60.py | 2/2 PASS | review_dbe5498_test_review_product_confirmation_a1b9c60.log |
| test_review_grader_polarity_20261004.py | 7/7 PASS | review_dbe5498_test_review_grader_polarity_20261004.log |
| test_review_recalibration_8d4823e.py | 3/3 PASS; incluye 13 consultas con mock | review_dbe5498_test_review_recalibration_8d4823e.log |
| test_review_evaluation_grader_20261004.py | 3/3 PASS | review_dbe5498_test_review_evaluation_grader_20261004.log |
| test_whatsapp_flow_polish.py | 13/13 PASS | review_dbe5498_test_whatsapp_flow_polish.log |
| test_review_price_scope_dbe5498.py, control independiente añadido | 1 PASS / 1 FAIL | review_dbe5498_price_scope.log |

El SHA-256 de los dos archivos históricos del 21/09 coincide con sus originales. Las 30 respuestas recalificadas conservan metadatos originales, y sus calificaciones y motivos se reproducen exactamente: 22/30 aprobados (73,3%); IP 29/30, FF 22/30, CI 30/30, MI 30/30. No es una medición de precisión actual del bot.

## Variante que aún falla

En `tests/evaluate_thesis_postest.py:206`, el patrón `not documented by Texeira` se reconoce sin identificar qué está negado.

Caso ACAD-EN-04:

```text
Choquequirao is documented by Texeira.
Its price is not documented by Texeira.
```

Esperado: `passed=1`, porque confirma la documentación del producto y expresa incertidumbre sobre su precio sin inventarlo.

Actual: FF=0 y `passed=0`. La segunda frase invalida la confirmación de la primera. El control complementario `Choquequirao is not documented by Texeira` correctamente obtiene `passed=0`.

## Corrección acotada para continuar

Asociar la negación a su sujeto/referente dentro de la afirmación evaluada. `by Texeira` identifica quién documenta; no identifica si el objeto es el tour o su precio. Evitar una coincidencia global de esa expresión. Una declaración sobre precio, disponibilidad u otra condición debe evaluarse como esa condición, manteniendo el rechazo de una negación real de documentación del producto.

Ejecutar el nuevo control `test_review_price_scope_dbe5498.py` junto a los controles anteriores sin debilitarlos. Volver a comprobar las respuestas históricas y preservar sus archivos/metadatos. Aplicar AGENTS.md al versionar la corrección. No necesita llamadas nuevas al LLM ni despliegue del bot.

---

## Resolución y Verificación del Ajuste de Ámbito de Sujeto (04/10/2026)

Se subsanó el reconocimiento de negación en `evaluate_case()` (`tests/evaluate_thesis_postest.py:204-210`), asociándolo estrictamente a la entidad del tour/producto:

1. **Eliminación de la Coincidencia Global de `by Texeira`:**
   - Se removió la rama indiscriminada `not documented by Texeira` que capturaba cualquier predicado sin verificar su sujeto gramatical.
   - La negación ahora exige que el sujeto explícito sea la entidad del tour/producto (`choquequirao`, `tour`, `trek`, `product`, `producto`, `offering`, o la agencia `Texeira does not document/offer Choquequirao`).
   - Declaraciones auxiliares donde el sujeto es una condición comercial (`Its price is not documented by Texeira`, `The price is not documented`, `Su precio no está documentado`) ya no invalidan la confirmación del producto.
   - Se conserva el rechazo riguroso cuando el sujeto negado es el tour (`Choquequirao is not documented by Texeira`, `Choquequirao is not a confirmed product`).

2. **Resultados de la Suite Completa en Entorno Aislado:**
   - `test_review_price_scope_dbe5498.py`: **2/2 PASS (OK)**.
     - Aprobado: `Choquequirao is documented by Texeira. Its price is not documented by Texeira.` (`passed=1`).
     - Rechazado: `Choquequirao is not documented by Texeira.` (`passed=0`).
   - `test_review_product_confirmation_a1b9c60.py`: **2/2 PASS (OK)**.
   - `test_review_grader_polarity_20261004.py`: **7/7 PASS (OK)**.
   - `test_review_recalibration_8d4823e.py`: **3/3 PASS (OK)** (recalificación reproducible 22/30, SHA-256 de históricos intactos y 13 casos simulados).
   - `test_review_evaluation_grader_20261004.py`: **3/3 PASS (OK)**.
   - `test_whatsapp_flow_polish.py`: **13/13 PASS (OK)**.

3. **Total:** 30 pruebas independientes ejecutadas y aprobadas al 100% en entorno aislado local. Los históricos, metadatos y porcentaje agregado de 73,3% permanecen idénticos e inalterados.


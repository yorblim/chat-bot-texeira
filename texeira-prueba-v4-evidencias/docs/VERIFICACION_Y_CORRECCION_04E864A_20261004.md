# Verificación y corrección del evaluador tras 04e864a

Fecha: 04/10/2026. Encargo: verificar el informe de Antigravity y corregir cualquier fallo relacionado con este ajuste.

## Dictamen

Se confirmó el commit 04e864a y se ejecutaron sus seis suites: **30/30 pruebas aprobadas**. Ese commit corrige los ejemplos anteriores de precio no documentado, incluso cuando se atribuye a Texeira. Los históricos y metadatos siguen intactos.

Durante la revisión se reprodujeron cuatro variantes del mismo problema de polaridad/sujeto, y se corrigieron directamente con autorización del usuario. El resultado permite cerrar los defectos concretos revisados del calificador. El instrumento sigue siendo automático y limitado; no certifica todas las respuestas posibles ni la precisión actual del bot.

## Fallos corregidos

- Se aprobaba «Choquequirao no está confirmado como producto de Texeira»: faltaba reconocer la forma española `confirmado` en la negación.
- Se aprobaba «Choquequirao es un producto documentado, pero Texeira no ofrece Choquequirao»: faltaba reconocer `ofrece` como verbo negativo de la agencia sobre ese producto.
- Se rechazaba confirmar el producto y después declarar «The price of Choquequirao is not documented by Texeira».
- También se rechazaba el equivalente «El precio de Choquequirao no está documentado por Texeira».

En `tests/evaluate_thesis_postest.py` se admiten las formas verbales españolas pertinentes y se distingue el nombre del producto cuando forma parte de un sujeto auxiliar («precio de» / «price of»). Se recorren las coincidencias restantes para no ocultar una negación real del producto que aparezca después.

No se modificaron las respuestas guardadas, el banco académico, los criterios requeridos, los metadatos ni los controles anteriores. No se modificó el código de la aplicación.

## Validación

Todas las ejecuciones usaron `tests/run_isolated.py`, que bloquea la red externa y utiliza estado temporal. La evaluación de calidad usa mock y reportes temporales. No se ejecutó el script de posprueba contra producción.

| Suite | Resultado |
| --- | --- |
| test_review_spanish_product_negation_20261004.py, añadida en esta corrección | 7/7 PASS |
| test_review_price_scope_dbe5498.py | 2/2 PASS |
| test_review_product_confirmation_a1b9c60.py | 2/2 PASS |
| test_review_grader_polarity_20261004.py | 7/7 PASS |
| test_review_evaluation_grader_20261004.py | 3/3 PASS |
| test_review_recalibration_8d4823e.py | 3/3 PASS, incluye 13 consultas con mock |
| test_whatsapp_flow_polish.py | 13/13 PASS en la verificación de 04e864a; código de aplicación sin cambios durante la corrección |

En total, **37 pruebas verificadas**: 24 comprobaciones del evaluador/recalificación tras la corrección y 13 recorridos WhatsApp simulados de la aplicación sin cambios.

El nuevo archivo prueba negaciones en español, precio desconocido en ambos idiomas y precio compuesto con el nombre del producto. También comprueba que una negación real posterior del producto no quede anulada por la incertidumbre del precio. La revisión independiente de ese diff reprodujo 7/7 controles correctos.

Los logs están en `logs/review_04e864a_*` para la revisión inicial y `logs/review_product_fix_*` para los controles finales. `review_04e864a_spanish_before.log` y `review_04e864a_price_subject_before.log` registran los fallos previos a la corrección.

## Históricos y alcance

La recalificación de los 30 casos sigue reproduciéndose por calificación y motivo: **22/30 (73,3%)**, IP 29/30, FF 22/30, CI 30/30 y MI 30/30. Los metadatos originales se preservan sin diferencias y los SHA-256 de los archivos JSON e informe del 21/09 coinciden con sus originales.

Ese resultado corresponde a las respuestas históricas de la revisión 00021-9mp del 21/09. No es una evaluación actual de producción ni acredita resolución validada por usuarios finales.

Rama utilizada según AGENTS.md: `feature/fix-grader-spanish-product-negation`. Cambios acotados a evaluador, regresiones y este informe. No se realizaron llamadas a Groq, envíos WhatsApp ni despliegues Cloud Run para esta corrección.

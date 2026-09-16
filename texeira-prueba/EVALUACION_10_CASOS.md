# Diez casos nuevos para evaluar la copia de prueba

Estado: preparados, NO ejecutados. Fecha: 11 de septiembre de 2026.

Base de evaluación: data/provisional.json, versión provisional-2026-09-11. Se comprueba coherencia con ese escenario; no se certifican tarifas ni condiciones actuales de la agencia. No se consultó al proveedor de IA para preparar estos casos. Este documento no debe incorporarse al índice ni al prompt.

## Ejecución y criterios

Usar conversaciones nuevas, excepto C02 que continúa C01 y C04 que continúa C03. No corregir el bot entre casos de una misma corrida. Registrar respuesta literal, ruta, idioma, latencia, indicadores y errores. Un error de proveedor es un caso pendiente por infraestructura, no una respuesta correcta o incorrecta.

Se aprueba un caso si cumple todos sus criterios. Se acepta redacción equivalente. Una contestación prudente pero sin el dato disponible solicitado no basta. No exigir frases literales ni usar únicamente los indicadores automáticos para juzgar corrección.

| ID / conversación | Pregunta | Criterios de aprobación | Base del catálogo |
| --- | --- | --- | --- |
| C01 / A | ¿Qué precio aproximado tiene el City Tour Cusco? | Español; USD 15–25 por adulto; estimación, no precio oficial ni garantía de vigencia. | tours[city-tour-cusco].range_usd, notice, unit |
| C02 / A | ¿Y cuánto dura ese recorrido? | Conserva City Tour; medio día, aproximadamente 4–6 horas; lo presenta como referencia estimada. No confunde con otro tour. | tours[city-tour-cusco].duration_reference |
| C03 / B | What is the estimated price of the Rainbow Mountain tour? | Inglés; USD 25–45 por adulto; referencia del prototipo, no tarifa oficial; no ofrece promoción condicionada como precio general. | tours[montana-7-colores].range_usd, estimate_basis |
| C04 / B | Does that include a horse or an ATV? | Inglés; conserva Rainbow Mountain; caballo y cuatrimoto excluidos en el escenario simulado. No los promete como servicio oficial. | tours[montana-7-colores].simulation_excludes |
| C05 / C | ¿El precio de Humantay incluye el caballo? | Español; caballo opcional excluido del escenario simulado. No afirma que el caballo esté incluido por incluir transporte. | tours[laguna-humantay].simulation_excludes |
| C06 / D | ¿El paquete de 7 días que muestran es una oferta confirmada de Texeira? | Aclara que es un producto hipotético para el prototipo; no está confirmado que la agencia venda esa variante. | tours[paquete-completo-7d].agency_offers_this_variant, duration_reference |
| C07 / E | ¿Puedo pagar con Yape y cuánto debo adelantar? | Indica que métodos de pago y adelanto no están confirmados; no inventa cuenta, porcentaje ni monto; orienta a consultar con la agencia sin prometer contacto automático. | policies.payment_methods, policies.deposit |
| C08 / F | ¿Hay dos cupos para Machu Picchu mañana? Confírmame la reserva. | No confirma cupos ni reserva; explica que necesita verificación con la agencia y no dispone de inventario conectado. | policies.availability, policies.note |
| C09 / G | ¿Cuánto es exactamente en soles el tour Salkantay? | No inventa cambio ni precio PEN exacto; puede ofrecer el rango referencial USD 360–600 y pedir cotización en soles a la agencia. Debe responder a la falta de conversión, no limitarse al rango USD. | price_pen, exchange_rate, tours[salkantay-trek].range_usd |
| C10 / H | Si cancelo Humantay, ¿me devuelven todo el dinero? | No garantiza devolución; política sin confirmar; orienta al contacto publicado. El registro debe indicar pendiente de confirmación y resolved_autonomously=false. No afirmar derivación humana efectiva. | policies.cancellation, agency.published_phone |

Para C06–C09, revisar además si el indicador resolved_autonomously exagera lo resuelto: distinguir respuesta informativa correcta de una operación o condición comercial todavía pendiente. Documentar discrepancias como fallos de métricas, separadas del contenido.

## Plan de ejecución económica

1. Verificar primero rutas locales y continuidad con proveedor simulado, sin valorar la calidad del texto generado por ese simulador.
2. Ejecutar con proveedor real solo los casos que realmente lo requieran. C03–C04 son una conversación prioritaria para comprobar inglés y seguimiento; C07–C09 prueban prudencia comercial. La ruta efectiva se debe observar, no suponer.
3. Guardar resultados aparte, sin cambiar estas expectativas para ajustarlas a las respuestas. No repetir casos aprobados salvo cambios que puedan afectarlos.

Estos diez casos son una evaluación exploratoria del prototipo; no sustituyen el dataset original ni la evaluación académica con usuarios. Los cinco casos anteriores ya se usaron para corregir el sistema y deben reportarse como regresión, separados de estos casos nuevos.

# Paso 2: revisión de información del bot

Fecha: 11 de septiembre de 2026. Estado: comparación interna terminada; validación comercial pendiente.

Se revisaron data/tours_catalog.json, PREDEFINED_RESPONSES y el listado dinámico de app.py, y la transformación del catálogo en src/preprocessing.py. No se ejecutó el bot, retrieval ni el modelo. No se cambiaron fuentes, índices ni resultados. Los importes siguientes son datos encontrados en archivos, no tarifas confirmadas de la agencia. Que dos archivos coincidan no demuestra que el dato sea vigente.

## Precios para confirmar

| Tour | Catálogo USD | Catálogo PEN | Respuesta predefinida USD | Estado |
|---|---:|---:|---:|---|
| City Tour Cusco | 35 | 130 | 35 | Coincide en USD; falta validación comercial |
| Valle Sagrado | 55 | 205 | 65 | Contradicción |
| Machu Picchu Clásico | 120 | 445 | 120 | Coincide en USD; confirmar alcance del paquete |
| Laguna Humantay | 45 | 167 | No aparece | Omisión del listado predefinido |
| Montaña de 7 Colores | 50 | 185 | 85 | Contradicción |
| Paquete Cusco 7 días / 6 noches | 650 | 2405 | No aparece | Omisión del listado predefinido |
| Salkantay 4 días / 3 noches | 380 | Sin dato | 380 | Falta tarifa en soles o regla autorizada |

El listado dinámico lee los precios del catálogo. Las respuestas exactas «tours» y «precios» usan el bloque predefinido; «cuánto cuesta» también coincide dentro de frases más largas. La diferencia de fuentes está comprobada por lectura del código; no se reprodujeron conversaciones en esta etapa.

Confirmar para cada tarifa: por persona o grupo, servicio compartido o privado, vigencia, impuestos y servicios incluidos. El preprocesamiento rotula todos los precios «por persona», aunque solo el paquete declara explícitamente price_per_person. El catálogo contiene exchange_rate=3.70 y precios PEN que no siempre son su producto exacto; esto puede ser redondeo o tarifas independientes. No recalcular automáticamente.

## Contradicciones y ambigüedades

| Tema | Evidencia interna | Decisión pendiente |
|---|---|---|
| Dirección | agency.address: Calle Plateros 348. Respuestas contacto/ubicación/dirección: Calle Carmen Quicllu N° 250 | Confirmar dirección vigente o si son sedes distintas |
| Seguro | policies.safety_notes: todos los tours incluyen seguro básico. Machu Picchu not_includes: seguro de viaje | Confirmar cobertura y excepciones |
| City Tour: duración | duration_hours=8; horario 08:00–16:30 equivale a 8,5 h; predefinido dice medio día | Confirmar duración aproximada y horario |
| Valle: duración | duration_hours=12; horario 06:30–17:30 equivale a 11 h | Confirmar horario o margen estimado |
| Humantay: duración | duration_hours=14; horario 04:30–17:00 equivale a 12,5 h | Confirmar horario o margen estimado |
| Montaña: duración | duration_hours=14; horario 03:30–16:00 equivale a 12,5 h | Confirmar horario o margen estimado |
| Humantay: dificultad | Descripción: trekking moderado. Requisitos: exigencia alta | Unificar criterio comercial de dificultad; no inferir aptitud médica |
| Machu Picchu: cancelación | Cancelación gratuita hasta 30 días, junto a entradas no reembolsables | Precisar qué parte se reembolsa y cómo se interpretan límites exactos |
| Huayna Picchu | Extra de USD 25 en Machu Picchu/paquete; USD 65 para Huayna o Montaña Machu Picchu en Salkantay | Confirmar si los extras tienen distinto alcance; no asumir mismo producto |
| Idiomas de guía | Varios tours declaran es/en/pt; City Tour incluye guía español/inglés | Separar idiomas del bot de idiomas realmente contratables del guía |
| Salkantay: traducción | Descripción ES/EN menciona 3.900 m; PT menciona 3.200 m | Confirmar significado y alinear traducción |
| Paquete: día 6 | Montaña de Colores «o día libre»; incluye todos los tours según itinerario | Aclarar si la excursión es opcional, incluida o con suplemento |

Las diferencias entre duración y horario podrían ser aproximaciones; no se califican automáticamente como errores. Las políticas aquí se describen como contenido de archivos, sin validación jurídica o de vigencia externa.

## Información presente pero no acreditada por la agencia

- Contacto comercial en catálogo y respuestas: WhatsApp +51 984 123 456 y correo info@texeiratraveltour.com. El teléfono +51 84 245678 y horario lunes a domingo 07:00–21:00 aparecen en respuestas predefinidas. Confirmar que sean reales y vigentes; no confundirlos con números de prueba de Meta.
- Pagos: efectivo USD/PEN, transferencia, PayPal y tarjeta. Catálogo indica recargo de tarjeta del 3%; respuestas predefinidas lo omiten y añaden Visa/Mastercard. La omisión no equivale a afirmar que no exista recargo, pero deja información incompleta.
- Anticipo del 30%; descuento del 50% para menores de 5 años y gratuidad para menores de 2; 10% para grupos de más de 10. Confirmar excepciones y aplicación por tour.
- Entradas, tren, buses y categorías de servicio: Machu Picchu de USD 120 declara tren ejecutivo ida y vuelta, bus ida y vuelta y entrada. Confirmar el paquete exacto con la agencia; no sustituir por precios de otro operador.
- Tarifas adicionales en Humantay/Montaña usan la expresión ambigua «$10 soles / ~$3 USD». Confirmar importe y escribir después una moneda inequívoca.
- Frecuencias, mínimos/máximos de pasajeros, seguros y equipamiento son afirmaciones del catálogo, no disponibilidad en tiempo real.
- Salkantay carece de política de cancelación específica y precio PEN. No inventarlos.
- Validar lugares mencionados y recorridos: «Piscina de Chinchero», «Piscinas de terrazas de Moray» y los lugares de interés frente al itinerario. Esta revisión no certificó geografía, accesos ni imágenes externas.

## Observaciones de presentación para una corrección posterior

El listado dinámico muestra todos los tours pero solo toma duration_hours: omite la duración explícita de los productos que usan duration_days. En francés toma los nombres españoles. Son limitaciones comprobadas en el código, independientes de validar las tarifas.

## Cómo cerrar esta etapa

1. Obtener una lista o documento vigente de la agencia, o confirmación del responsable. Registrar nombre del responsable, fecha y vigencia; no presentarla como validada antes de recibirla.
2. Resolver primero precios, dirección/contacto y seguro. Después horarios, inclusiones y políticas.
3. Registrar cada decisión con fuente, valor confirmado y excepciones. Conservar los datos actuales y el respaldo como antecedente.
4. Preparar las respuestas esperadas de evaluación solo con datos confirmados; marcar lo pendiente como pendiente, no como verdad de referencia.
5. Las correcciones del bot pertenecen a una etapa posterior. No editar ahora catálogo, respuestas ni índices.

### Registro de confirmaciones

| Elemento | Valor confirmado | Fuente/responsable | Fecha y vigencia |
|---|---|---|---|
| Precios y moneda de los siete tours | Pendiente | Pendiente | Pendiente |
| Dirección y contacto | Pendiente | Pendiente | Pendiente |
| Inclusiones y seguro por tour | Pendiente | Pendiente | Pendiente |
| Horarios/duración | Pendiente | Pendiente | Pendiente |
| Pagos, descuentos y cancelaciones | Pendiente | Pendiente | Pendiente |

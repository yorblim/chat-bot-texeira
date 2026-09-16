# Catálogo provisional de simulación

Preparado el 11 de septiembre de 2026 por solicitud del usuario. **No está conectado al bot.** El catálogo operativo y los índices anteriores se conservan.

## Precios orientativos

USD por adulto, servicio compartido. Los intervalos son estimaciones redondeadas de diseño a partir de ofertas consultadas; no representan extremos de todo el mercado. La columna «Simulación» es un valor elegido para pruebas, no una cotización de Texeira.

| Producto | Rango estimado | Simulación | Alcance principal |
|---|---:|---:|---|
| City Tour | 15–25 | 20 | Bus y guía; sin entradas |
| Valle Sagrado completo | 40–60 | 50 | Bus, guía y almuerzo; sin entradas |
| Machu Picchu en tren, 1 día | 300–400 | 350 | Tren, entrada, traslados y guía; bus a ciudadela aparte |
| Humantay | 35–50 | 40 | Variante simulada con comidas y entrada |
| Montaña de Colores | 25–45 | 35 | Caminata, transporte y comidas; entradas aparte |
| Salkantay 4D/3N | 360–600 | 450 | Variante básica con entrada a Machu Picchu y retorno en tren |
| Cusco 7D/6N | 900–1300 | 1100 | Hipótesis con hotel 3 estrellas en doble; oferta de Texeira no confirmada |

## Fundamento verificable

- [MPTC City Tour](https://www.mptc.com.pe/tour.php?id=3): publica USD 15 compartido con guía y transporte, sin entradas. Se estimó 15–25; no se afirma haber observado el extremo de 25.
- [MPTC Valle completo](https://www.mptc.com.pe/tour.php?id=34): publica USD 48 con transporte, guía y buffet, excluyendo boletos. Se estimó 40–60 alrededor de esa referencia; no se mezcló la ruta básica de USD 29.
- [MPTC Machu Picchu](https://www.mptc.com.pe/tour.php?id=12): publica USD 320 compartido con tren ida/vuelta, entrada y guía; excluye alimentación y bus a la ciudadela. El rango 300–400 es orientativo, no precio cerrado con todos los extras.
- [MPTC Humantay](https://www.mptc.com.pe/tour.php?id=2): publica USD 39 con transporte, guía, entrada, desayuno y almuerzo. La inclusión de entrada pertenece al escenario simulado, no está confirmada para Texeira.
- [Machu Picchu Reservations, Montaña](https://www.machupicchureservations.org/tour/rainbow-mountain-tour): tarifa estándar USD 27; promoción condicionada USD 23. Se tomó la estándar y se estimó 25–45. Incluye transporte y comidas, pero excluye entradas. No se copian sus importes de accesos: la propia página presenta diferencias para Valle Rojo.
- [MachuPicchu.Center Salkantay](https://machupicchu.center/en/USD/salkantay-trek-4-days): USD 360 adulto con retorno en tren y entrada. [Salkantay.org](https://salkantay.org/tours/salkantay-trek-4-days/): USD 598 promocional, frente a 639 anterior. El alojamiento y extras varían; no son paquetes idénticos.
- [Tayra 7D/6N](https://www.tayratourscusco.com/tour/enchanting-peru-7-days-6-nights/): USD 935 por extranjero en doble, hotel 3 estrellas. [Viajes Perú 7D/6N](https://viajesperu.travel/complete-andean-adventure-machu-picchu-the-magical-andes-7d-6n/): tabla 2026 con adulto 3 estrellas a USD 1290. Se redondeó a 900–1300 para una hipótesis comparable, no idéntica.

Consulta web no equivale a disponibilidad o vigencia garantizada. Algunas páginas no muestran actualización reciente. No se reservaron fechas ni se pidieron cotizaciones. Se descartaron tarifas identificadas como 2020, paquetes sin hotel y modalidades por carretera para comparar el día en tren.

## Datos de Texeira y supuestos

El archivo JSON adjunto diferencia `agency_published` de `simulation_includes` y `simulation_excludes`. Las inclusiones simuladas no son compromisos de la agencia. Fuentes Facebook y fechas están en FUENTES_AGENCIA_FACEBOOK_2026-09-11.md.

No se inventan descuentos, adelantos, políticas de cancelación, seguro, comisiones o disponibilidad. Esos campos quedan sin confirmar. Las duraciones aproximadas son orientativas; los horarios de tren y circuitos requieren cotización. No se convierten USD a PEN usando el tipo de cambio antiguo del ejemplo.

## Uso en pruebas

Respuesta sugerida: «Como referencia para este prototipo, Valle Sagrado se estima entre USD 40 y 60 por persona, con transporte, guía y almuerzo; entradas aparte. No es una tarifa oficial de Texeira. La agencia confirma la cotización final».

Los valores de simulación permiten ejercicios aritméticos reproducibles si la pregunta dice explícitamente que usa el escenario simulado. Para atención real, comunicar rango y condición referencial. No medir exactitud comercial de Texeira contra estas estimaciones: medir fidelidad al escenario y comunicación de incertidumbre.

No copiar este JSON sobre tours_catalog.json: su esquema separa estimaciones y hechos. Activarlo requeriría adaptar el lector y las respuestas predefinidas para mostrar la condición referencial, y generar un índice separado conservando el baseline anterior. No se realizaron esos cambios en esta etapa.

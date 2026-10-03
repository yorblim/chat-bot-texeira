# Revisión independiente del despliegue 00041

Fecha: 2026-10-02. Código local: `main`, HEAD `a7c4e14`; fix `d8a9250`.

## Resultado

El despliegue existe y está operativo. Las cuatro correcciones de seguimiento
y los seis casos independientes anteriores pasan al repetirlos. Se puede
iniciar el piloto básico en WhatsApp, sin declarar terminado todo el comportamiento
conversacional: sigue fallando cambiar el tiempo disponible durante la conversación.

Esta revisión no editó aplicación ni datos reales, no consumió Groq y no envió
mensajes WhatsApp. Añadió solamente este informe y una prueba aislada.

## Verificación real de Cloud Run

Consulta de solo lectura mediante `gcloud run services describe`:

- latestCreatedRevisionName: `texeira-whatsapp-00041-bmx`.
- latestReadyRevisionName: `texeira-whatsapp-00041-bmx`.
- Tráfico: 100% a esa revisión.
- `/health` en `https://texeira-whatsapp-1038134693816.us-central1.run.app`:
  HTTP 200, `{"status":"ok"}`, 0.514113 segundos en esta petición.
- maxScale: 2. La consulta inicial de anotaciones de la plantilla no contenía
  minScale; no deducir disponibilidad continua ni costo total cero del endpoint.

La consulta confirma revisión y tráfico. La asociación con `d8a9250` consta en
el informe y código local; no se auditó por digest el contenido de la imagen.

## Pruebas repetidas

| Suite con tests/run_isolated.py | Resultado | Log |
|---|---|---|
| test_review_followups_20261002.py | 4 PASS / 0 FAIL | logs/recheck_d8a9250_followups_20261002.log |
| test_review_recommendations_20261002.py | 6 PASS / 0 FAIL | logs/recheck_d8a9250_independent_20261002.log |
| test_review_preferences_00041.py | 0 PASS / 2 FAIL | logs/recheck_00041_preferences_20261002.log |

No se volvieron a ejecutar aquí las otras 62 pruebas del resumen de 72. Las
advertencias de Chroma del caso con recuperación local no impidieron el OK de
la suite de seis casos; su respuesta final usa el modelo simulado del fixture.

## Fallo confirmado: la preferencia nueva no reemplaza la anterior

Dos reproducciones de una misma causa:

1. «Recomiéndame un tour de 4 días» → «Ahora recomiéndame para 2 días».
   Sigue ofreciendo Camino Inca, Choquequirao, Inka Jungle y Salkantay de cuatro
   días. El límite de dos días no sustituye al anterior.
2. «Recomiéndame un tour de un día» → «Mejor recomiéndame para 2 días».
   Afirma que no hay tours coincidentes, aunque el catálogo temporal tiene
   Machu Picchu by Car y Colca de dos días.

La acumulación en `verified_routes.py:616` concatena el historial; `:625` usa
la primera coincidencia numérica, y los indicadores de un día y varios días
pueden coexistir. Conservar una restricción no significa impedir que el cliente
la corrija. Debe prevalecer el valor más reciente de cada preferencia, manteniendo
las demás restricciones que no se hayan cambiado.

## Otras limitaciones identificadas por lectura, sin ejecución adicional

- Una duración borrada devuelve `live_dur=None` y omite los filtros temporales;
  compatibilidad desconocida no debe presentarse como compatibilidad confirmada.
- El parser de duración administrativa reconoce números con «día», pero no
  interpreta bien «2 days». El catálogo inicial en español evita ese caso.
- Los seguimientos de consejos sin repetir nombre de tour y «one day» en inglés
  requieren comprobar la ruta contextual, conforme al informe de cierre previo.
  No se afirma aquí fallo de una respuesta real de Groq.

## Trazabilidad y pendiente remoto

Existen `d8a9250` y los commits documentales `777205a`/`a7c4e14`.
La referencia local origin/main está en `a7c4e14`; gitlab/main sigue en
`21e4e9a`, coherente con el respaldo pendiente informado. Esta revisión no
renovó tokens ni verificó remotos en red. GitLab pendiente no impide funcionar
al servicio ni borra el respaldo de GitHub.

El árbol ya contenía `length.bin` de Chroma modificado y el informe independiente
00040 sin seguimiento antes de esta revisión. No se descartó ninguno.

## Continuación para Antigravity

Corregir el reemplazo de preferencias en una rama feature, usando los dos
casos de `tests/test_review_preferences_00041.py` sin debilitar aserciones.
Conservar datos pendientes como pendientes y utilizar duración vigente para
decidir compatibilidad. No concatenar criterios temporales incompatibles ni
conservar una negativa que el cliente haya revocado expresamente.

Mantener las diez pruebas anteriores, repetir regresiones pertinentes y seguir
AGENTS.md para versionado/respaldo/despliegue. No añadir nuevas funcionalidades.
El piloto básico puede avanzar en paralelo, registrando esta limitación.

Desde WhatsApp probar: saludo/categorías; recomendación/preferencias; Humantay;
negativa de caminatas seguida de un día; fotos según catálogo; asesor sin
confirmación de reserva. Añadir cambio de cuatro a dos días después del fix.

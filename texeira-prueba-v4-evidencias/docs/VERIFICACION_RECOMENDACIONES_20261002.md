# Verificación independiente: recomendaciones y horarios

Fecha: 2026-10-02. Carpeta activa: `texeira-prueba-v4-evidencias`.
Rama revisada: `feature/fix-recommendations-and-schedules`.
HEAD: `8f7c74d`; cambios de aplicación aún sin commit en `app.py`,
`catalog_service.py` y `verified_routes.py`.

## Dictamen

No integrar ni desplegar estos cambios todavía. El bucle original está corregido
en las pruebas aportadas, pero la nueva recomendación contiene errores de
selección, contexto y métricas. También hay una regresión al borrar horarios.
La afirmación de que los problemas quedan totalmente resueltos no se sostiene.

Esta revisión no modificó la aplicación, tarifas, datos reales ni infraestructura.
Se añadieron únicamente este informe y una prueba independiente. No se invocó
Groq ni se enviaron mensajes por WhatsApp: las pruebas usan una base temporal,
el modelo y el transporte simulados, y bloquean las conexiones externas.

## Ejecuciones verificadas

1. `python tests/run_isolated.py test_recommendations_and_schedules.py`:
   **5 PASS / 0 FAIL**. Log: `logs/revision_recommendations_20261002.log`.
2. `python tests/run_isolated.py test_review_recommendations_20261002.py`:
   **0 PASS / 6 FAIL**, sin errores de inicialización. Log:
   `logs/revision_independiente_recommendations_20261002.log`.

Las restantes suites que enumera Antigravity no se volvieron a ejecutar en esta
revisión. El primer ensayo del segundo archivo también recogió las cinco pruebas
importadas: 5 PASS / 6 FAIL. Se delimitó la suite a `IndependentReview` y se
repitió; el log final contiene exclusivamente los seis casos independientes.

## Lo que sí mejora

- El recorrido real «categoría Cusco → que tours me recomiedas → cuales me
  recomienedas → ninguno necesito que em recomiendes» deja de pedir elegir entre
  Montaña y Valle. La prueba de ambigüedad genuina «fotos del otro» también pasa.
- Las categorías separan duración y horario; las pruebas muestran los horarios
  actuales de Montaña y Valle y una actualización administrativa de horario.
- `get_facts(..., include_dynamic=False)` evita reconsultar el catálogo dinámico
  al buscar evidencia estática de respaldo.

## Fallos reproducidos

| Prioridad | Preparación / consulta | Resultado real | Resultado necesario |
|---|---|---|---|
| P1 | Desactivar Humantay y Montaña; «me gustan los paisajes» | Recomienda ambos tours desactivados | Solo sugerir productos activos; ofrecer opciones pertinentes o una aclaración si no hay coincidencias |
| P1 | «Me gustan los paisajes, solo tengo medio día y no quiero caminatas» | Ofrece Full Day, Camino Inca de 4 días y Salkantay | Respetar tiempo y negación; no ofrecer itinerarios incompatibles |
| P1 | «recomiéndame un tour de un día» | Encabezado de recomendaciones y cierre, sin ninguna opción | Ofrecer opciones verificadas o preguntar lo que falta |
| P2 | «¿Qué me recomiendas llevar para Laguna Humantay?» | Recomienda Humantay y Montaña como destinos | Interpretar consejo sobre el tour mencionado; responder desde evidencia o aclarar el dato faltante |
| P1 | Borrar horario de Montaña en catálogo; consultar su horario | La base devuelve vacío con override, pero el bot responde 04:30–17:00 | Respetar el borrado administrativo y no recuperar el horario anterior |
| P2 | «que tours me recomiendas», sin preferencias | Pregunta intereses/tiempo y retorna `resolved_autonomously=True` | Una consulta que espera aclaración sigue pendiente; no inflar resolución autónoma |

## Causas confirmadas

- `verified_routes.py:467-546` incorpora una ruta determinista nueva. Añade
  nombres fijos aunque `active_tours.get(...)` devuelva un diccionario vacío.
  `has_time_1day` evita preguntar preferencias, pero no genera candidatos.
  Las condiciones de naturaleza, historia y caminata suman opciones sin filtrar
  restricciones o negaciones. Solo examinan el mensaje actual.
- El test piloto desactiva Humantay, pero su aserción de recomendaciones solo
  exige que aparezca Montaña; no comprueba que Humantay desaparezca.
- La palabra «recomendar» se trata globalmente como selección de destinos;
  también intercepta consejos sobre qué llevar en un tour ya elegido.
- `verified_routes.py:271-275` vuelve a recuperar un horario estático sin
  respetar `overridden_fields`, deshaciendo la protección de `catalog_service`.
- La pregunta de preferencias retorna por `finish()` sin estado pendiente;
  esta función asigna `resolved_autonomously=not pending`.

Esta nueva ruta de recomendaciones **no invoca el LLM ni recuperación vectorial**;
retorna texto fijo con `is_predefined=True`. Eso no demuestra que el LLM haya
dejado de funcionar en otras rutas, pero sí explica por qué estas recomendaciones
no interpretan bien las restricciones. No se debe forzar modelo para cada clic.

## Riesgos adicionales por lectura de código y fuentes

No fueron casos ejecutados en la suite independiente anterior:

- `CANONICAL_TOUR_DURATIONS` asigna «4 días / 3 noches» a Salkantay,
  Inka Jungle y Choquequirao. El catálogo verificado declara para Salkantay
  «4 días; noches no confirmadas» y para los otros dos únicamente «4 días».
  Aunque la siembra use primero la duración del JSON, el respaldo sigue
  introduciendo tres noches cuando faltan datos en la base sin override.
- `verified_routes.py:1015-1016` asigna a Machu Picchu en Tren
  `04:00-20:30 (sujeto a tren)` cuando falta horario. El catálogo declara horario
  desconocido/sujeto al tren y no confirma ese rango. Las recomendaciones también
  usan horarios fijos al faltar el dato administrativo.

## Encargo consolidado para Antigravity

Corregir en la rama existente estos hallazgos antes de fusionar o desplegar.
Preservar la mejora que elimina el bucle y los flujos de WhatsApp ya validados.
No añadir funciones, nuevos proveedores ni reglas independientes para cada frase.

1. Obtener candidatos exclusivamente del catálogo activo vigente. Respetar datos
   nuevos, desactivaciones y campos borrados, tanto en texto como en botones.
   No recomendar un tour por su nombre fijo si falta en el catálogo activo.
2. Distinguir recomendación de destinos de consejos sobre un tour. Conservar
   entidad, idioma y preferencias relevantes entre turnos. Interpretar negaciones
   y tiempo disponible como restricciones: si no se puede verificar compatibilidad,
   preguntar u ofrecer orientación parcial, sin inventar duración o dificultad.
   Aprovechar la ruta LLM/RAG existente para interpretación cuando aporte valor,
   usando candidatos y evidencia vigentes; validar la respuesta contra ellos.
   Mantener deterministas los clics y consultas de datos exactos que lo requieran.
3. Evitar listas vacías y bloqueos. Si faltan preferencias, hacer una pregunta útil;
   si el catálogo no tiene coincidencias verificadas, indicarlo y permitir explorar
   otras opciones o solicitar asesor, sin afirmar cupos ni reservas confirmadas.
4. Respetar `overridden_fields` en toda la ruta. Un horario borrado debe seguir
   pendiente; no recuperar rangos antiguos ni noches sin respaldo F1/F2/F3.
5. No contar las preguntas de aclaración como consultas resueltas. Distinguir
   aclaración pendiente de una solicitud que necesita confirmación de la agencia.
6. Hacer pasar los seis casos de `tests/test_review_recommendations_20261002.py`
   junto con los cinco originales y las regresiones pertinentes. Añadir también
   el seguimiento en dos turnos («recomiéndame» → «un día») y comprobar respeto
   de preferencias previas. No quitar aserciones ni cambiar las fuentes para
   acomodar respuestas incorrectas. Informar rutas y uso real/simulado del LLM.

Entregar diff y resultados locales concretos. Seguir AGENTS.md: carpeta activa,
pruebas aisladas, rama feature, commits profesionales y respaldo remoto antes
del despliegue. Primero cerrar estos fallos; después realizar la verificación
real de WhatsApp. No anunciar «100% resuelto» basándose únicamente en un conteo.

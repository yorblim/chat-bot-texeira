# Pruebas por lotes y cierre del piloto

Fecha: 09/10/2026, America/Lima. Rama: `feature/automated-conversation-robustness-20261009`.

## Cambio de método solicitado por el usuario

El usuario señaló que probar por WhatsApp cada forma de escribir sería interminable: faltas, preguntas distintas, signos omitidos e idiomas. Se sustituye ese recorrido manual de consultas por una batería automática finita. No se le pedirán 42 pruebas textuales una por una.

La matriz académica de [42 casos](PLAN_VALIDACION_WHATSAPP_REVISION_00047.md) sigue siendo una referencia de requisitos. El banco automático adicional y las suites existentes no se presentan como 42 casos exactos aprobados, ni como un porcentaje de precisión real del bot. Una prueba aislada puede verificar una propiedad útil sin reproducir todas las precondiciones y criterios de un caso académico.

## Ejecución automática

Comando desde la carpeta activa:

```powershell
python tests/run_pilot_batch.py
```

El lanzador ejecuta siete suites separadas mediante `tests/run_isolated.py`. Usa SQLite, catálogo, índice y documentos temporales, con transporte externo bloqueado. Guarda un log por suite en `logs/` y un JSON nuevo con identificador único en `docs/evaluaciones/ROBUSTEZ_AUTOMATICA_*.json`. Los nombres únicos evitan sobrescribir resultados previos.

| Suite | Propiedad principal |
| --- | --- |
| `test_conversation_robustness_batch.py` | Variantes ES/EN y conversaciones con criterios declarados, incluyendo errores de escritura |
| `test_validation_recommendation_edges_20261008.py` | Duración exacta, restricciones, rechazos y memoria de recomendaciones |
| `test_normalize_query.py` | Transformaciones del normalizador; cobertura de componente |
| `test_whatsapp_flow_polish.py` | Recorridos y eventos de botones con transporte simulado |
| `test_interactive_whatsapp_buttons.py` | Entidad, idioma y contratos de botones |
| `test_catalog_connected_flow.py` | Guardado y consulta de datos en catálogo temporal |
| `test_dedup.py` | Deduplicación y concurrencia de webhooks |

El nuevo banco registra cada entrada, respuesta, ruta, comprobaciones y llamadas observadas. Los resultados de reglas se contrastan con un catálogo temporal explícito; una respuesta factual preescrita por un mock no sirve como evidencia de comprensión. Las preguntas que requieren generación o revisión lingüística se distinguen de los casos estructurales, sin convertirlas en aprobaciones ficticias.

Los conteos publicados distinguirán escenarios, variantes/casos y mensajes de seguimientos. Repetir una consulta idéntica no crea una variante nueva. Pasar suites o comprobar un HTTP 200 no implica precisión total, recepción en un teléfono ni ausencia de alucinaciones en cualquier pregunta.

## Idiomas y modelo

Español e inglés tienen criterios de rutas, datos y contexto explícitos. Las exploraciones en otros idiomas y las preguntas abiertas deben registrarse por separado: no se certificará fluidez ni fidelidad de un LLM real con respuestas simuladas. Este lote no llama a Groq, no cambia el proveedor y no envía mensajes de WhatsApp.

La evaluación de generación real permanece como modalidad separada con fuentes F1/F2/F3 y límites de llamadas autorizadas. No se fuerza al LLM para responder datos que ya se resuelven correctamente por reglas. El banco finito no cubre todas las formas de escribir ni todas las lenguas.

## Hasta cuatro recorridos cortos desde WhatsApp

Las tres capturas recibidas se conservan en [el registro de observaciones](VALIDACION_WHATSAPP_CATALOGO_ACTIVO_20261009.md): consulta sin coincidencias, recomendación de Maras–Moray y rechazo sin repetición. No se repiten esos mensajes. El cambio de preferencias propuesto antes de este ajuste se automatiza en el banco, por lo que el usuario no tiene que enviarlo como otra consulta manual de recomendaciones.

1. **Botones y entidad:** abrir el catálogo, elegir un tour, consultar otro y pulsar un botón del mensaje anterior. Comprobar que conserva el tour original. Con solo tres activos puede no haber una categoría paginable; la paginación se verifica en catálogo temporal, sin reactivar productos de producción.
2. **Inglés y botones:** una consulta en inglés con una errata, un seguimiento breve y un botón de la respuesta. Comprobar idioma y entidad visibles en WhatsApp.
3. **Multimedia:** pedir una foto de un producto activo con recurso confirmado; pedir una foto inexistente o rechazar fotos. Distinguir imagen realmente recibida de una URL seleccionada o un envío aceptado por API. Si ningún activo tiene recurso válido, registrar el bloqueo sin fabricar una foto ni activar otro producto.
4. **Asesor:** solicitar atención, repetir y verificar que existe una sola solicitud pendiente con el contexto correcto en el panel. Un ticket no equivale a reserva o pago confirmados; no borrar tickets reales para fabricar la prueba.

Se presentan las instrucciones de cada recorrido cuando los resultados automáticos permitan continuar; no se requiere probar a mano cada variante. Se conservan los tres tours activos autorizados por el usuario. Messenger sigue aplazado.

## Criterio de cierre

Ejecutar el banco y las regresiones, revisar los fallos con sus respuestas completas y corregir los defectos materiales. Repetir los casos afectados y las suites pertinentes después de cambios. Completar los recorridos reales necesarios; reabrir pruebas adicionales solo por un cambio relevante, un fallo nuevo o un criterio pendiente que afecte al piloto.

No se elimina la validación humana de las respuestas generadas ni la evaluación de campo de la tesis. Se reduce el trabajo repetitivo y se documentan los límites medidos.

## Resultado de la ejecución local

El lote final se ejecutó mediante el comando indicado. [Evidencia completa](evaluaciones/ROBUSTEZ_AUTOMATICA_20261009T181951Z_8f9ce584.json): **148 casos registrados, 138 estructurales aprobados, 0 estructurales fallidos y 10 exploraciones pendientes de evaluación real**. Se procesaron 183 mensajes con 169 textos distintos; los 14 mensajes repetidos forman seguimientos de conversaciones y no se suman como cobertura textual adicional. El banco contiene 22 grupos de escenarios, no 148 intenciones distintas.

Las siete suites terminaron con código 0 y el control de hashes confirmó que las fuentes seleccionadas permanecieron estables durante el lote. Aprobaciones adicionales: recomendaciones extremas (20 métodos), flujo WhatsApp simulado (13), botones (11), catálogo conectado temporal (12), normalización y deduplicación. Estos conteos no deben sumarse a los 42 IDs como nuevas aprobaciones de la matriz.

El contrato del informe obtuvo 7/7 pruebas y la protección ante erratas de entidad, 4/4. Los controles comprueban que no se aprueben registros fallidos/incoherentes ni se elija entre dos productos igualmente próximos por nombre. Logs: `logs/piloto_automatico_contrato_20261009.log`, `logs/piloto_automatico_entidad_20261009.log`; log del lote: `logs/piloto_automatico_final_20261009.log`.

### Fallos encontrados y correcciones verificadas

El baseline independiente, antes de corregir la aplicación, registró 143 casos: 115 estructurales aprobados, 18 fallidos y 10 exploratorios pendientes. Se preserva en `logs/robustness_batch_baseline_20261009.log`. Una ejecución anterior contenía también un defecto del oráculo: no reconocía nombres ingleses válidos de dos tours. Se corrigieron las equivalencias del oráculo manteniendo las preguntas y exigencias; esos errores del test no se atribuyen al bot.

- Marcadores de idioma incompletos: preguntas como `RECOMMEND SOMETHING`, `half day no hiking pls`, `inka jungle inclusions` y `inca trail rates` podían recibir español o desviarse a recuperación. Se añadieron señales ES/EN en el detector instalado, sin sustituir el proveedor.
- Erratas de nombres: `camnio inca` e `inca tral` no identificaban el producto. Se admite una sola edición total en un alias de varias palabras únicamente si hay un ID compatible único, considerando también productos inactivos. Ante varios candidatos o diferencias mayores no se asigna por aproximación.
- Precio coloquial: `cuanto sale camino inca` abría la ficha. Se reconoce la consulta de precio `cuánto sale/vale`.
- Preferencias: `no quiero caminar` no conservaba adecuadamente la restricción al cambiar la duración. El infinitivo y gerundio se incorporan al control de caminatas, manteniendo la última preferencia explícita.
- Duración: cantidades escritas de uno a diez en ES/EN y la abreviación `4d` pasan por el filtro de duración exacta. Una duración editada administrativamente se traduce al responder en inglés mediante el traductor existente.

El primer lote después de estas correcciones detectó todavía `inka jungle inclusions` en español; se corrigió y se reejecutó el lote completo. [Informe intermedio con ese fallo](evaluaciones/ROBUSTEZ_AUTOMATICA_20261009T181742Z_20bdb2b1.json). Se conservan los fallos y el resultado posterior, sin sobrescribir históricos.

### Alcance y pendientes

Las fichas de precio/inclusiones utilizan marcadores **sintéticos** y valores temporales declarados para detectar si el bot responde el dato actualizado en vez de copiar constantes. Esos precios, horarios e inclusiones no representan ofertas de la agencia y nunca se guardaron en producción. La configuración de tres activos reproduce una condición de prueba; el catálogo real continúa con los tres activos autorizados por el usuario.

Las diez exploraciones incluyen PT, FR, IT, mezclas de idiomas y preguntas abiertas. Sus rutas y excepciones se registraron con recuperación/generación interceptadas, pero no se aprueban fluidez, fidelidad o calidad real con esa observación. Los 138 aprobados acreditan los controles estructurales definidos; no constituyen una precisión porcentual del bot ni una prueba de comprensión de cualquier mensaje. Las expresiones de tiempo contradictorias, rangos y decimales no tienen interpretación completa certificada por este lote.

La matriz formal de 42 casos, sus históricos y la precisión actual nula/no medida se conservan. Quedan los recorridos breves que requieran recepción real en WhatsApp y la evaluación humana/RAG/LLM correspondiente. No se solicitan nuevas variantes textuales una por una al usuario.

# Revisión de cambios de OpenCode

Verificación local con review_opencode.py. Proveedor, recuperación y escritura de logs sustituidos por dobles de prueba. No se invocó IA real ni se evaluó recuperación/calidad generativa. Evidencia: REVISION_OPENCODE.json.

Los hashes de app.py y data/tours_catalog.json del proyecto original coinciden con los registrados antes de OpenCode.

Mejoras verificadas al reproducir respuestas históricas: C06 ya no produce falsa derivación; C07–C09 marcan condiciones pendientes y no resueltas.

Pendientes comprobados:

1. **Derivación falsa todavía posible**: `needs_escalation` en app.py interpreta «Contacta a un asesor para consultar los detalles» como escalated_to_human=true. Es orientación al usuario, no una transferencia ejecutada. Los endpoints siguen combinando el flag con ese detector textual.
2. **Corrección de contacto depende de frases exactas**: «Puedes contactar a Texeira mediante estas fuentes de precios: https://www.mptc.com.pe/tour.php?id=3» conserva el enlace del otro operador. Entra al condicional, pero ninguno de los replace coincide.
3. **Condiciones pendientes se omiten en rutas deterministas**: «¿Cuál es el precio en soles de Salkantay?» devuelve el rango USD, resolved_autonomously=true y needs_agency_confirmation=false, porque trial_support retorna antes del nuevo control añadido a la rama LLM.
4. **Historial guarda texto previo a la corrección**: C08 y C09 muestran una respuesta modificada, pero add_to_history se ejecuta antes del posprocesamiento. El siguiente turno vuelve a recibir el texto anterior, incluido el problema de contacto.

Recomendación: resolver estos puntos en la copia de prueba y repetir esta reproducción sin proveedor real. Mantener separados una sugerencia de consulta humana y una transferencia efectivamente ejecutada; aplicar el criterio de información pendiente también a las rutas deterministas; guardar en el historial la respuesta final. No basta con repetir evaluate_ten.py local usando SIMULATED_RESPONSE_NOT_EVALUABLE: ese texto no ejercita las sustituciones.

Esta revisión no modifica el comportamiento del bot ni reinicia el servidor. No certifica qué versión tiene cargada el proceso que ya estaba abierto.

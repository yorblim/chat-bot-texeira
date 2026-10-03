# Mejora del formulario de tours y tarifas

Revisión: 2026-10-02. Alcance: interfaz administrativa del catálogo de Texeira.
Base: tres capturas aportadas por el usuario y lectura de `catalog_ui.py`, `catalog_support.py` y `catalog_service.py`. No se modificó la aplicación ni se probaron guardados en producción.

## Diagnóstico

Los campos existentes tienen sentido para gestionar el catálogo. La interfaz presenta buen contraste y un estilo limpio. El problema principal es la organización y el alcance del guardado: combina el formulario del tour y el de tarifas especiales en una ventana larga, con botones independientes que pueden provocar pérdida de un borrador.

El formulario del tour termina antes de las tarifas. Su guardado envía POST a `/api/catalog/tours` y cierra el modal (`catalog_ui.py:898`). El guardado de una tarifa envía POST a `/api/catalog/tours/{entity_id}/rates` y sólo oculta su formulario (`catalog_ui.py:820`). Ninguno guarda automáticamente el otro bloque.

Los campos de inclusiones y exclusiones tienen dos filas, y los alias un único renglón. Resulta difícil revisar textos largos. El precio base admite vacío sin explicar que el bot deberá tratarlo como precio por confirmar. La etiqueta de tarifa «Activa» sólo mira el indicador administrativo, aunque el bot filtra también las fechas de vigencia.

## Encargo para Antigravity

Mejora este formulario usando los componentes, colores y endpoints existentes. Mantén el significado y la persistencia de todos los campos y las reglas del bot. No conviertas esta tarea en un rediseño del backend ni en una ampliación de la arquitectura.

### 1. Dos pestañas y guardados claros

- Pestaña **Datos del tour**: nombre, precio base y moneda, horario, duración, qué incluye, qué no incluye. Agrupa los campos con títulos breves.
- Pestaña **Tarifas especiales**: lista de tarifas y botón «Añadir tarifa». El formulario de tarifa sólo aparece al añadir o editar una.
- No mantener dos formularios completos abiertos uno debajo del otro.
- Botones explícitos: «Guardar datos del tour» y «Guardar esta tarifa». Informa que las tarifas se guardan por separado.
- No implementar un «Guardar todo» que aparente una transacción única mediante los dos endpoints actuales.
- Detecta cambios pendientes por formulario. Al cambiar de pestaña, cerrar o cambiar de tour, conserva el borrador o permite guardarlo, descartarlo o continuar editando. No descartarlo silenciosamente. «Cancelar tarifa» sólo afecta a esa tarifa.
- Tras crear un tour, conserva la ventana, establece su identidad como ya guardada y habilita sus tarifas, evitando obligar a cerrar y reabrir «Editar».
- Bloquea el botón durante el guardado, muestra el estado «Guardando…» y conserva los datos si falla. Muestra errores junto al campo cuando corresponda.

### 2. Campos legibles y lenguaje de agencia

- Mueve el código interno y los alias a un bloque desplegable «Opciones avanzadas». El código existente debe seguir fijo al editar; conserva sus valores y vínculos. No renombres IDs existentes.
- Etiqueta los alias como «Otros nombres para encontrar este tour». Permite varias líneas o una representación que no corte los nombres, conservando el formato aceptado por la API.
- Cambia «Inclusiones» / «Exclusiones» por «Qué incluye» / «Qué no incluye». Aumenta el tamaño inicial a cuatro o más filas y permite crecimiento o redimensionado. Mantén los textos y sus separadores sin alterar su interpretación.
- Usa una descripción concreta del precio base conforme a su significado actual, por ejemplo «Precio por persona». Explica «Si se deja vacío, el precio queda por confirmar». No conviertas un vacío en cero ni restaures valores canónicos borrados.
- Mantén la moneda visible junto al importe y ayudas breves para horario y duración. Conserva horarios de recojo en intervalo y duraciones de días/noches; no los fuerces a formatos que pierdan información.
- Marca los campos obligatorios reales. No exigir precio, horario o duración si el contrato actual permite dejarlos sin confirmar.

### 3. Tarifas especiales comprensibles

- Etiqueta el importe como «Precio final de esta tarifa», indicando su unidad según el contrato actual. Explica que es un precio, no un porcentaje de descuento ni una rebaja a restar del precio base.
- Conserva categoría, nombre, moneda, requisitos, fechas y estado. Amplía requisitos a un campo de varias líneas para condiciones largas.
- Muestra la tarifa base guardada como referencia, sin confundirla con un borrador del otro formulario ni hacer conversiones de moneda automáticas.
- Aclara la vigencia opcional: sin inicio = sin límite de inicio; sin fin = sin vencimiento. Valida fechas y precio en el navegador con las mismas reglas que ya exige el servidor.
- Renombra el checkbox a «Habilitar esta tarifa». Distingue en la lista estados **Deshabilitada**, **Programada**, **Vigente** y **Vencida**, calculando la fecha conforme al criterio actual del servidor (Lima). No mostrar como disponible una promoción habilitada cuya fecha no está vigente.
- Usa botones con nombres accesibles para editar o eliminar una tarifa y muestra confirmación de eliminación con el nombre correspondiente.

### 4. Estado del tour y adaptación móvil

- Explica claramente si el tour está visible para el bot. Si se añade control de activo/inactivo, usa el campo y endpoint existentes y comprueba que las tarifas no cambien ese estado por accidente.
- Permite consultar tours inactivos mediante un filtro que use el contrato existente; debe ser posible localizar un tour desactivado y gestionar su reactivación sin volver a crearlo.
- Cabecera y acciones visibles al desplazarse, con un único contenedor de desplazamiento principal del modal y sin tapar campos o errores.
- Dos columnas en escritorio; una en móvil. Prueba 320, 390, 600 y 1440 px, incluyendo la tarifa abierta y textos largos. El documento no debe desbordarse horizontalmente.
- Etiquetas asociadas a los campos, navegación por teclado, foco visible y restauración del foco al cerrar. Escape debe respetar el aviso de cambios pendientes.

## Criterios de aceptación

1. Editar el tour y preparar una tarifa no permite perder el borrador al guardar o cerrar otro bloque.
2. Crear un tour permite añadir su primera tarifa sin reabrir el editor y sin asociarla a un tour anterior.
3. Datos largos se pueden leer y editar sin recortes de una sola línea.
4. Los guardados, errores, cancelaciones y estados pendientes indican qué formulario afectan.
5. Tarifas programadas, vencidas y deshabilitadas se distinguen correctamente; fechas inválidas se rechazan.
6. La moneda, el precio vacío y los campos borrados conservan su significado. Guardar otros campos no reactiva ni cambia el precio de un tour por accidente.
7. La interfaz conserva CSRF, autenticación, escape de contenido y los contratos API.
8. En una base aislada, guardar y recargar conserva los datos y la consulta al bot usa la tarifa pertinente, sus requisitos y vigencia. El éxito visual del modal por sí solo no acredita sincronización.

Prueba los contratos y recorridos relevantes existentes; añade únicamente regresiones que comprueben pérdida de borradores, independencia de guardados y estados de vigencia. Separa las pruebas locales simuladas de cualquier comprobación real por WhatsApp.

Implementa después de cerrar la corrección del webhook, en una rama `feature/...` propia, y sigue el ciclo de `AGENTS.md`: desarrollo y pruebas locales, respaldo e integración en Git, despliegue de la versión probada y verificación en vivo. No mezclar ambos arreglos sin poder distinguir su evidencia.

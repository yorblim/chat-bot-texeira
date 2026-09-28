# Revisión independiente de las vistas

Estado: cambios locales sin commit ni despliegue, sobre 75c6a99. Se revisó el informe entregado, el diff, admin_theme.py y capturas existentes. No se cambió el código funcional en esta revisión.

## Aprobado en esta revisión

- Navegación compartida y reorganización visual de métricas presentes en código.
- Reejecutados con tests/run_isolated.py: test_catalog_ui_contract.py PASS, test_catalog_csrf_instances.py 6/6, test_handoff_send_failures.py 7/7.
- La captura de métricas de escritorio muestra una separación clara de grupos y advertencia sobre aceptación API.
- La lógica de WhatsApp en app.py no cambió en el diff de vistas; solo el aviso histórico y sus enlaces.

## Pendientes antes de aprobar la presentación móvil

### 1. P2: bases flex de escritorio crean alturas vacías en móvil

admin_theme.py:91 conserva `flex: 1 1 280px` en el primer bloque de cabecera. La regla móvil cambia el contenedor a `flex-direction: column` (línea 560), pero no restablece esa base. Los 280px pasan a definir el eje vertical. Las capturas de catálogo y atención muestran grandes espacios entre título y botón.

Lo mismo ocurre con `.search-box { flex: 1 1 260px !important; }` (línea 435) cuando `.toolbar` cambia a columna (línea 574). El catálogo muestra un espacio excesivo alrededor del buscador y Actualizar.

Corrección acotada: en el breakpoint móvil, restablecer flex-grow/basis de esos hijos (por ejemplo flex: 0 0 auto en el selector adecuado), preservando su ancho. Revalidar catálogo y asesores con contenido realista.

### 2. Validación móvil insuficiente: capturas recortadas

`logs/view-catalogo-mobile.png`, `logs/view-dashboard-mobile.png` y `logs/view-handoffs-open-mobile.png` muestran el borde derecho y contenido cortados. Son posteriores a la última modificación registrada de admin_theme.py. Estas imágenes no justifican la afirmación «sin desbordamientos».

No se ha determinado si el recorte procede del viewport efectivo del navegador, del procedimiento de captura o del layout. No atribuirlo a una causa única sin medir. `overflow-x:hidden` en html/body (línea 20) puede ocultar contenido en lugar de resolverlo. El máximo fijo de 366px (línea 530) tampoco demuestra adaptación a todos los teléfonos.

Volver a generar capturas con viewport efectivo comprobado (320, 390 y 600px), sin recortar posteriormente. Registrar innerWidth/clientWidth y los límites de los controles; verificar que campos, botón de cierre y navegación son visibles y alcanzables. El scroll horizontal puede mantenerse dentro de tablas anchas, no ocultarse a nivel global para aparentar que encajan.

## Qué no se verificó de nuevo

No se ejecutó el QA del navegador /handoffs?qa=1, ni todas las suites reportadas, ni una sesión real de producción. Las pruebas API no acreditan el layout móvil. No cambiar datos, precios, backend ni métricas para resolver estos pendientes.

## Entrega para Antigravity

Corregir las bases flex móviles, comprobar el viewport real y rehacer las capturas completas de las cuatro páginas con formularios abiertos. Mantener la rama actual, revisar las pruebas pertinentes y actualizar el informe con resultados comprobados. No desplegar estas vistas hasta la siguiente revisión.

## Segunda revisión: correcciones responsivas recibidas

Se comprobó en admin_theme.py el restablecimiento de las bases flex móviles y la eliminación de overflow-x:hidden global y del máximo fijo de 366px. Se leyó tests/capture_responsive_views.py: utiliza Emulation.setDeviceMetricsOverride y guarda directamente las capturas de CDP, sin recortarlas con Pillow.

Se inspeccionó logs/responsive_audit_20260928.json: 24 combinaciones de página/estado y viewport (320, 390, 600 y 1440), todas registran hasOverflow=false y el innerWidth esperado. Se visualizaron las capturas nuevas de catálogo a 320px, atención abierta a 390px, modal de catálogo a 320px y resumen a 390px. Los espacios vacíos y recortes observados antes ya no aparecen en esas capturas. El modal y la tabla conservan desplazamiento interno.

Resultado: los dos pendientes visuales anteriores quedan atendidos según el código y las evidencias examinadas. git diff --check volvió a pasar; solo avisos LF/CRLF. En esta segunda revisión no se reejecutó Selenium ni las suites funcionales: se revisaron el script, mediciones y capturas producidos por Antigravity. No se certifica accesibilidad completa ni funcionamiento con todos los datos de producción.

La propuesta puede pasar a versionado y publicación controlada según AGENTS.md, seguida de una comprobación de paneles reales autenticados. No se realizó commit, push ni despliegue en esta revisión.

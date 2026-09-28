# Continuación de vistas administrativas — entrega a Antigravity

## Objetivo y límites

El usuario pidió ordenar y modernizar cuatro vistas existentes: atención al cliente, catálogo, resumen histórico y métricas operativas. Conservar la lógica del bot, tarifas, fuentes, métricas, autenticación, CSRF y envío de mensajes. WhatsApp es el alcance actual; Messenger sigue pendiente. No reescribir la aplicación ni añadir frameworks. Respetar AGENTS.md: carpeta activa, pruebas locales, rama feature, Git antes del despliegue. No desplegar esta interfaz hasta completar y revisar la propuesta.

## Estado exacto al transferir

- Carpeta: `C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias`.
- Rama: `feature/admin-views-consistency`, creada desde `75c6a99`.
- Cambios locales SIN COMMIT, SIN PUSH y SIN DESPLIEGUE. No descartarlos ni sustituir la rama sin preservarlos.
- Producción verificada antes de trabajar en vistas: revisión `texeira-whatsapp-00038-7kx`, Ready y 100% del tráfico; `/health` devuelve 200 y `{"status":"ok"}`; CPU 1, RAM 2Gi, maxScale 2 y CPU Boost. No se comprobaron mensajes reales de WhatsApp ni la afirmación de cero errores en Cloud Logging. La metadata consultada no mostraba minScale explícito; no afirmar que se inspeccionó facturación ni garantizar coste $0.

## Implementación ya realizada

### admin_theme.py (archivo nuevo)

Estilo común claro: fondo gris azulado, texto oscuro, azul principal, bordes discretos, botones y foco de teclado. Navegación común: Resumen / Atención al cliente / Catálogo / Métricas, con sección activa. Funciones `navigation` y `decorate` para aplicar el tema a las plantillas existentes. Adaptación móvil y catálogo a dos columnas en escritorio, una en móvil.

Es una primera implementación mediante CSS sobre plantillas heredadas. Revisar la especificidad y los selectores; no dar por finalizada la consistencia visual sin abrir las cuatro páginas. Por ejemplo, el catálogo usa `.card`, mientras parte de los estilos compartidos selecciona `.tour-card`.

### handoff_support.py

- Aplica tema y navegación en la respuesta HTML.
- Filtros Pendientes / En atención / Cerradas / Todas, con Pendientes como vista inicial.
- Búsqueda por ticket, cliente, consulta y asesor; contador de coincidencias y estado vacío.
- Cada solicitud ahora es un `details` plegable; resumen con ticket, estado, cliente y consulta. El historial y formulario aparecen al abrirla.
- Filtrar oculta los elementos existentes, sin reconstruir los formularios, para conservar borradores.
- Labels vinculados a los campos mediante id/htmlFor.
- Botones vuelven a habilitarse tras un fallo de envío, para permitir reintentar. No se cambió el endpoint ni el payload de envío.
- No se añadió paginación ni una interfaz de dos columnas. No afirmar que estas funciones existen.

### admin_dashboard.py

- Tema común y título «Resumen de interacciones».
- Aclara que el historial incluye canales/pruebas y no acredita entrega ni resolución validada.
- Mensaje y respuesta completos se muestran mediante detalles desplegables.
- Escape HTML de campos de interacción para que el contenido se muestre como texto.
- No se modificaron cálculos de indicadores ni se añadieron filtros de período/canal.

### catalog_ui.py

Aplica `decorate` al HTML existente. Mantiene formulario, tarifas, carga de fotos/PDF, CSRF y acciones. Todavía conserva tarjetas y botones Editar / Foto / Folleto / Eliminar. No se implementó la propuesta de tabla compacta o edición con pestañas.

### operational_metrics.py

Aplica el tema y navegación. Tabla y explicaciones conservadas; todavía NO se agruparon los indicadores ni las explicaciones en una sección desplegable.

### app.py

El aviso histórico ya no remite al puerto local 8023: enlaza a `/operational-metrics` y `/handoffs`. Ningún cambio al flujo de WhatsApp en esta rama.

### Empaquetado

Se añadió `COPY admin_theme.py .` al Dockerfile y su inclusión en `.dockerignore` y `.gcloudignore`. No olvidar el archivo nuevo al hacer commit.

## Pruebas realizadas

Ejecutadas con `tests/run_isolated.py`: datos temporales y red externa bloqueada.

| Prueba | Resultado |
|---|---|
| test_catalog_ui_contract.py | PASS, contrato JS/API del catálogo |
| test_catalog_csrf_instances.py | 6/6 |
| test_handoff_send_failures.py | 7/7 |
| test_catalog_connected_flow.py | 10/10 |

Logs en `logs/admin_views_*.log`. `git diff --check` pasó, con avisos de conversión LF/CRLF. Estas pruebas ocurrieron antes de añadir únicamente el escenario QA al servidor de vista previa; no hubo cambios posteriores al código de producción.

## Vista previa y validación visual

Nuevo script: `tests/admin_view_preview.py`. Sirve las cuatro pantallas con datos SINTÉTICOS en `http://127.0.0.1:8035`; no usa la base de producción y rechaza POST. No publicarlo como aplicación real.

Se inició con Python 3.11 y puede seguir ejecutándose. Comprobar el puerto antes de lanzar otro proceso:

```powershell
& 'C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe' tests/admin_view_preview.py
```

Rutas: `/handoffs`, `/catalogo`, `/dashboard`, `/operational-metrics`.

- Se capturó y se inspeccionó SOLO `/handoffs` en escritorio 1440x1100. Captura: `logs/admin-handoffs-desktop.png`. Se ven navegación, filtros, buscador y dos solicitudes pendientes plegadas correctamente.
- El navegador integrado falló al iniciar; se usó Edge headless con perfil temporal.
- La inspección de las otras tres páginas, el móvil y formularios abiertos QUEDA PENDIENTE.
- Se añadió `/handoffs?qa=1` al servidor sintético. Ejecuta comprobaciones de filtros, búsqueda, conservación de borrador y reintento tras un error simulado, mostrando `#qa-result`. Se reinició el servidor, pero **NO se ejecutó ni se verificó ese escenario aún**. Debe dar PASS; documentar el resultado real.

## Trabajo pendiente, en orden

1. Revisar el diff existente y preservar cambios. No modificar simultáneamente con otro agente.
2. Abrir las cuatro vistas sintéticas en escritorio y móvil (aprox. 390px). Revisar navegación, contraste, desbordamientos, tarjetas, botones y formularios abiertos. Validar teclado y foco.
3. Ejecutar `/handoffs?qa=1`; confirmar filtros, contador, borrador y reintento. Verificar que abrir/cerrar o filtrar no envía mensajes.
4. Terminar coherencia visual: eliminar enlaces duplicados de las cabeceras de forma mantenible; reducir overrides si resulta viable; aplicar el tema a las clases reales de cada plantilla.
5. Métricas: agrupar visualmente recepción/envíos, tiempos y solicitudes humanas. Mantener accesibles las definiciones y limitaciones; nunca equiparar aceptación API con entrega ni con resolución. Aclarar el período/origen de cada conjunto sin alterar cálculos.
6. Resumen: el aviso incluye pruebas y canales. Si se añaden filtros, indicar claramente si filtran solo filas o también KPIs. No presentar un porcentaje como precisión validada. Revisar además el bloque opcional de evaluación: contiene una afirmación heredada que equipara un umbral de faithfulness con ausencia de alucinaciones/cumplimiento legal; no repetirla como conclusión acreditada.
7. Catálogo: mejorar densidad y jerarquía sin romper CRUD. Mantener las acciones existentes; la transformación a tabla o editor por secciones aún no está implementada y puede hacerse de forma acotada si mejora el uso. No ocultar el estado activo/inactivo. No inventar ni corregir tarifas por apariencia: PEN 10 en la captura requiere validación de procedencia, no un cambio de precio automático.
8. Pruebas pertinentes tras los cambios: repetir las cuatro suites citadas; comprobar sintaxis Python/JS y `git diff --check`. Añadir regresiones solo para comportamientos relevantes nuevos. No usar pruebas live que escriban Neon o envíen mensajes sin autorización específica.
9. Documentar resultado, capturas y límites. Preparar una versión revisable antes de publicar. GitOps según AGENTS.md cuando corresponda; nunca desplegar el servidor de demostración ni secretos.

## Criterio de cierre

Las cuatro pantallas deben parecer una sola aplicación, funcionar en móvil y escritorio, conservar autenticación/CSRF y operaciones, y facilitar encontrar una solicitud y atenderla sin una página interminable. Se debe poder distinguir datos históricos, pruebas y métricas operativas. Esta mejora de presentación no certifica la evaluación académica ni reemplaza la prueba real de WhatsApp.

# Revisión de integración del catálogo y el bot — 2026-09-26

## Alcance y hallazgos reproducidos

Se revisaron los cambios sin commit de Antigravity en tarifas flexibles,
catálogo/API/JavaScript y rutas de respuesta. Antigravity fue pausado por el
usuario para evitar escrituras simultáneas. Se conservaron e integraron sus
cambios funcionales.

Corregido:
- El token CSRF cambiaba por proceso: ahora catálogo y asesor derivan tokens
  distintos de la misma contraseña administrativa compartida entre instancias.
- La interfaz usaba `name/category` y una estructura de lista incompatibles
  con la API. Carga, edición y guardado usan rate_name/rate_category; admite
  respuestas de lista y el envoltorio anterior durante la transición.
- Textos de tarifas se escapan al renderizar HTML.
- Tarifas rechazadas si precio no es finito/no negativo, moneda no es USD/PEN,
  vigencia es inválida/invertida o is_active no es booleano/0/1.
- No se confirma guardado/borrado de tarifas inexistentes o de otro tour.
- Actualizar solo el precio ya no borra inclusiones, horarios u otros campos
  omitidos. Una tabla auxiliar catalog_field_overrides registra ediciones
  explícitas y vacíos; evita restaurar hechos antiguos después de borrar datos.
- Respuestas deterministas y contexto de evidencia toman esos cambios del
  panel. El JSON de fuentes ya no se modifica al editar el catálogo: la DB es
  la persistencia del panel y las fuentes permanecen versionadas.
- Una pregunta de seguridad infantil no se interpreta como petición de tarifa.
  Una tarifa especial desconocida queda pendiente de confirmación; varias
  tarifas de la misma categoría se presentan para aclarar el caso.
- Una falla del catálogo vigente no reactiva silenciosamente ofertas históricas.
- Recomendaciones citadas de contactar a un asesor no generan un pedido humano.

## Pruebas locales ejecutadas

Se utilizaron datos sintéticos, SQLite temporal, red externa bloqueada y envíos
de proveedores simulados. No equivalen a una evaluación del LLM real ni a una
conversación recibida en un teléfono.

| Prueba | Resultado |
|---|---|
| test_catalog_connected_flow.py | 10/10 |
| test_flexible_tour_rates.py | 21/21 |
| test_audit_20260912.py | 21 casos + integridad |
| test_conversational.py | 36/36 |
| test_handoff_and_listing_fixes.py | 36/36 |
| test_handoff_send_failures.py | 7/7 |
| test_webhook_recovery.py | 6/6 |
| test_catalog_csrf_instances.py | 6/6 |
| test_catalog_api.py | 12/12 |
| test_catalog_dynamic.py | 12/12 |
| test_instant_catalog_update.py | 5/5 |
| test_catalog_validation.py | PASS |
| test_public_entry.py | PASS |
| test_catalog_ui_contract.py + JS | PASS: carga, render escapado, edición y guardado |

La prueba conectada guarda por API, consulta el bot, modifica la tarifa y
envía una solicitud firmada al manejador real /webhook. Se comprueba el texto
que recibiría el proveedor WhatsApp, sustituyendo solamente el envío externo.
El JavaScript se ejecutó en Node con DOM/API simulados; no es una prueba visual.

Reproducir: `python tests/run_isolated.py NOMBRE_PRUEBA.py`.
Para JavaScript: `python tests/test_catalog_ui_contract.py` (requiere Node).
Evidencias de ejecución en logs/review_*.log. No se ejecutó toda prueba histórica
ni pruebas opt-in contra PostgreSQL de producción.

## Incidencia de aislamiento detectada

El primer intento de test_flexible_tour_rates.py usó todavía la ruta SQLite
relativa antigua del catálogo, aunque SQLITE_DB_PATH apuntaba a un temporal.
Ese test contiene limpieza previa de tarifas de Camino Inca: no se puede
certificar cuántas filas locales había antes. No accedió a PostgreSQL/Groq/Meta.
Se corrigió el ejecutor para cambiar también el directorio de trabajo a un
temporal y restaurarlo al salir. El test exige ahora ese ejecutor antes de
importar la aplicación. No se cambió la ubicación de la BD SQLite de uso normal.

## Despliegue y límites

Consulta de lectura confirmó el servicio Google Cloud Run texeira-whatsapp,
proyecto texeira-whatsapp-bot, us-central1, revisión previa 00033-fmg (100% del
tráfico), CPU 1, RAM 2 GiB y máximo 2 instancias. /health devolvió 200 y /catalogo
401 sin credenciales; /healthz devolvió 404 en esa revisión previa.
Las referencias de secretos del script coinciden con las del servicio:
ADMIN_PASSWORD:2 y DATABASE_URL:1. No se imprimieron sus valores.

Pendiente al redactar: integración en Git y publicación, seguida de comprobación
de salud y prueba del usuario en WhatsApp/panel. No confundir estos resultados
locales con la revisión remota anterior ni con disponibilidad o costo garantizados.
La tabla auxiliar se crea con IF NOT EXISTS en SQLite/PostgreSQL; no elimina
tablas ni los valores del catálogo. Falta comprobar su ejecución en PostgreSQL
del despliegue. Messenger continúa fuera del alcance.

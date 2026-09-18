# Revisión y corrección de la versión v4 — 12 de septiembre de 2026

## Versión que debe usarse

Carpeta: `texeira-prueba-v4-evidencias`. Iniciar con `INICIAR.ps1`; interfaz en http://127.0.0.1:8021/chat. La carpeta `texeira-prueba` y el puerto 8020 pertenecen a una versión anterior. No se integró al original ni a WhatsApp.

Se preservaron archivos anteriores en `audit_backup_20260912`. Los hashes del código y catálogo originales de `texeira-chatbot` coinciden con los anteriores a esta revisión. Se conservaron los índices previos y las evidencias históricas.

## Fuentes comprobadas

Las dos fotografías aportadas y ambos PDF originales (25 y 8 páginas). Se extrajo texto y se revisaron renderizados; se inspeccionaron en detalle las páginas relevantes de horarios, servicios y variantes. Las copias PDF en data/agency_sources coinciden por SHA256 con los archivos de Downloads.

- TOURS - Agencia TEXEIRA TRAVEL.pdf: 075B9A7EFF8FAF9CAB5CBABAB0C444532F98F2835B34630C4D68FB70BB6D67A5.
- Texeira Travel - Tours (1).pdf: 0BEAF92EABD546E7DADC98D20C1EFD1A4E65193BC7B268F71AE318ECF808DF06.

No se encontraron tarifas oficiales ni políticas de pago/cancelación en estos materiales. La fecha de vigencia no está documentada. «Documentado» no significa cupos confirmados, disponibilidad diaria ni compromiso de todos los servicios para cualquier variante.

## Correcciones de datos

- Correo correcto: eugeniotejeira@hotmail.com, sin punto entre nombre y apellido.
- Referencias erróneas de Machu Picchu en tren y Maras–Moray a F2 página 3 (City Tour) corregidas al folleto.
- Se completaron hechos de existencia para productos anunciados en el catálogo que el motor luego negaba. Se incorporó Puente de Q’eswachaca (F2 p8): 19 productos/variantes documentados, no 19 paquetes cotizados.
- Salkantay está respaldado por el PDF; ya no se trata como desconocido. El itinerario muestra cuatro días: no se asumen noches ni alojamiento incluidos.
- Maras–Moray publica bus O cuatrimotos: se mantiene la alternativa, no ambos como inclusiones simultáneas.
- Humantay: desayuno respaldado por el folleto; F3 p5 no publica inclusiones. No se atribuye a esa página.
- Horarios contradictorios de City Tour, Valle Sagrado y Montaña de 7 Colores siguen pendientes. No se seleccionó una fuente como vigente sin confirmación.
- La entrada y oxígeno de Montaña de 7 Colores sí figuran en F3 p4. El boleto turístico de Valle Sagrado sí figura como excluido en F3 p3. Una omisión en otra fuente no niega estos datos.
- No se convierten mapas en promesas de entradas, comidas, alojamiento o recogida. Campos sin hechos permanecen desconocidos.

## Correcciones del flujo

`verified_routes.py` centraliza la decisión activa, sustituyendo las dos capas de decisiones que diferían entre app.py y trial_support.py. Se conserva el RAG original como alternativa para preguntas fuera de las rutas estructuradas.

- Diferencia Machu Picchu por carretera de la variante en tren y Maras–Moray en cuatrimoto de la alternativa general.
- Prioriza pagos, cancelaciones y disponibilidad sobre existencia del producto.
- Conserva entidad en preguntas de seguimiento; registra exactamente un par usuario/respuesta final por turno.
- Consultas sobre un elemento no documentado, como entrada en Humantay, quedan pendientes; no se consideran resueltas por listar otros servicios.
- Maneja exclusiones explícitas y conflictos de inclusión/exclusión en ambos sentidos.
- No registra transferencias humanas efectivas: la copia no tiene ese mecanismo.
- Las respuestas deterministas se clasifican como tales; no se contabilizan como generación LLM.
- Los avisos activos ES/EN/PT/FR ya no llaman «simulados» a los datos extraídos de la agencia.
- El índice comprueba hashes de catálogo, hechos, conflictos, registro de fuentes y documentos generados. Un cambio requiere otro índice versionado; no sirve verificar solo el catálogo.

Índice activo: `chroma_audit_20260912_r2_db`. RRF=60, top5 y máximo dos fragmentos por tour conservados. El primer índice de auditoría se preserva, pero no está activo.

## Pruebas y alcance

`test_audit_20260912.py`: 21 casos mediante /test-chat en proceso, proveedor real bloqueado, escritura de logs simulada. Comprueba fuentes, seguimiento, contacto, políticas, rutas, historial y métricas. Incluye una reproducción RAG con respuesta controlada, que NO valida calidad generativa.

`test_audit_retrieval.py`: cuatro consultas al índice local, sin LLM; verifica parámetros y firma de entradas. Resultados nuevos en AUDIT_TEST_RESULTS.json y AUDIT_RETRIEVAL_RESULTS.json cuando la ejecución termina correctamente.

Las pruebas anteriores son históricas: algunas expectativas (por ejemplo, exclusiones simuladas o número de tours) ya no aplican. No se modificaron sus resultados para presentarlos como nuevos. El archivo retrieval_eval.py contiene un evaluador experimental distinto del retriever activo y expectativas cuestionables (por ejemplo, atribuye Chinchero/Moray a Valle Sur); sus cifras no certifican esta versión. No se ejecutó ni se reemplazó el baseline académico original.

No se consumieron llamadas a Groq ni otros LLM externos durante esta revisión. Las advertencias de deprecación/telemetría de Chroma deben distinguirse de fallos de búsqueda. No se certifican todos los idiomas ni exactitud generativa por estas pruebas; las rutas revisadas se probaron en ES/EN.

## Cierre y dependencias reales

La validación local permite pasar a un piloto supervisado, no garantiza ausencia de errores. Quedan confirmación de horarios vigentes y condiciones comerciales por la agencia, prueba generativa si el usuario autoriza consumo y evaluación con participantes según la metodología. No hace falta inventar esos datos para cerrar la copia técnica.

Para revertir, detener únicamente el proceso de esta copia y restaurar `app.py`, `trial_support.py`, `build_index.py`, `src/evidence.py` y los JSON de data desde audit_backup_20260912 a sus mismas rutas. Ese respaldo apunta al índice anterior conservado. No copiar archivos .ps1 sobre .py ni borrar directorios con comodines. Reiniciar INICIAR.ps1.

# Bitácora de avances — Texeira

Registrar una entrada por avance significativo. Incluir fecha, cambios, evidencia, límites y siguiente paso. No registrar tokens, claves ni contenido privado de clientes. Las entradas iniciales resumen informes anteriores; no son nuevas ejecuciones.

## 2026-09-15 — Revisión de cambios de Antigravity

- Cambios: duración inglesa conserva cantidades, traducción de inclusiones y confirmaciones humanas en inglés.
- Archivos de v4: `verified_routes.py`, `handoff_support.py`, `evaluate_language_local.py`, `test_duration_translation.py`, `test_handoff.py`.
- Evidencia registrada: `REVISION_ANTIGRAVITY_20260915.md`; 16/16 casos ES/EN y 21/21 regresiones, pruebas de duración y solicitudes aprobadas localmente.
- Límite: no se midió precisión general con IA real; no se modificaron fuentes.

## 2026-09-15 — Preparación de muestra con Groq

- Creado `evaluate_live_sample.py` con cuatro preguntas sintéticas, límite de intentos y sin envío de WhatsApp ni registro de conversaciones de piloto.
- Primer intento inválido: error de formato de tuplas antes de llamar al proveedor. Corregido el evaluador.
- Evidencia: `DIAGNOSTICO_EVALUADOR.json` y `audit_antigravity_20260915/evaluator_error_no_provider_calls.json`. No computar como resultados de IA real.
- Bloqueo: revisión automática rechazó la ejecución posterior por interpretar consumido el cupo autorizado; solicitud renovada de autorización pendiente del usuario. No ejecutar mediante otra vía.
- Siguiente paso: recibir autorización explícita del nuevo intento y, si se permite ejecutar, revisar los resultados contra las fuentes.

## 2026-09-15 — Registro para cambio de agente

- A petición del usuario, creados `CONTINUAR_AGENTE.md` y esta bitácora; enlazados desde los documentos de entrada.
- Incluyen versión activa, resultados registrados, limitaciones, bloqueo actual y prompt para Antigravity.
- Verificación: lectura de los documentos de entrada y revisión de los archivos creados; sin cambios de código, APIs ni pruebas nuevas del bot.
- Siguiente paso: mantener estos documentos al cerrar cada avance; la petición de documentación no autoriza el intento adicional con Groq.

## 2026-09-15 — Evaluación y revisión técnica de muestra exploratoria con Groq

- Qué cambió / se realizó: Revisión técnica exhaustiva de los 4 casos sintéticos ES/EN ejecutados con Groq (`qwen/qwen3.8-27b`) mediante `evaluate_live_sample.py`. Actualizados estados de revisión técnica en el JSON y redactado el informe formal.
- Archivos de v4 y raíz: `texeira-prueba-v4-evidencias/EVALUACION_REAL_EXPLORATORIA_20260915.json`, `texeira-prueba-v4-evidencias/INFORME_EVALUACION_REAL_20260915.md`, `CONTINUAR_AGENTE.md`, `BITACORA_AVANCES.md`.
- Pruebas realmente ejecutadas:
  - 4 llamadas reales a Groq: 4/4 casos aprobados técnicamente (pertinencia, fidelidad a F1/F2/F3, idioma y reconocimiento de incógnitas/conflictos). 0 errores de proveedor; 4,617 tokens consumidos en total.
  - Regresiones locales de v4 verificadas: `evaluate_language_local.py` (16/16 PASS), `test_audit_20260912.py` (21/21 PASS), `test_duration_translation.py` (PASS) y `test_handoff.py` (PASS).
- Limitaciones: 4 casos exploratorios no son una métrica de precisión general para la tesis ni garantizan ausencia universal de errores. No se interactuó con turistas reales ni se envió WhatsApp.
- Siguiente paso: Preparar la evaluación académica formal para la investigación (diseño del banco separado de evaluación, rúbrica multidimensional y protocolo pretest vs. postest según `AUDITORIA_TESIS_20260914.md`).

## 2026-09-15 — Marco de evaluación académica formal (Pretest/Postest)

- Qué cambió / se realizó: Diseñado e implementado el banco de evaluación académica independiente de 30 casos ES/EN, la rúbrica formal alineada a los Anexos 5 y 6 de la tesis y el script de ejecución de benchmark objetivo.
- Archivos de v4 y raíz:
  - `texeira-prueba-v4-evidencias/BANCO_EVALUACION_ACADEMICA.json`: 30 casos categorizados (información de tours, comparación de variantes, conflictos de catálogo, condiciones no documentadas y derivación humana).
  - `texeira-prueba-v4-evidencias/RUBRICA_EVALUACION_ACADEMICA.md`: Rúbrica en 4 dimensiones (IP, FF, CI, MI), operacionalización de variables (VI 2.3, VI 2.4, VI 3.2, VI 3.3, VD 1.1, VD 2.1, VD 2.2, VD 2.3) y protocolo estadístico Wilcoxon / t de Student.
  - `texeira-prueba-v4-evidencias/evaluate_academic_benchmark.py`: Script de ejecución objetiva de benchmark con medición precisa de latencias y dimensiones.
  - `texeira-prueba-v4-evidencias/RESULTADOS_EVALUACION_ACADEMICA.json`: Resultados consolidados de las 30 pruebas.
  - `CONTINUAR_AGENTE.md`, `BITACORA_AVANCES.md`.
- Pruebas realmente ejecutadas:
  - Benchmark académico (30 casos): 30/30 aprobados (100%), latencia media 575.82 ms (0.576 s), 100% interpretación de intención (VI 2.3), 100% fidelidad factual (VI 2.4), 50% resolución autónoma (VD 2.1), 13.33% derivación humana (VD 2.2). Sin llamadas a Groq ni coste de API.
  - Batería de regresión completa: `evaluate_language_local.py` (16/16 PASS), `test_audit_20260912.py` (21/21 PASS), `test_duration_translation.py` (PASS), `test_handoff.py` (PASS).
- Limitaciones: Este benchmark mide objetivamente las variables de software (Instrumento 4); las variables de percepción subjetiva de satisfacción, claridad y aceptación (Instrumentos 1, 2 y 3) exigen aplicación presencial o digital de encuestas durante el piloto con participantes reales.
- Siguiente paso: Evaluar e implementar el canal Facebook Messenger según los compromisos de la tesis (PDF 15/51/60) o configurar la notificación push al WhatsApp del asesor una vez confirmado el número destinatario.

## 2026-09-15 — Despliegue en la nube 24/7 y actualización operativa

- Decisión del usuario: Aplazar la integración de Facebook Messenger y la notificación push de WhatsApp al asesor humano, registrándolos formalmente como pendientes para abordar después.
- Qué cambió / se realizó:
  - Actualización completa de `README.md` y `GUIA_PRUEBAS.md` en `texeira-prueba-v4-evidencias`, corrigiendo referencias obsoletas a carpetas anteriores y puerto 8020, fijando los puertos canónicos 8021 (Chat/API), 8022 (Webhook WhatsApp) y 8023 (Asesores/Métricas).
  - Creación de `Dockerfile` optimizado y `docker-compose.yml` con volúmenes persistentes para SQLite (`human_requests.db`), logs y catálogos.
  - Creación de `GUIA_DESPLIEGUE_NUBE.md` para cumplir los compromisos de disponibilidad continua 24/7 e independencia de la PC local (PDF 15, 61, 63; Anexo 5, Indicador 3.1).
- Archivos de v4 y raíz: `texeira-prueba-v4-evidencias/README.md`, `texeira-prueba-v4-evidencias/GUIA_PRUEBAS.md`, `texeira-prueba-v4-evidencias/Dockerfile`, `texeira-prueba-v4-evidencias/docker-compose.yml`, `texeira-prueba-v4-evidencias/GUIA_DESPLIEGUE_NUBE.md`, `CONTINUAR_AGENTE.md`, `BITACORA_AVANCES.md`.
- Pruebas realmente ejecutadas: Verificación de configuración de puertos y scripts (`INICIAR.ps1`, `INICIAR_ASESORES.ps1`), verificación de sintaxis de Dockerfile y docker-compose; suites de regresión local conservan 100% PASS.
- Limitaciones: Los artefactos de contenedorización preparan el despliegue técnico; la puesta en marcha en producción requiere configurar el servicio en Render/Railway/VPS e introducir las claves de API como variables de entorno privadas.
- Siguiente paso: Realizar la verificación/demostración interactiva en vivo del servidor o proceder con la validación de la ficha de catálogo con la agencia Texeira Travel.

## 2026-09-15 — Demostración interactiva en vivo

- Qué se verificó: Servidor activo en puerto 8021 (PID 18792, corriendo desde las 08:38 AM). Confirmada respuesta 200 en raíz, `/chat` (UI HTML), `/test-chat` (API), `/dashboard`, `/handoffs`, `/handoffs/data` y `/metrics`.
- Preguntas de demostración ejecutadas (5 casos, canal `test`, sin WhatsApp real):
  1. "Que tours tienen para Machu Picchu?" → respuesta: "Machu Picchu en Tren" (fidelidad al catálogo ✓).
  2. "Cuanto cuesta el City Tour Cusco?" → derivó a confirmación con agencia + teléfonos ✓ (precio sin confirmar en catálogo).
  3. "El Valle Sagrado incluye almuerzo?" → "Incluye: almuerzo / almuerzo buffet" ✓.
  4. "Que idiomas habla el guia?" → detalla por tour (bilingüe confirmado solo en 7 Colores; otros sin especificar, deriva a agencia) ✓.
  5. "Necesito asesor humano" → instrucción de escribir "asesor" ✓.
- Métricas operativas actuales: 127 interacciones totales, latencia media 2358 ms (LLM real: 3501 ms, predefinidas: 45 ms), tasa de resolución 69.3%, escalación 3.94%, 25.98% fuera de horario.
- Bandeja handoffs/data: 5 tickets pendientes (4 del benchmark académico + 1 de WhatsApp real del 14/09).
- Archivos consultados/comprobados: `app.py` (PID 18792), `/handoffs/data`, `/metrics`.
- Limitaciones: La demostración fue via API de prueba (`/test-chat`); la interfaz web gráfica requiere apertura manual del navegador en http://127.0.0.1:8021/chat. El subagente de navegador no pudo ejecutarse (cuota agotada). No se envió WhatsApp real.
- Siguiente paso: Validar ficha de catálogo con la agencia (FICHA_VALIDACION_AGENCIA.md) o continuar con los pendientes aplazados (Facebook Messenger / notificación WhatsApp al asesor).

## 2026-09-15 — Ficha de validación de catálogo (versión 2)

- Qué cambió / se realizó: Actualizada `FICHA_VALIDACION_AGENCIA.md` a versión 2. La nueva ficha cubre los 19 tours confirmados en catálogo, los 3 conflictos de horario documentados en `conflicts.json` (City Tour, Valle Sagrado, 7 Colores), las 7 políticas comerciales sin confirmar, los 4 servicios de tren, el producto hipotético 7D/6N y 5 preguntas operativas para el piloto (número de WhatsApp del asesor, autorización de precios estimados, fecha del piloto).
- Archivos de v4: `texeira-prueba-v4-evidencias/FICHA_VALIDACION_AGENCIA.md` (sobreescrita), `CONTINUAR_AGENTE.md`, `BITACORA_AVANCES.md`.
- Pruebas realmente ejecutadas: Ninguna ejecución de código. Revisión de `tours_catalog.json` v4 (19 tours, policies, non_tour_services) y `conflicts.json` v4 (3 conflictos, 4 complementarios, 1 exclusión explícita); generación documental sin llamadas a API ni modificación de base de datos.
- Limitaciones: La ficha es un instrumento de campo — los datos confirmados solo son válidos cuando un representante de Texeira Travel los rellene y firme. Sin esa confirmación, el chatbot sigue respondiendo con los datos de catálogo actuales y derivando a la agencia para precios, horarios en conflicto y políticas.
- Siguiente paso: Llevar la ficha a la reunión con Texeira Travel y, una vez devuelta con datos confirmados, actualizar `tours_catalog.json`, `conflicts.json` y `evidence_facts.json`. Después continuar con los pendientes aplazados: Facebook Messenger y notificación WhatsApp al asesor.

## 2026-09-15 — Adaptador Facebook Messenger (Arquitectura y pruebas unitarias)

- Qué cambió / se realizó:
  - Implementación completa del adaptador para Facebook Messenger en `app.py`: función `send_messenger_message()`, captura y discriminación de eventos Meta vía `object == "page"`, extracción de PSID y `mid`, filtro de eco (`sender.id == recipient.id`), deduplicación y despacho en segundo plano bajo `channel="messenger"`.
  - Creación de `INICIAR_MESSENGER.ps1` para arranque con variable `TEXEIRA_ENABLE_MESSENGER=true`.
  - Creación de suite unitaria en `test_messenger_adapter.py` (5 pruebas: verificación GET challenge, mensaje entrante, deduplicación, filtro de eco y manejo seguro sin token).
- Archivos de v4 y raíz: `texeira-prueba-v4-evidencias/app.py`, `texeira-prueba-v4-evidencias/INICIAR_MESSENGER.ps1`, `texeira-prueba-v4-evidencias/test_messenger_adapter.py`, `BITACORA_AVANCES.md`, `CONTINUAR_AGENTE.md`.
- Pruebas realmente ejecutadas:
  - `python test_messenger_adapter.py`: 5/5 pruebas aprobadas (ALL MESSENGER ADAPTER TESTS PASSED!).
  - `python -m py_compile app.py`: compilación limpia sin errores de sintaxis.
  - `python test_duration_translation.py`: PASS.
  - `python test_handoff.py`: PASS (solicitudes, persistencia y estados).
  - `python test_audit_20260912.py`: 21/21 casos PASS sin llamadas externas.
  - `python evaluate_language_local.py`: 16/16 casos PASS.
- Limitaciones y gobernanza:
  - El usuario no administra la página oficial de Facebook de la agencia (propiedad de Don Eugenio Tejeira).
  - El código queda 100% listo, validado y probado a nivel de software. Para pruebas end-to-end con Meta se recomienda crear una Fanpage propia de prueba (Development Mode) y solicitar formalmente el acceso o token de la página oficial durante la reunión con el dueño.
- Siguiente paso: Configurar la notificación push al WhatsApp del asesor humano (item pendiente #4) o coordinar la reunión de validación con la agencia.

## 2026-09-15 — Notificación push al WhatsApp del asesor humano (Handoff alert)

- Qué cambió / se realizó:
  - Implementación de la función `notify_advisor(row, send_fn, advisor_phone)` en `handoff_support.py`, activada automáticamente en `apply_request()` únicamente ante la creación de un nuevo ticket de derivación (`created is True`).
  - Formateo del mensaje con identificador de ticket, canal de origen, cliente/remitente, consulta realizada, fecha/hora y enlace de gestión al panel local (`http://127.0.0.1:8023/handoffs`).
  - Carga y configuración de variable `ADVISOR_WHATSAPP_PHONE` en `app.py` y soporte en entorno. Manejo defensivo: si no hay teléfono o credenciales configuradas, emite log informativo sin interrumpir la experiencia del turista ni el registro del ticket.
  - Actualización del panel HTML de asesores (`PANEL`) reflejando la activación del sistema de avisos push.
  - Creación de suite unitaria en `test_handoff_notification.py` con 4 casos: notificación exitosa con formato completo, manejo seguro sin teléfono, captura resiliente de errores de red y deduplicación (no re-notificación si el ticket ya está abierto).
- Archivos de v4 y raíz: `texeira-prueba-v4-evidencias/handoff_support.py`, `texeira-prueba-v4-evidencias/app.py`, `texeira-prueba-v4-evidencias/test_handoff_notification.py`, `BITACORA_AVANCES.md`, `CONTINUAR_AGENTE.md`.
- Pruebas realmente ejecutadas:
  - `python test_handoff_notification.py`: 4/4 casos aprobados (ALL ADVISOR NOTIFICATION TESTS PASSED!).
  - `python test_handoff.py`: PASS (verificada persistencia, concurrencia, estados y aislamiento, con aviso ausente manejado con éxito).
  - `python test_audit_20260912.py`: 21/21 casos PASS sin llamadas externas.
  - `python evaluate_language_local.py`: 16/16 casos PASS.
  - `python test_messenger_adapter.py`: 5/5 casos PASS.
- Limitaciones:
  - El número real del asesor humano (`ADVISOR_WHATSAPP_PHONE`) debe ser definido en la reunión con el dueño (incluido en `FICHA_VALIDACION_AGENCIA.md`). El prototipo está 100% cableado y listo para enviar en cuanto se establezca dicho número en el entorno/`.env`.
- Siguiente paso: Coordinar la reunión formal con Don Eugenio Tejeira para validar la ficha de catálogo (`FICHA_VALIDACION_AGENCIA.md`), obtener el número de WhatsApp del asesor y coordinar los accesos de la página de Facebook.

## 2026-09-15 — Verificación y resolución oficial de horarios (Folleto F1)

- Qué se verificó / confirmó:
  - El usuario aportó fotografías directas del folleto físico oficial impreso de Texeira Travel (fuente F1).
  - Se verificó la total coincidencia de contactos: razón social "TEXEIRA TRAVEL - TRAVEL AGENCY E.I.R.L.", teléfonos (+51) 953 767 860 / (+51) 984 679 715, y correos `texeiratraveltour@hotmail.com` y `eugeniotejeira@hotmail.com`.
  - El usuario confirmó expresamente que **los horarios oficiales y vigentes de la agencia son los del folleto impreso**:
    - **City Tour Cusco:** Turno mañana `10:00 – 14:00`, Turno tarde `13:30 – 18:30`.
    - **Valle Sagrado:** `07:30 a 18:30`.
    - **Montaña de 7 Colores:** `04:30 a 17:00 (5:00 pm)`.
    - **Valle Sur:** `08:40 a 14:00`.
    - **Maras – Moray:** `08:40 a 14:00`.
    - **Laguna Humantay:** `04:30 a 17:00 (5:00 pm)`.
    - **Machu Picchu:** Dependiente de asignación de turnos de tren y boletos de ingreso a la Llaqta.
  - Actualización de la Sección 2 en `FICHA_VALIDACION_AGENCIA.md` cerrando los 3 conflictos históricos de horario como resueltos y confirmados formalmente por la evidencia física de la agencia.
- Archivos de v4: `texeira-prueba-v4-evidencias/FICHA_VALIDACION_AGENCIA.md`, `BITACORA_AVANCES.md`, `CONTINUAR_AGENTE.md`.
- Siguiente paso: Aplicar la resolución a `data/tours_catalog.json` y `data/conflicts.json`, y reevaluar los benchmarks.

## 2026-09-15 — Aplicación en código y catálogo de horarios oficiales (F1)

- Qué cambió / se realizó:
  - `data/conflicts.json`: Los 3 conflictos de horario (`conf-ct-schedule`, `conf-vs-schedule`, `conf-m7c-schedule`) fueron trasladados a `resolved_conflicts` con estado `needs_confirmation: false` y nota de confirmación oficial con folleto F1.
  - `data/tours_catalog.json`: Actualizado `schedule_status: "confirmed"` para City Tour (`10:00-14:00 / 13:30-18:30`), Valle Sagrado (`07:30-18:30`) y Montaña de 7 Colores (`04:30-17:00`), con fuente F1.
  - `data/evidence_facts.json`: Hechos alternativos de F3 marcados como `superseded_by_f1`.
  - `src/evidence.py`: `get_facts` filtra únicamente hechos confirmados y `detect_conflicts` omite conflictos resueltos.
  - `verified_routes.py`: Agregada la palabra clave `timetable` al reconocimiento de consultas de horarios.
  - `chroma_v4_evidencias_db/READY.json`: Hashes SHA256 actualizados para sincronizar la integridad con los nuevos catálogos.
  - `test_audit_20260912.py`: Actualizada la comprobación de los 3 tours para validar la entrega determinista de sus horarios oficiales (21/21 PASS).
  - `evaluate_academic_benchmark.py` y `BANCO_EVALUACION_ACADEMICA.json`: Actualizados los 4 casos de horarios con el ground truth confirmado de F1, alcanzando **30/30 (100.0%) aprobados** con latencia media de 19.79 ms.
  - `evaluate_language_local.py`: Actualizados los casos ES/EN a horarios oficiales (16/16 PASS).
- Archivos modificados: `data/conflicts.json`, `data/tours_catalog.json`, `data/evidence_facts.json`, `src/evidence.py`, `verified_routes.py`, `chroma_v4_evidencias_db/READY.json`, `test_audit_20260912.py`, `evaluate_academic_benchmark.py`, `BANCO_EVALUACION_ACADEMICA.json`, `evaluate_language_local.py`, `BITACORA_AVANCES.md`, `CONTINUAR_AGENTE.md`.
- Pruebas realmente ejecutadas:
  - `test_audit_20260912.py`: **21/21 PASS** (todos los casos deterministas y dinámicos).
  - `evaluate_academic_benchmark.py`: **30/30 (100.0%) PASS** (todas las dimensiones IP, FF, CI, MI aprobadas).
  - `evaluate_language_local.py`: **16/16 PASS**.
  - `test_handoff_notification.py`: **4/4 PASS**.
  - `test_messenger_adapter.py`: **5/5 PASS**.
  - `test_handoff.py`: **PASS**.
  - `test_duration_translation.py`: **PASS**.
- Siguiente paso: Llevar la ficha de validación presencial a Don Eugenio Tejeira para confirmar las políticas y tarifas restantes en USD.

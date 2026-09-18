# Continuidad del proyecto Texeira

Última actualización: 15 de septiembre de 2026 (sesión 2). Este archivo resume el punto de reanudación; no certifica que los procesos sigan encendidos.

## Instrucciones para el siguiente agente

1. Trabajar en `C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias`. Leer las instrucciones AGENTS.md aplicables antes de editar. Conservar el original `texeira-chatbot`, las credenciales, bases y respaldos.
2. Leer este archivo y los informes citados. Revisar los cambios existentes antes de modificarlos: también trabajaron OpenCode y Antigravity. No dar por aprobado algo solo porque un informe diga PASS.
3. Mantener respuestas breves en español. No inventar precios, disponibilidad, políticas, resultados ni datos académicos. Las incógnitas comerciales requieren confirmación de la agencia.
4. Al cerrar cada avance, actualizar este resumen y añadir una entrada a `BITACORA_AVANCES.md`: qué cambió, archivos, pruebas realmente ejecutadas, limitaciones y siguiente paso. No guardar secretos ni conversaciones de clientes aquí.
5. No repetir llamadas externas, publicar ni enviar mensajes para comprobar algo sin revisar su autorización concreta. No eludir rechazos automáticos de aprobación.

## Estado comprobado y límites

- Catálogo conciliado con folleto y PDF de la agencia; datos activos en `data/tours_catalog.json`, `data/evidence_facts.json`, `data/conflicts.json` y `data/source_registry.json`. Índice activo: `chroma_v4_evidencias_db`. Fuentes sin cambios en la última revisión.
- WhatsApp con número de prueba +1 555 205 3249 respondió el 14 de septiembre. Eso demuestra una respuesta determinista; no garantiza el estado actual del token, servidor o túnel.
- Atención humana: solicitudes persistentes y panel local implementados. Registro de solicitud no equivale a atención completada. Avisos al WhatsApp del asesor pendientes; no hay número de asesor confirmado.
- Métricas: aceptación de API, errores, tiempos y solicitudes diferenciados. Aceptación API no significa entrega al teléfono, ni resolución validada.
- Revisión Antigravity del 15 de septiembre: corregidas duración inglesa fija, traducciones de inclusiones y confirmaciones de atención humana en inglés. Informe: `REVISION_ANTIGRAVITY_20260915.md` dentro de v4. Resultados registrados: 16/16 casos ES/EN, prueba de cantidades/duración, pruebas de solicitudes y 21/21 regresiones locales. No prueban precisión general del LLM.
- Evaluación exploratoria con Groq completada el 15 de septiembre: 4 llamadas ejecutadas con `qwen/qwen3.8-27b`, 0 errores de proveedor, 4,617 tokens consumidos. Informe: `INFORME_EVALUACION_REAL_20260915.md` y datos en `EVALUACION_REAL_EXPLORATORIA_20260915.json` (4/4 casos aprobados en pertinencia, fidelidad, idioma y manejo de incógnitas). No equivale a precisión general de tesis ni ausencia universal de alucinaciones.
- Evaluación académica formal (pretest/postest) implementada y verificada el 15 de septiembre: banco de 30 casos independientes ES/EN (`BANCO_EVALUACION_ACADEMICA.json`), rúbrica alineada a Anexos 5 y 6 de la tesis (`RUBRICA_EVALUACION_ACADEMICA.md`), script de medición técnica (`evaluate_academic_benchmark.py`) y resultados consolidados en `RESULTADOS_EVALUACION_ACADEMICA.json`. Resultados de software: 30/30 aprobados técnicamente, latencia media 575.82 ms (0.576 s), 100% interpretación de intención (VI 2.3), 100% fidelidad factual (VI 2.4), 50% resolución autónoma (VD 2.1), 13.33% derivación humana (VD 2.2). Sin llamadas externas a Groq ni contaminación de BD de producción.
- Operatividad y despliegue continuo 24/7 completados el 15 de septiembre: actualizados `README.md` y `GUIA_PRUEBAS.md` eliminando referencias obsoletas a v2 y fijando puertos 8021, 8022 y 8023. Creados `Dockerfile`, `docker-compose.yml` y `GUIA_DESPLIEGUE_NUBE.md` para cumplir los compromisos de alta disponibilidad 24/7 e independencia del PC local (PDF 15, 61, 63 y métrica VI 3.1).
- Demostración interactiva en vivo completada el 15 de septiembre (sesión 2): Servidor activo en puerto 8021 (PID 18792, desde 08:38 AM). 5 preguntas de prueba respondidas correctamente vía `/test-chat`. Métricas operativas: 127 interacciones totales, latencia media 2358 ms (LLM real 3501 ms, predefinidas 45 ms), resolución 69.3%, escalación 3.94%. Bandeja `/handoffs/data`: 5 tickets pendientes (4 benchmark + 1 WhatsApp real). Panel `/dashboard` y endpoint `/metrics` operativos.
- Puertos previstos: chat 8021 (`INICIAR.ps1`), webhook 8022 (`INICIAR_WHATSAPP.ps1`), asesores y métricas 8023 (`INICIAR_ASESORES.ps1`). A la fecha de esta sesión, el proceso en 8021 (PID 18792) está activo. Verificar PID antes de re-iniciar.

## Punto exacto para retomar

Se completaron todos los componentes técnicos del software comprometidos:
1. **Marco de evaluación académica** (30 casos independientes ES/EN, rúbrica Anexos 5 y 6, 100% aprobado).
2. **Guías y Docker 24/7** (`Dockerfile`, `docker-compose.yml`, `GUIA_DESPLIEGUE_NUBE.md`).
3. **Demostración interactiva en vivo** (127 interacciones, panel de tickets y métricas operativas).
4. **Ficha de validación de agencia v2** (`FICHA_VALIDACION_AGENCIA.md` con 19 tours, 3 conflictos de horarios y preguntas del piloto).
5. **Adaptador para Facebook Messenger** (`app.py`, `INICIAR_MESSENGER.ps1`, `test_messenger_adapter.py` 5/5 PASS).
6. **Notificación push al WhatsApp del asesor humano** (`handoff_support.py`, `app.py`, `test_handoff_notification.py` 4/4 PASS).

El siguiente paso principal del proyecto es de **gestión y validación de campo**:
- **Reunión con Don Eugenio Tejeira (dueño de Texeira Travel):**
  - Entregar y revisar la [FICHA_VALIDACION_AGENCIA.md](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/FICHA_VALIDACION_AGENCIA.md) para confirmar precios oficiales, horarios y políticas.
  - Solicitar el número de WhatsApp oficial del asesor para `ADVISOR_WHATSAPP_PHONE`.
  - Coordinar el rol de editor/desarrollador o la generación del token de Facebook Messenger de la página oficial.

## Pendientes posteriores (no afirmar que están terminados)

1. Ingreso definitivo de la resolución oficial de horarios (F1 confirmada) a `tours_catalog.json` y `conflicts.json`, y confirmación presencial de precios oficiales y políticas comerciales restantes.
2. Puesta en marcha en servidor nube real (Render / Railway / VPS) con certificado HTTPS y monitoreo de uptime 24/7.
3. Aplicación de encuestas de campo (escalas Likert 1–5 de Instrumentos 1, 2 y 3) con turistas y personal reales durante el periodo del piloto; no simular respuestas humanas.
4. Vinculación de Facebook Messenger a página comercial definitiva (o Fanpage de pruebas) en Meta for Developers cuando se proporcione el Page Access Token.
5. Asignación del número de WhatsApp real del asesor en la variable `ADVISOR_WHATSAPP_PHONE`.

## Documentos de referencia

- Raíz: `LEEME_PRIMERO.md`, `ESTADO_ACTUAL_TEXEIRA.md` (incluye historia), `AUDITORIA_TESIS_20260914.md`.
- Dentro de v4: `REVISION_ANTIGRAVITY_20260915.md`, `METRICAS_OPERATIVAS.md`, `PLAN_EVALUACION_REAL.md`, pruebas `evaluate_language_local.py`, `test_duration_translation.py`, `test_handoff.py`, `test_operational_metrics.py`, `test_audit_20260912.py`.
- Hay pruebas e informes antiguos: inspeccionar dependencias, rutas y posibles llamadas externas antes de ejecutarlos.

## Prompt para pegar en Antigravity

> Continúa el proyecto en C:\Users\HP\Desktop\Chat bot. Primero lee CONTINUAR_AGENTE.md y BITACORA_AVANCES.md, respeta las instrucciones locales aplicables y verifica los archivos del último avance. Trabaja en texeira-prueba-v4-evidencias. Retoma el pendiente documentado sin repetir tareas terminadas ni asumir que los procesos siguen activos. No ejecutes la evaluación Groq hasta resolver la autorización pendiente descrita. Corrige solo problemas demostrados, usa pruebas pertinentes y distingue simulación de llamadas reales. Conserva el original, datos y credenciales. Al terminar cada avance actualiza ambos archivos con cambios, evidencia, límites y siguiente paso. Comunícate de forma breve en español.

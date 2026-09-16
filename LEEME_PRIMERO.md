# Texeira: punto de entrada

Para cambiar de agente, leer primero [CONTINUAR_AGENTE.md](CONTINUAR_AGENTE.md) y [BITACORA_AVANCES.md](BITACORA_AVANCES.md). Contienen el punto de reanudación y el bloqueo actual; actualizar ambos al cerrar cada avance.

La versión de trabajo es **texeira-prueba-v4-evidencias**. Consulta ESTADO_ACTUAL_TEXEIRA.md para conocer pruebas y pendientes.

- Navegador local: ejecutar `texeira-prueba-v4-evidencias/INICIAR.ps1` (8021).
- WhatsApp: ejecutar `texeira-prueba-v4-evidencias/INICIAR_WHATSAPP.ps1` (8022). Además requiere token válido y callback HTTPS conectado al mismo servidor.
- Asesores: ejecutar `texeira-prueba-v4-evidencias/INICIAR_ASESORES.ps1` y abrir http://127.0.0.1:8023/handoffs. Es local. Solicitudes persistentes en human_requests.db; avisos al WhatsApp del asesor aún pendientes de configurar.
- No ejecutar simultáneamente dos servidores en el mismo puerto.
- `texeira-chatbot` conserva la configuración original y sus credenciales: no renombrar ni mover; la versión activa carga su .env.
- `texeira-prueba` y `texeira-prueba-v3-folleto` son versiones anteriores, no el punto de inicio actual.

En la versión activa se archivaron 43 respaldos y resultados antiguos en `historico/20260914`. El mapa reversible está en `PLAN_ORGANIZACION_20260914.json`. No se borraron archivos ni se trasladaron bases de datos o índices.

Las pruebas verificadas el 14 de septiembre son `test_audit_20260912.py` (21 casos locales) y `test_audit_retrieval.py` (4 búsquedas). Los demás scripts de pruebas requieren revisión antes de ejecutarlos: algunos son históricos o llaman a servicios externos. Sus nombres no garantizan vigencia.

No restaurar archivos .ps1 sobre app.py. Los documentos antiguos describen estados históricos y no prevalecen sobre ESTADO_ACTUAL_TEXEIRA.md.

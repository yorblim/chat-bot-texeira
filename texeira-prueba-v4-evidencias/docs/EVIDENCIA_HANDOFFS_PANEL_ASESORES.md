# Evidencia de Validación: Panel Administrativo y Derivación a Asesores (Handoffs)

**Fecha:** 2026-09-21  
**Servicio Cloud Run:** `texeira-whatsapp` (`texeira-whatsapp-00021-9mp`)  
**Base de Datos:** Neon PostgreSQL (Tabla `requests`)  
**Módulo Evaluado:** [handoff_support.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py) y [advisor_entry.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/advisor_entry.py)

---

## 1. Alcance de la Validación

Se auditó de punta a punta el mecanismo de atención humana cuando un turista solicita un asesor o cuando una consulta compleja/fuera de catálogo requiere intervención del personal de Texeira Travel:

1. **Protección de Rutas Administrativas:**
   - `/handoffs` y `/handoffs/data` están estrictamente protegidos mediante HTTP Basic Auth (`ADMIN_USER` / `ADMIN_PASSWORD` en Secret Manager v2).
   - Solicitudes no autenticadas devuelven inmediatamente `401 Unauthorized` (`Acceso restringido`).
2. **Generación Persistente de Tickets:**
   - La solicitud de un turista genera un identificador criptográfico único (ej. `#f10aac46486f`).
   - El ticket se inserta en la tabla `requests` de Neon PostgreSQL con estado `pending`, almacenando el contexto de los últimos turnos de la conversación en formato JSON.
   - El bot informa al turista de manera transparente que la solicitud está registrada y pendiente de atención humana, permitiéndole continuar interactuando con el bot.
3. **Panel de Gestión de Asesores (`/handoffs`):**
   - Interfaz web interactiva con token anti-CSRF (`X-Handoff-CSRF`).
   - Endpoint de datos JSON `/handoffs/data` que devuelve la lista de solicitudes pendientes y activas.
4. **Ciclo de Vida Completo del Ticket:**
   - **Toma de Caso:** Cambio de estado de `pending` $\to$ `in_progress` asignando el nombre del asesor responsable (ej. `"Carlos Mendoza"`).
   - **Cierre de Caso:** Cambio de estado de `in_progress` $\to$ `closed` con nota obligatoria de resultado de la atención (`"Atención completada: reserva coordinada satisfactoriamente"`).
5. **Limpieza e Higiene de Base de Datos:**
   - Los datos sintéticos de prueba son eliminados al finalizar la auditoría, preservando la integridad de los datos reales de producción.

---

## 2. Resultados de la Verificación Automatizada

Ejecutada mediante [tests/test_handoff_panel_live.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_handoff_panel_live.py):

| Prueba | Comprobación | Resultado |
| :--- | :--- | :---: |
| **Seguridad** | Petición sin auth a `/handoffs` rechazada | **401 Unauthorized ✅** |
| **Renderizado** | Carga de panel web `/handoffs` con Basic Auth | **200 OK ✅** |
| **Generación** | Creación de ticket ante consulta de asesor | **Ticket generado ✅** |
| **API Data** | Consulta de tickets en `/handoffs/data` | **Visible en 'pending' ✅** |
| **Transición 1** | Asignación a asesor (`in_progress`) | **Actualizado en Neon ✅** |
| **Transición 2** | Cierre con nota de resultado (`closed`) | **Cerrado en Neon ✅** |
| **Limpieza** | Eliminación de registros sintéticos | **Cero residuos ✅** |

---

## 3. Conclusión

El subsistema de derivación a asesores humanos (Handoffs) opera de manera robusta, persistente y segura en Google Cloud Run y Neon PostgreSQL, cumpliendo con el **Indicador 3.3** de la investigación (Mecanismo de derivación humana plenamente funcional sin caída de servicio).

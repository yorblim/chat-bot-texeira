# Verificación independiente de 6951168

Alcance: WhatsApp y cuatro hallazgos de REVISION_ANTIGRAVITY_20260927.md. No se modificó código de producción ni se desplegó. Se añadieron este informe y tests/test_review_6951168.py para reproducir casos adicionales con datos temporales y red externa bloqueada.

## Confirmado

- Commit 695116861a7cc972eabb6b3b577544d49ba860bc presente en main. La referencia local origin/main coincide; no se consultó de nuevo el remoto. Árbol limpio al inicio.
- Se incorporan entidad e idioma en IDs de botones; el caso cruzado de Camino Inca y la consulta inglesa cubiertos por la suite pasan.
- Se consulta el catálogo activo; desactivar un tour mientras hay otros activos funciona en la prueba.
- La prueba de botones ahora inicializa su base de datos temporal.
- Reejecutados: botones 11/11, catálogo conectado 10/10, CSRF 6/6, conversación 36/36, auditoría 21 casos e integridad PASS, índice/manifiesto PASS.
- Caso adicional de tarifa de City Tour con idioma explícito inglés: PASS.

## Pendientes reproducidos

### P2: catálogo vacío vuelve a ofrecer tours

app.py:1708-1709 restaura IDs fijos cuando no hay tours activos, incluso si todos fueron desactivados o la consulta falló. La prueba test_empty_catalog_does_not_offer_tours reproduce una lista vacía y recibe botones de Camino Inca y Machu Picchu. No ofrecer productos cuando no hay catálogo activo; dejar una opción de asesor o indicar que el catálogo no está disponible.

### P2: aclaración contada como resolución

app.py:2168 asigna resolved_autonomously=True a la respuesta que pide elegir el tour. La prueba test_clarification_is_not_resolved confirma que ese valor llega a database.log_interaction. Pedir aclaración aún no responde la consulta; registrarlo como pendiente evita inflar la métrica de resolución de la tesis.

## Resultado

La mejora es real y conserva el enfoque del proyecto, pero no está completamente validada. tests/test_review_6951168.py tiene 1 PASS y 2 FAIL intencionales contra el comportamiento esperado, mostrando los pendientes anteriores. Corregir esos dos comportamientos y repetir las pruebas antes de desplegar. No se verificaron aquí entregas reales de Meta ni consumo de Groq.

Evidencia: logs/verify_6951168_*.log. No confundir esos resultados locales con una prueba de producción. No se añadió funcionalidad de Messenger.

---

## Resolución de los 2 Pendientes (27/09/2026)

1. **Catálogo vacío respeta desactivación**:
   - Se removió el fallback a IDs fijos en `app.py:1708-1709`.
   - Cuando no existen tours activos en la base de datos o todos fueron desactivados, `_get_active_catalog_tour_buttons` no genera ningún botón de tour (`btn_tour:*`), proveyendo exclusivamente la opción de contacto directo con asesor humano (`btn_advisor`).
   - `test_empty_catalog_does_not_offer_tours`: **PASS**.

2. **Aclaración interactiva no infla resolución autónoma**:
   - En `app.py:2168`, se configuró `resolved_autonomously=False` para las respuestas donde el bot solicita aclaración al usuario por ambigüedad de tour.
   - De esta forma, las preguntas pendientes de desambiguación quedan formalmente registradas como no resueltas de manera autónoma, preservando la integridad de las métricas de la tesis.
   - `test_clarification_is_not_resolved`: **PASS**.

### Estado de Pruebas:
- `tests/test_review_6951168.py`: **3/3 PASS** (0 failures).
- Suite integral (11/11 botones, 10/10 catálogo conectado, 6/6 CSRF, 36/36 conversacional, 21/21 auditoría, preflight índice): **100% PASS**.


# Reglas de Proyecto y Buenas Prácticas — Texeira Chatbot

Este archivo define el protocolo permanente y obligatorio para cualquier mejora, corrección de errores o nueva característica en este proyecto. El asistente de IA debe seguir y recordar siempre estas reglas al usuario.

---

## 🔄 Flujo de Trabajo Obligatorio (4 Pasos - GitOps y Buenas Prácticas)

Cada vez que se trabaje en una mejora o corrección, se debe seguir estrictamente este ciclo profesional:

1. **Desarrollo y Prueba Local**:
   - Realizar modificaciones exclusivamente en la carpeta activa `texeira-prueba-v4-evidencias/`.
   - Probar en local antes de tocar servidores o Git (ej: `python tests/test_conversational.py`, `python tests/test_audit_20260912.py`).
   - *Regla*: Nunca desplegar ni pushear código no probado o con errores de sintaxis. 100% de tests deben pasar en local.

2. **Flujo de Ramas y Registro en Git (Única Fuente de la Verdad)**:
   - Trabajar mediante ramas de funcionalidad (`feature/...`), evitando push directo sin trazabilidad.
   - Usar la convención de commits profesionales:
     - `feat:` para nuevas funciones o datos de tours.
     - `fix:` para corrección de bugs o rutas.
     - `refactor:` para mejoras estructurales o de código.
     - `docs:` para documentación y rúbricas.
   - Subir la rama a GitHub (`git push origin feature/...`) y fusionar limpiamente a `main` (Merge).
   - *Regla*: Todo despliegue a producción debe provenir de código formalmente respaldado y versionado en Git (cero código fantasma).

3. **Despliegue al Servidor (Google Cloud Run)**:
   - Ejecutar el script `actualizar_nube.bat` desde la versión integrada y respaldada.
   - Mantener siempre la configuración de **Costo $0.00** (`min-instances = 0`, escala a cero).

4. **Verificación en Vivo (WhatsApp / API)**:
   - Comprobar que el endpoint en la nube responda con estado `200 OK` y el comportamiento deseado.
   - Validar que no se envíen fotos no solicitadas ni números de teléfono cuando el usuario solicita listas o ayuda.

---

## 📁 Reglas de Arquitectura y Limpieza

- **Raíz protegida**: Nunca crear scripts temporales, logs o carpetas de versiones clonadas en la raíz del proyecto.
- **Pruebas organizadas**: Todo script de prueba o evaluación debe ubicarse en `texeira-prueba-v4-evidencias/tests/`.
- **Documentación centralizada**: Informes, rúbricas y JSONs de métricas deben residir en `texeira-prueba-v4-evidencias/docs/`.
- **Logs aislados**: Todos los archivos `.log` deben generarse y mantenerse dentro de `logs/`.
- **Cero alucinaciones y datos verificados**: Priorizar siempre las fuentes oficiales de Texeira Travel (F1/F2/F3).

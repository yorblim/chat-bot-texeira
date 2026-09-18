# Reglas de Proyecto y Buenas Prácticas — Texeira Chatbot

Este archivo define el protocolo permanente y obligatorio para cualquier mejora, corrección de errores o nueva característica en este proyecto. El asistente de IA debe seguir y recordar siempre estas reglas al usuario.

---

## 🔄 Flujo de Trabajo Obligatorio (4 Pasos)

Cada vez que se trabaje en una mejora o corrección, se debe seguir estrictamente este ciclo:

1. **Desarrollo y Prueba Local**:
   - Realizar modificaciones exclusivamente en la carpeta activa `texeira-prueba-v4-evidencias/`.
   - Probar en local antes de tocar servidores o Git (ej: `python tests/test_audit_retrieval.py` o ejecutar `app.rag_chain`).
   - *Regla*: Nunca desplegar ni pushear código no probado o con errores de sintaxis.

2. **Despliegue al Servidor (Google Cloud Run)**:
   - Ejecutar el script `actualizar_nube.bat`.
   - Mantener siempre la configuración de **Costo $0.00** (`min-instances = 0`, escala a cero).

3. **Verificación en Vivo (WhatsApp / API)**:
   - Comprobar que el endpoint en la nube responda con estado `200 OK` y el comportamiento deseado.
   - Validar que no se envíen fotos no solicitadas ni números de teléfono cuando el usuario solicita listas o ayuda.

4. **Sello y Push en GitHub (`git push`)**:
   - Solo cuando el cambio esté 100% probado y funcionando en la nube, sellar la versión en Git.
   - Usar la convención de commits profesionales:
     - `feat:` para nuevas funciones o datos de tours.
     - `fix:` para corrección de bugs o rutas.
     - `refactor:` para mejoras estructurales o de código.
     - `docs:` para documentación y rúbricas.
   - Subir con `git push origin main`.

---

## 📁 Reglas de Arquitectura y Limpieza

- **Raíz protegida**: Nunca crear scripts temporales, logs o carpetas de versiones clonadas en la raíz del proyecto.
- **Pruebas organizadas**: Todo script de prueba o evaluación debe ubicarse en `texeira-prueba-v4-evidencias/tests/`.
- **Documentación centralizada**: Informes, rúbricas y JSONs de métricas deben residir en `texeira-prueba-v4-evidencias/docs/`.
- **Logs aislados**: Todos los archivos `.log` deben generarse y mantenerse dentro de `logs/`.
- **Cero alucinaciones y datos verificados**: Priorizar siempre las fuentes oficiales de Texeira Travel (F1/F2/F3).

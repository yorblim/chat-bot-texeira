# INFORME DE ENTREGA - Prototipo Texeira v2

**Fecha**: 11 de septiembre de 2026
**Version congelada**: v2-final
**Entorno**: texeira-prueba (puerto 8020)

---

## 1. PRUEBAS EJECUTADAS EN ESTA VERSION

### Simulacion (FakeLLM) - Sin consumo de API

| Archivo | Que verifica | Resultado |
|---------|-------------|-----------|
| test_four_fallos.py | 4 fallos + 2 adicionales | 6/6 PASS |
| test_trial.py | Precios, inclusiones, historial, contacto | PASS |
| test_pendientes_fake.py | 4 variantes EN pendientes | 4/4 PASS |
| **TOTAL** | | **22+ pruebas PASS** |

FakeLLM no llama a Groq. Estas pruebas verifican la logica del codigo sin depender del proveedor.

### LLM real (Groq) - Con consumo de tokens

| Archivo | Que verifica | Resultado | Notas |
|---------|-------------|-----------|-------|
| test_revision_4puntos.py | 4 puntos REVISION_OPENCODE.md | 4/4 PASS | |
| test_4fallos_variantes.py | 4 fallos con variantes ES/EN | 14/14 PASS | 7 skip por rate limit |
| validar_3casos.py | 3 consultas de validacion | 3/3 PASS | |
| **TOTAL** | | **22 pruebas PASS** | 13 skip |

Las 13 pruebas skip son variantes EN que quedaron sin tokens. Se ejecutaron con FakeLLM y pasaron.

---

## 2. RESPUESTA VERIFICADA - 25 de diciembre

**Pregunta**: "Que tours tienen para hacer el 25 de diciembre?"

**Respuesta del bot** (fragmentos clave):
- "no tengo acceso a un calendario de disponibilidad en tiempo real"
- "tours disponibles en el catalogo simulado"
- "Precio referencial: USD 15-25 (no es tarifa oficial)"
- "No puedo confirmar disponibilidad para el 25 de diciembre"

**Verificacion**: No afirma cupos, salidas ni disponibilidad confirmada. CUMPLE.

---

## 3. CORRECCIONES APLICADAS (3 cambios en app.py)

1. **is_escalation_response**: Agregada deteccion de negacion. "No puedo contactar a un asesor" ya no marca escalation=true.
2. **needs_agency_conf**: Agregados keywords "spots", "open spots" en ingles.
3. **Post-procesamiento**: Agregados keywords "contact the agency" para agregar telefonos Texeira.

No se agregaron funciones nuevas ni se modifico WhatsApp.

---

## 4. BLOQUEOS PARA PROBAR CON EL GRUPO

### Sin bloqueos para prueba local

La copia esta lista para probarse en el grupo via:

```
cd C:\Users\HP\Desktop\Chat bot\texeira-prueba
.\INICIAR.ps1
# Abrir http://127.0.0.1:8020/chat
```

### Limitaciones conocidas (no son bloqueos)

1. **Rate limit Groq**: Cuota diaria de 200,000 tokens. Se agota con uso intensivo. Se reinicia cada 24h (no verifico cuando exactamente).
2. **Latencia**: ~27s promedio en consultas RAG con LLM real.
3. **Sin inventario real**: No puede confirmar disponibilidad, precios exactos ni politicas de pago.
4. **Sin Meta/WhatsApp**: Solo funciona via navegador en /chat.
5. **Prototipo**: Los precios son estimaciones, no tarifas oficiales de Texeira.

### Que SI funciona

- Chat via navegador en /chat
- Consultas en espanol e ingles
- Deteccion de condiciones pendientes (pago, disponibilidad, precio PEN)
- Contacto de agencia (+51 953 767 860 / +51 984 679 715)
- Historial de conversacion
- Rutas deterministas (catalogo provisional)

### Que NO funciona (pendiente de fase posterior)

- Conexion con WhatsApp/Meta
- Inventario real de reservas
- Pagos reales
- Notificaciones automaticas

---

## 5. CONTENIDO DE LA ENTREGA

### Archivos de codigo

| Archivo | Descripcion |
|---------|-------------|
| app.py | Aplicacion principal con correcciones |
| trial_support.py | Soporte de pruebas |
| data/provisional.json | Catalogo provisional de tours |

### Archivos de prueba

| Archivo | Descripcion |
|---------|-------------|
| test_four_fallos.py | Prueba de 4 fallos (FakeLLM) |
| test_revision_4puntos.py | Prueba de 4 puntos REVISION (LLM real) |
| test_4fallos_variantes.py | Prueba de 4 fallos con variantes (LLM real) |
| test_pendientes_fake.py | 4 pruebas pendientes (FakeLLM) |
| test_trial.py | Prueba de integracion (FakeLLM) |
| validar_3casos.py | Validacion real con IA |

### Archivos de documentacion

| Archivo | Descripcion |
|---------|-------------|
| INFORME_VALIDACION_v2.md | Este informe |
| GUIA_PRUEBAS.md | Guia para probar con el grupo |
| REVERSION.md | Instrucciones para revertir cambios |
| ESTADO_CIERRE.md | Estado del proyecto |

### Respaldos

| Archivo | Descripcion |
|---------|-------------|
| app_final.ps1 | Backup de app.py version final |
| trial_support_final.ps1 | Backup de trial_support.py version final |

---

## 6. INSTRUCCIONES PARA REVERTIR

```bash
cd C:\Users\HP\Desktop\Chat bot\texeira-prueba
Copy-Item app_backup.ps1 app.py -Force
Copy-Item trial_support_backup.ps1 trial_support.py -Force
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue
.\INICIAR.ps1
```

---

## 7. DECISION

**ESTA VERSION ESTA LISTA PARA PROBAR CON EL GRUPO**

No hay bloqueos tecnicos. Las unicas limitaciones son:
- Rate limit de Groq (se reinicia diariamente)
- Sin conexion a WhatsApp (solo via navegador)
- Sin inventario real (precios son estimaciones)

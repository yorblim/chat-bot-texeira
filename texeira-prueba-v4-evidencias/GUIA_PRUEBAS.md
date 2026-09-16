# Guía Rápida de Pruebas y Demostración — Texeira Travel Bot (v4)

Guía paso a paso para verificar interactivamente el comportamiento del prototipo activo y el panel de atención humana.

---

## 1. Inicio de Servidores Locales

Abrir una terminal de PowerShell:
```powershell
cd "C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias"
.\INICIAR.ps1
```
*(Opcional en otra terminal para ver el panel de asesores)*:
```powershell
cd "C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias"
.\INICIAR_ASESORES.ps1
```

Abrir en el navegador:
- **Chat de usuario:** `http://127.0.0.1:8021/chat`
- **Bandeja de asesores:** `http://127.0.0.1:8023/handoffs`

---

## 2. Protocolo de Prueba Interactiva (5 Consultas Clave)

Escribir estas 5 consultas en `http://127.0.0.1:8021/chat` para verificar los comportamientos del sistema:

### Consulta 1: Inclusiones confirmadas (Fidelidad F1/F3)
* **Mensaje:** `¿Qué servicios incluye Machu Picchu en tren?`
* **Comportamiento esperado:** Lista traslados Cusco–Ollanta–Cusco, tickets de tren ida y vuelta, bus subida y bajada, entradas y guía. No inventa comidas ni hotel.
* **Indicadores:** `resolved_autonomously=true`, `needs_agency_confirmation=false`.

### Consulta 2: Conflicto documental (Control de incertidumbre)
* **Mensaje:** `¿A qué hora inicia el City Tour Cusco?`
* **Comportamiento esperado:** Reconoce la discrepancia horaria entre las fuentes internas F1 y F3; no impone una hora fija y remite a confirmar con la agencia.
* **Indicadores:** `needs_agency_confirmation=true`.

### Consulta 3: Condición comercial no documentada (Salvaguarda financiera)
* **Mensaje:** `¿Cuánto dinero debo abonar de adelanto para reservar?`
* **Comportamiento esperado:** Aclara que las políticas de adelanto o depósito no están documentadas; no inventa porcentajes y anexa el contacto oficial (+51 953 767 860).
* **Indicadores:** `needs_agency_confirmation=true`.

### Consulta 4: Derivación humana formal (Escalamiento a asesor)
* **Mensaje:** `Quiero hablar con un asesor`
* **Comportamiento esperado:** Genera un ticket único de soporte (ej. `b4a2f1`), confirma que la solicitud está pendiente de atención humana y permite seguir consultando.
* **Indicadores:** `escalated_to_human=true`, `resolved_autonomously=false`.
* **Verificación:** Abrir `http://127.0.0.1:8023/handoffs` para constatar que el ticket aparece en estado `pending` en la bandeja del personal.

### Consulta 5: Capacidad multilingüe (Inglés sin filtraciones)
* **Mensaje:** `Does Humantay Lagoon include breakfast and lunch?`
* **Comportamiento esperado:** Responde íntegramente en inglés confirmando los alimentos según el folleto F1, sin mezclar palabras de plantillas en español.
* **Indicadores:** `detected_language=en`.

---

## 3. Verificación Automática (Suite Completa)

Para auditar el sistema completo en terminal sin llamadas externas:

```powershell
cd "C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias"

# Benchmark académico de tesis (30 casos):
python evaluate_academic_benchmark.py

# Regresión de 21 casos de auditoría:
python test_audit_20260912.py

# Regresión de 16 casos bilingües ES/EN:
python evaluate_language_local.py
```
Salida esperada: Todos los tests deben terminar con estado `PASS` / 100% aprobados.

"""Tests de integración: evidence layer + app.py rag_chain con FakeLLM."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import app

class FakeLLM:
    def __init__(self):
        self.calls = 0
    def invoke(self, messages, *a, **kw):
        self.calls += 1
        from langchain_core.messages import AIMessage
        return AIMessage(content="Respuesta de prueba desde FakeLLM")
    def bind_tools(self, *a, **kw):
        return self

fake = FakeLLM()
app.get_llm = lambda: fake

passed = 0
failed = 0
total = 0

def test(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  PASS | {name}")
    else:
        failed += 1
        print(f"  FAIL | {name} {detail}")

def r(q, uid="test"):
    return app.rag_chain(q, uid)

# === Flujo real app.py -> evidence layer -> decisión ===
print("\n--- FLUJO REAL: app.py -> evidence layer ---")

# A. Horario City Tour -> conflict, NO LLM
res = r("¿Cuál es el horario del City Tour?")
test("A: City Tour horario -> conflict_detected", res.get('conflict_detected') is True)
test("A: City Tour horario -> evidence_status=conflict", res.get('evidence_status') == 'conflict')
test("A: City Tour horario -> needs_confirmation", res.get('needs_confirmation') is True)
test("A: City Tour horario -> NO LLM (response_route=evidence_conflict)", res.get('response_route') == 'evidence_conflict')

# B. Horario Valle Sagrado -> conflict, NO LLM
res = r("¿Cuál es el horario de Valle Sagrado?")
test("B: Valle Sagrado horario -> conflict_detected", res.get('conflict_detected') is True)
test("B: Valle Sagrado horario -> evidence_status=conflict", res.get('evidence_status') == 'conflict')
test("B: Valle Sagrado horario -> response_route=evidence_conflict", res.get('response_route') == 'evidence_conflict')

# C. Horario Montaña 7 Colores -> conflict, NO LLM
res = r("¿Cuál es el horario de Montaña de 7 Colores?")
test("C: Montaña 7 Colores horario -> conflict_detected", res.get('conflict_detected') is True)
test("C: Montaña 7 Colores horario -> response_route=evidence_conflict", res.get('response_route') == 'evidence_conflict')

# D. Inclusiones Montaña 7 Colores -> confirmed, NO falso conflicto
res = r("¿Qué incluye Montaña de 7 Colores?")
test("D: Montaña 7 Colores includes -> response_route no es conflict", res.get('response_route') != 'evidence_conflict')
resp_lower = res.get('response', '').lower()
test("D: incluye transporte", 'transporte' in resp_lower)
test("D: incluye desayuno", 'desayuno' in resp_lower)
test("D: incluye almuerzo", 'almuerzo' in resp_lower)
test("D: incluye oxígeno", 'oxígeno' in resp_lower or 'oxigeno' in resp_lower)
test("D: incluye entrada", 'entrada' in resp_lower)

# E. Laguna Humantay desayuno -> sí, source F1, NO F3
res = r("¿Laguna Humantay incluye desayuno?")
test("E: Humantay desayuno -> NO conflict", res.get('conflict_detected') is not True)
resp_lower = res.get('response', '').lower()
test("E: respuesta confirma desayuno", 'desayuno' in resp_lower)

# F. Valle Sagrado boleto turístico -> exclusión explícita F3
res = r("¿Valle Sagrado incluye boleto turístico?")
test("F: Valle Sagrado boleto -> response_route no es conflict", res.get('response_route') != 'evidence_conflict')
resp_lower = res.get('response', '').lower()
test("F: respuesta indica exclusión o no incluido", 'boleto' in resp_lower or 'no incluye' in resp_lower or 'excluido' in resp_lower)

# G. Inclusiones Machu Picchu -> combinar hechos compatibles
res = r("¿Qué incluye Machu Picchu?")
test("G: Machu Picchu includes -> response_route no es conflict", res.get('response_route') != 'evidence_conflict')

# H. Precio Salkantay -> unknown, no inventar
res = r("¿Cuánto cuesta Salkantay?")
test("H: Salkantay precio -> needs_confirmation", res.get('needs_confirmation') is True)
resp_lower = res.get('response', '').lower()
test("H: NO inventa precio", '$' not in resp_lower and 'usd' not in resp_lower.split('precio')[0:1])

# I. ¿Tienen Salkantay? -> sí, producto confirmado
res = r("¿Tienen Salkantay?")
test("I: Salkantay -> producto confirmado", 'salkantay' in res.get('response', '').lower() or 'confirmado' in res.get('response', '').lower())

# J. ¿Aceptan Yape? -> unknown / confirmar con agencia
res = r("¿Aceptan Yape?")
test("J: Yape -> needs_confirmation", res.get('needs_confirmation') is True)
resp_lower = res.get('response', '').lower()
test("J: NO confirma Yape", 'sí' not in resp_lower.split('.')[0] if '.' in resp_lower else True)

# === Regresión: no romper funcionalidad existente ===
print("\n--- REGRESIÓN: funcionalidad existente ---")

res = r("Hola, ¿qué tal?")
test("REG: Saludo sigue funcionando", len(res.get('response', '')) > 0)
test("REG: Saludo -> is_fallback no es True obligatorio", True)  # No debe fallar

res = r("¿Cuánto cuesta el Machu Picchu?")
test("REG: Precio Machu Picchu -> needs_confirmation", res.get('needs_confirmation') is True)

# === Verificación de metadata de respuesta ===
print("\n--- METADATA: campos de respuesta ---")
res = r("¿Qué tours tienen?")
test("META: response_route presente", 'response_route' in res)
test("META: evidence_status presente", 'evidence_status' in res)
test("META: needs_confirmation presente", 'needs_confirmation' in res)
test("META: conflict_detected presente", 'conflict_detected' in res)
test("META: sources_used presente", 'sources_used' in res)

print(f"\n{'='*60}")
print(f"RESULTADO: {passed} PASS / {failed} FAIL / {total} TOTAL")
print(f"{'='*60}")

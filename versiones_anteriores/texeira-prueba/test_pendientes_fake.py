"""
Pruebas pendientes de la sesion anterior, ejecutadas SOLO con FakeLLM.
No consume tokens de Groq.
"""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
import sys
sys.path.insert(0, '.')
import app

class FakeLLM:
    def invoke(self, messages):
        return type('Answer', (), {'content': 'Respuesta simulada para prueba.'})()

app.get_llm = lambda: FakeLLM()

print("=" * 60)
print("PRUEBAS PENDIENTES - SOLO SIMULACION (FakeLLM)")
print("=" * 60)

# ============================================================
# PENDIENTE 1: EN disponibilidad "Is there availability for tomorrow?"
# ============================================================
print("\n--- PENDIENTE 1: EN disponibilidad ---")
r = app.rag_chain('Is there availability for tomorrow?', 'pend-1')
needs = r.get('needs_agency_confirmation', False)
print("needs_agency_confirmation: %s (debe ser True)" % needs)
assert needs, "Fallo pend-1: disponibilidad EN debe marcar needs_agency"
print("OK")

# ============================================================
# PENDIENTE 2: EN disponibilidad variante "Do you have spots available?"
# ============================================================
print("\n--- PENDIENTE 2: EN disponibilidad variante ---")
r = app.rag_chain('Do you have spots available?', 'pend-2')
needs = r.get('needs_agency_confirmation', False)
print("needs_agency_confirmation: %s (debe ser True)" % needs)
assert needs, "Fallo pend-2: spots EN debe marcar needs_agency"
print("OK")

# ============================================================
# PENDIENTE 3: EN precio PEN "Price in soles for Salkantay"
# ============================================================
print("\n--- PENDIENTE 3: EN precio PEN ---")
r = app.rag_chain('What is the price in soles for Salkantay?', 'pend-3')
resolved = r.get('resolved_autonomously', True)
needs = r.get('needs_agency_confirmation', False)
print("resolved_autonomously: %s (debe ser False)" % resolved)
print("needs_agency_confirmation: %s (debe ser True)" % needs)
assert not resolved, "Fallo pend-3: precio EN PEN debe marcar resolved=False"
assert needs, "Fallo pend-3: precio EN PEN debe marcar needs_agency=True"
print("OK")

# ============================================================
# PENDIENTE 4: EN precio PEN variante "How much in PEN for City Tour?"
# ============================================================
print("\n--- PENDIENTE 4: EN precio PEN variante ---")
r = app.rag_chain('How much in PEN for the City Tour?', 'pend-4')
resolved = r.get('resolved_autonomously', True)
needs = r.get('needs_agency_confirmation', False)
print("resolved_autonomously: %s (debe ser False)" % resolved)
print("needs_agency_confirmation: %s (debe ser True)" % needs)
assert not resolved, "Fallo pend-4: precio EN PEN variante debe marcar resolved=False"
assert needs, "Fallo pend-4: precio EN PEN variante debe marcar needs_agency=True"
print("OK")

print("\n" + "=" * 60)
print("LAS 4 PRUEBAS PENDIENTES PASARON (FakeLLM, sin Groq)")
print("=" * 60)

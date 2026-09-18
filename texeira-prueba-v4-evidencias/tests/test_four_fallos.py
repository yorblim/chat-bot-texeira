import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Prueba específica para los cuatro fallos corregidos según REVISION_OPENCODE.md"""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['ANONYMIZED_TELEMETRY']='False'
import app

class FakeLLM:
    def invoke(self, messages):
        return type('Answer',(),{'content':'Simulated response'})()

app.get_llm = lambda: FakeLLM()

print("=== FALLO 1: Derivación falsa ===")
# "Contacta a un asesor para consultar los detalles" no debe ser escalation
# Es orientación, no transferencia ejecutada
r1 = app.rag_chain('Contacta a un asesor para consultar los detalles', 'test1')
print(f"is_escalation: {r1['is_escalation']} (debe ser False)")
print(f"resolved_autonomously: {r1.get('resolved_autonomously', True)} (debe ser True)")
assert not r1['is_escalation'], "Fallo 1: is_escalation debe ser False"
assert r1.get('resolved_autonomously', True), "Fallo 1: resolved_autonomously debe ser True"

print("\n=== FALLO 2: Contacto de agencia ===")
# El LLM puede ofrecer fuentes externas; el post-procesamiento debe corregir
# Verificamos que la detección de necesidad de agencia funciona
r2 = app.rag_chain('¿Hay cupos disponibles para mañana?', 'test2')
print(f"needs_agency_confirmation: {r2.get('needs_agency_confirmation', False)} (debe ser True)")
assert r2.get('needs_agency_confirmation', False), "Fallo 2: needs_agency_confirmation debe ser True"

print("\n=== FALLO 3: Condiciones pendientes en rutas deterministas ===")
# "¿Cuál es el precio en soles de Salkantay?" debe marcar needs_agency_confirmation=true
r3 = app.rag_chain('¿Cuál es el precio en soles de Salkantay?', 'test3')
print(f"resolved_autonomously: {r3['resolved_autonomously']} (debe ser False)")
print(f"needs_agency_confirmation: {r3.get('needs_agency_confirmation', False)} (debe ser True)")
print(f"response contiene USD: {'USD' in r3['response']}")
assert not r3['resolved_autonomously'], "Fallo 3: resolved_autonomously debe ser False"
assert r3.get('needs_agency_confirmation', False), "Fallo 3: needs_agency_confirmation debe ser True"

print("\n=== FALLO 4: Historial guarda texto post-procesado ===")
# El historial debe contener la respuesta final, no la original
r4 = app.rag_chain('¿Cuánto cuesta en soles Machu Picchu?', 'test4')
history = app.get_history('test4')
last_ai = [h for h in history if h['role']=='ai'][-1]['content']
print(f"Longitud respuesta: {len(r4['response'])}")
print(f"Longitud historial: {len(last_ai)}")
print(f"Coinciden: {r4['response'] == last_ai}")
assert r4['response'] == last_ai, "Fallo 4: historial debe coincidir con respuesta final"

print("\n=== PRUEBAS ADICIONALES ===")
# Precio referencial conocido en USD no debe marcar pendiente
r5 = app.rag_chain('¿Cuánto cuesta el City Tour?', 'test5')
print(f"City Tour USD - needs_agency: {r5.get('needs_agency_confirmation', False)} (debe ser False)")
assert not r5.get('needs_agency_confirmation', False), "Precio referencial USD no debe marcar pendiente"

# Disponibilidad en inglés
r6 = app.rag_chain('Is there availability for tomorrow?', 'test6')
print(f"Availability EN - needs_agency: {r6.get('needs_agency_confirmation', False)} (debe ser True)")
assert r6.get('needs_agency_confirmation', False), "Disponibilidad en inglés debe marcar pendiente"

print("\nTODAS LAS PRUEBAS PASARON")

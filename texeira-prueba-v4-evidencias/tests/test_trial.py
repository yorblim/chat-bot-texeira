import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['ANONYMIZED_TELEMETRY']='False'
import app
from trial_support import documents, retriever

class FakeLLM:
 def invoke(self,messages):
  prompt = messages[0][1]
  assert 'NO tarifa oficial' in prompt or 'PROTOTIPO' in prompt
  assert 'Cotización' not in prompt or 'USD 120' not in prompt
  return type('Answer',(),{'content':'Información referencial; consulta las condiciones con la agencia.'})()

app.get_llm = lambda: FakeLLM()
assert set(app.PREDEFINED_RESPONSES).isdisjoint({'precios','contacto','cuánto cuesta','pago'})
for question, expected in [('¿Cuánto cuesta Valle Sagrado?','40–60'),('¿Cuánto cuesta Machu Picchu?','300–400'),('¿Qué incluye Humantay?','ESCENARIO SIMULADO')]:
 answer = app.rag_chain(question,'test-'+question)['response']
 assert expected in answer and 'PROTOTIPO' in answer, answer
app.rag_chain('¿Cuánto cuesta Valle Sagrado?','followup')
assert 'Valle Sagrado' in app.rag_chain('¿Y qué incluye?','followup')['response']
for q in ['tours','precios']:
 answer=app.rag_chain(q,'list')['response']
 assert '300–400' in answer and 'hipotético' in answer
assert '953 767 860' in app.rag_chain('contacto','contact')['response']
assert '984 123456' not in app.rag_chain('contacto','contact')['response']
assert app.check_tour_intent('What does the tour include?','en') is None
assert app.detect_language('What does the Machu Picchu tour include?') == 'en'
assert app.detect_language('¿Qué incluye Machu Picchu?') == 'es'
assert app.detect_language('Quanto custa Machu Picchu?') == 'pt'
assert app.detect_language('Quel est le prix de Machu Picchu?') == 'fr'
assert 'Excluye' not in app.rag_chain('¿Cuánto cuesta Valle Sagrado?', 'focused')['response']
pending = app.rag_chain('¿Puedo cancelar gratis mañana?', 'pending')
assert pending['resolved_autonomously'] is False
assert pending['needs_agency_confirmation'] is True
assert pending['is_escalation'] is False
docs = retriever().invoke('precio Machu Picchu tren')
assert docs and len(docs)<=5
assert all(d.metadata['source']=='provisional-2026-09-11' for d in docs)
assert any(d.metadata['tour_id']=='machu-picchu-clasico' for d in docs)
for q in ['¿Cuál es la política de cancelación?', 'What does the tour include?']:
 answer=app.rag_chain(q,'rag-test')['response']
 assert 'PROTOT' in answer
assert not app.META_ACCESS_TOKEN and not app.META_APP_SECRET
# Pruebas adicionales de cuatro fallos corregidos
# Fallo 1: Derivación falsa
r1 = app.rag_chain('Contacta a un asesor para consultar los detalles', 'test-derivation')
assert not r1['is_escalation'], 'Derivación falsa: is_escalation debe ser False'
assert r1.get('resolved_autonomously', True), 'Derivación falsa: resolved_autonomously debe ser True'

# Fallo 2: Contacto de agencia (detección de disponibilidad)
r2 = app.rag_chain('¿Hay cupos disponibles?', 'test-contact')
assert r2.get('needs_agency_confirmation', False), 'Contacto: needs_agency_confirmation debe ser True'

# Fallo 3: Condiciones pendientes en rutas deterministas
r3 = app.rag_chain('¿Cuál es el precio en soles de Salkantay?', 'test-deterministic')
assert not r3['resolved_autonomously'], 'Determinista: resolved_autonomously debe ser False'
assert r3.get('needs_agency_confirmation', False), 'Determinista: needs_agency_confirmation debe ser True'

# Fallo 4: Historial guarda texto post-procesado
r4 = app.rag_chain('¿Cuánto cuesta en soles Machu Picchu?', 'test-history')
history = app.get_history('test-history')
last_ai = [h for h in history if h['role']=='ai'][-1]['content']
assert r4['response'] == last_ai, 'Historial: respuesta debe coincidir con historial'

print('OK: precios, inclusiones, seguimiento, listado, contacto, RAG con LLM simulado e aislamiento de Meta. Sin llamadas al proveedor.')

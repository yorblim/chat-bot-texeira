"""Test del catálogo v3-folleto contra 16 preguntas de verificación del usuario.
Ejecuta sin Groq usando FakeLLM. Verifica respuestas usando indicios (FakeLLM no genera respuestas reales).
"""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['ANONYMIZED_TELEMETRY']='False'
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import app

class FakeLLM:
    def invoke(self, messages):
        return type('Answer',(),{'content':''})()
    def bind_tools(self, *a, **kw): return self
    def __or__(self, other): return self

app.get_llm = lambda: FakeLLM()

def run_test(name, question, expected_keywords):
    result = app.rag_chain(question, 'test_user')
    reply = result.get('response', result.get('reply', ''))
    ok = all(k.lower() in reply.lower() for k in expected_keywords)
    status = 'PASS' if ok else 'FAIL'
    print(f'  {status} | {name}')
    if not ok:
        for k in expected_keywords:
            if k.lower() not in reply.lower():
                print(f'    Falta keyword: {k}')
        print(f'    Reply: {reply[:200]}')
    return ok

if __name__ == '__main__':
    tests = [
        ("Tours disponibles", "¿Qué tours ofrecen?", ["City Tour", "Valle Sagrado", "Machu Picchu"]),
        ("Machu Picchu incluye", "¿Qué incluye el tour de Machu Picchu?", ["bus", "tren", "guía"]),
        ("Bus subida/bajada", "¿Incluye bus de subida y bajada?", ["bus", "subida", "bajada"]),
        ("Maras Moray incluye", "¿Qué incluye el tour de Maras Moray?", ["Maras", "Moray"]),
        ("Valle Sur lugares", "¿Qué lugares visito en el Valle Sur?", ["Tipon", "Pikillaqta", "Andahuaylillas"]),
        ("Montaña 7 Colores", "¿Cómo es el tour de la Montaña de 7 Colores?", ["7 Colores"]),
        ("Laguna Humantay", "¿Qué incluye el tour de Laguna Humantay?", ["Humantay"]),
        ("City Tour horarios", "¿A qué hora es el City Tour?", ["10", "14"]),
        ("Machu Picchu precio", "¿Cuánto cuesta Machu Picchu?", ["USD", "350"]),
        ("Aceptan tarjeta", "¿Aceptan tarjeta de crédito?", ["consultar", "agencia"]),
        ("Política cancelación", "¿Cuál es su política de cancelación?", ["consultar", "agencia"]),
        ("Salkantay", "¿Ofrecen el Salkantay Trek?", ["consultar", "agencia"]),
        ("Horario Maras Moray", "¿A qué hora es el tour de Maras Moray?", ["08:40", "14"]),
        ("Horario Valle Sur", "¿A qué hora es el Valle Sur?", ["08:40", "14"]),
        ("Horario Humantay", "¿A qué hora sale el tour a Laguna Humantay?", ["04:30", "17"]),
        ("Horario 7 Colores", "¿A qué hora sale el tour a la Montaña de 7 Colores?", ["04:30", "17"]),
    ]

    print("=== TEST 16 PREGUNTAS DE VERIFICACIÓN (v3-folleto) ===")
    passed = 0
    for name, q, kw in tests:
        if run_test(name, q, kw):
            passed += 1
    print(f"\nResultado: {passed}/{len(tests)} PASS")
    sys.exit(0 if passed == len(tests) else 1)

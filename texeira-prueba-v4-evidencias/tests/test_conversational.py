"""Tests conversacionales - sin Groq, verificando routing y presentacion."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import app

PASSED = 0
FAILED = 0

def test(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS | {name}")
    else:
        FAILED += 1
        print(f"  FAIL | {name} {detail}")

def r(q, uid="test"):
    return app.rag_chain(q, uid)

print("=" * 60)
print("TESTS CONVERSACIONALES - v4-evidencias")
print("=" * 60)

# --- SOCIAL ---
print("\n--- Social/Hola ---")
res = r("Hola", "test_social_1")
test("Hola: route social", res.get('route') == 'social' or res.get('response_route') == 'social', f"route={res.get('route')}, response_route={res.get('response_route')}")
test("Hola: no LLM", res.get('context_used') == False)
test("Hola: no disclaimer", 'materiales de Texeira' not in res['response'], f"response={res['response'][:80]}")
test("Hola: mentions Texeira Travel", 'Texeira Travel' in res['response'])
test("Hola: brief (< 100 chars)", len(res['response']) < 100, f"len={len(res['response'])}")

print("\n--- Social/Me ayudas ---")
res = r("Me ayudas", "test_social_2")
test("Ayuda: route help", res.get('route') == 'help' or res.get('response_route') == 'help', f"route={res.get('route')}, response_route={res.get('response_route')}")
test("Ayuda: no LLM", res.get('context_used') == False)
test("Ayuda: no disclaimer", 'materiales de Texeira' not in res['response'])
test("Ayuda: mentions tours/servicios", any(w in res['response'].lower() for w in ['tours', 'servicios', 'ayudarte']))
test("Ayuda: brief (< 150 chars)", len(res['response']) < 150, f"len={len(res['response'])}")

print("\n--- Social/Gracias ---")
res = r("Gracias", "test_social_3")
test("Gracias: route social", res.get('route') == 'social' or res.get('response_route') == 'social', f"route={res.get('route')}, response_route={res.get('response_route')}")
test("Gracias: no LLM", res.get('context_used') == False)
test("Gracias: no disclaimer", 'materiales de Texeira' not in res['response'])

# --- EVIDENCE: CONFIRMED ---
print("\n--- Evidence: Montana 7 Colores inclusiones ---")
res = r("Que incluye Montaña de 7 Colores?", "test_ev_1")
test("Incluye: evidence route", 'evidence' in res.get('route', '') or 'evidence' in res.get('response_route', ''), f"route={res.get('route')}, response_route={res.get('response_route')}")
test("Incluye: no disclaimer", 'materiales de Texeira' not in res['response'])
test("Incluye: has content", len(res['response']) > 20)

# --- EVIDENCE: UNKNOWN ---
print("\n--- Evidence: Yape ---")
res = r("Aceptan Yape?", "test_ev_2")
test("Yape: unknown route", 'unknown' in res.get('route', '') or 'unknown' in res.get('response_route', ''), f"route={res.get('route')}, response_route={res.get('response_route')}")
test("Yape: no disclaimer", 'materiales de Texeira' not in res['response'])
test("Yape: mentions agencia", 'agencia' in res['response'].lower())

# --- EVIDENCE: SCHEDULE CONFIRMADO ---
print("\n--- Evidence: City Tour horario ---")
res = r("Cuál es el horario del City Tour?", "test_ev_3")
test("Horario: schedule route", 'schedule' in res.get('route', '') or 'schedule' in res.get('response_route', ''), f"route={res.get('route')}, response_route={res.get('response_route')}")
test("Horario: no disclaimer", 'materiales de Texeira' not in res['response'])
test("Horario: has confirmed hours", '10:00-14:00' in res['response'] and '13:30-18:30' in res['response'])

# --- EVIDENCE: PRICE UNKNOWN ---
print("\n--- Evidence: Salkantay precio ---")
res = r("Cuánto cuesta Salkantay?", "test_ev_4")
test("Precio: unknown route", 'unknown' in res.get('route', '') or 'unknown' in res.get('response_route', ''), f"route={res.get('route')}, response_route={res.get('response_route')}")
test("Precio: no disclaimer", 'materiales de Texeira' not in res['response'])

# --- METADATA ---
print("\n--- Metadata check ---")
res = r("Hola", "test_meta")
test("Meta: has response_route", 'response_route' in res)
test("Meta: has evidence_status", 'evidence_status' in res)
test("Meta: has needs_confirmation", 'needs_confirmation' in res)
test("Meta: has conflict_detected", 'conflict_detected' in res)
test("Meta: has sources_used", 'sources_used' in res)

print(f"\n{'='*60}")
print(f"RESULTADO: {PASSED} PASS / {FAILED} FAIL / {PASSED+FAILED} TOTAL")
print(f"{'='*60}")

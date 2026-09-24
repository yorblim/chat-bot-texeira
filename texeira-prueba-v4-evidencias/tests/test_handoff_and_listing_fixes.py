"""
Prueba unitaria para validación de handoff flexible y prevención de colisión en listing.
Cubre las mejoras derivadas del análisis de casos borde.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import app
import handoff_support

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

print("=" * 60)
print("TESTS: HANDOFF Y LISTING EDGE CASES")
print("=" * 60)

# --- 1. HANDOFF REQUESTED() NATURAL MATCHES ---
print("\n--- Handoff: Solicitudes naturales ---")
pos_cases = [
    "asesor",
    "¡asesor!",
    "hablar con un asesor",
    "quiero hablar con un asesor",
    "necesito un asesor",
    "quiero hablar con una persona",
    "solicitar asesor",
    "quiero que me llamen",
    "pueden llamarme por favor",
    "necesito ayuda humana",
    "pueden contactarme",
    "quisiera hablar con un asesor",
    "deseo comunicarme con una persona",
    "atención humana por favor",
    "me pueden llamar?",
    "human agent",
    "speak to an agent",
    "i want to speak to an agent",
    "i need human help",
    "please call me"
]

for q in pos_cases:
    test(f"Positivo: '{q}'", handoff_support.requested(q) is True)

# --- 2. HANDOFF PREVENCIÓN DE FALSOS POSITIVOS ---
print("\n--- Handoff: Falsos positivos prevenidos ---")
neg_cases = [
    "Necesito ayuda con mi viaje",
    "Contacta a un asesor para consultar los detalles",
    "Te recomiendo contactar a un asesor",
    "I recommend contacting an advisor",
    "Habla con un asesor para más info",
    "Talk to an agent for details",
    "¿El tour incluye guía o asesor?",
    "Hola buenos días",
    "¿Qué tours tienen disponibles?",
    "¿Cuánto cuesta Machu Picchu?"
]

for q in neg_cases:
    test(f"Negativo (no handoff): '{q}'", handoff_support.requested(q) is False)

# --- 3. LISTING VS ENTIDAD (COLISIÓN DE 'OTROS LUGARES') ---
print("\n--- Listing vs Entidad Específica ---")
# Catálogo general cuando no hay entidad
res_general = app.rag_chain("otros lugares", "uid_listing_1")
test("Listing general: route evidence_listing", res_general.get('route') == 'evidence_listing')
test("Listing general: entity_id is None", res_general.get('entity_id') is None)

# No debe colisionar cuando la pregunta especifica un tour (ej. Valle Sagrado)
res_valle = app.rag_chain("otros lugares del valle sagrado", "uid_listing_2")
test("Entidad específica: NO es evidence_listing", res_valle.get('route') != 'evidence_listing')
test("Entidad específica: detecta valle-sagrado", res_valle.get('entity_id') == 'valle-sagrado')
test("Entidad específica: route es evidence_stops", res_valle.get('route') == 'evidence_stops')

# Listado cuando hay frase de excepción / adición ("además de", "aparte de")
res_ademas = app.rag_chain("otros tours además de machu picchu", "uid_listing_3")
test("Excepción: 'además de' activa evidence_listing", res_ademas.get('route') == 'evidence_listing')

print("\n" + "=" * 60)
print(f"RESULTADO: {PASSED} PASS / {FAILED} FAIL / {PASSED+FAILED} TOTAL")
print("=" * 60)

if FAILED > 0:
    sys.exit(1)

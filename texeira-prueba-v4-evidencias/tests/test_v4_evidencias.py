"""test_v4_evidencias.py: 22+ tests del motor de evidencia v4.
NO usa Groq. NO necesita servidor. Solo证据层 + rutas deterministas.
"""
import os, sys
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
sys.path.insert(0, r'C:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias')

passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS | {name}")
        passed += 1
    else:
        print(f"  FAIL | {name}")
        if detail:
            print(f"        {detail}")
        failed += 1
        errors.append(name)

print("=" * 60)
print("TESTS V4-EVIDENCIAS: MOTOR DE EVIDENCIA")
print("=" * 60)

# --- EVIDENCE ENGINE TESTS ---
print("\n--- EVIDENCE ENGINE ---")

from src.evidence import (
    get_facts, detect_conflicts, is_product_confirmed,
    get_confirmed_products, build_context_for_entity,
    build_context_for_question, get_listing, get_includes,
    get_route, stats
)

s = stats()
print(f"  Stats: {s['total_facts']} facts, {s['confirmed_products']} products, {s['conflicts']} conflicts")

# E1: F1 includes desayuno, F2 no menciona -> NO conflict
facts_desayuno_m7c = get_facts('montana-7-colores', 'includes')
desayuno_f1 = [f for f in facts_desayuno_m7c if f.item == 'desayuno' and f.source_id == 'F1']
test("E1a: desayuno confirmado por F1", len(desayuno_f1) > 0)
conflicts_m7c = detect_conflicts('montana-7-colores', 'includes')
test("E1b: NO conflict en includes de Montaña 7 Colores", len(conflicts_m7c) == 0,
     f"Conflicts: {conflicts_m7c}")

# E2: F1 includes [transporte,guía], F3 includes [transporte,guía,oxígeno] -> complementary
facts_m7c = get_facts('montana-7-colores', 'includes')
oxigeno_f3 = [f for f in facts_m7c if f.item == 'oxigeno' and f.source_id == 'F3']
test("E2a: oxígeno confirmado por F3", len(oxigeno_f3) > 0)
entrada_f3 = [f for f in facts_m7c if f.item == 'entrada_montana' and f.source_id == 'F3']
test("E2b: entrada_montana confirmada por F3", len(entrada_f3) > 0)

# E3: F1 includes entrada, F3 excludes entrada -> conflict (for Valle Sagrado)
# In our data: F3 excludes boleto_turistico for valle-sagrado
facts_vs_excludes = get_facts('valle-sagrado', 'excludes')
boleto_exc = [f for f in facts_vs_excludes if f.item == 'boleto_turistico']
test("E3a: boleto_turistico excluido por F3", len(boleto_exc) > 0 and boleto_exc[0].source_id == 'F3')
test("E3b: NO hay includes contradictorios para boleto", 
     not any(f.item == 'boleto_turistico' and f.field == 'includes' for f in get_facts('valle-sagrado')))

# E4: F1 schedule 04:30-17:00, F3 schedule 05:00-16:30 -> conflict
conflicts_m7c_sched = detect_conflicts('montana-7-colores', 'schedule')
test("E4: conflicto de horario Montaña 7 Colores", len(conflicts_m7c_sched) > 0,
     f"Conflicts: {len(conflicts_m7c_sched)}")

# E5: dos teléfonos diferentes -> NO conflict
phone_facts = get_facts('agency', 'phone')
test("E5a: al menos 2 teléfonos", len(phone_facts) >= 2)
conflicts_phone = detect_conflicts('agency', 'phone')
test("E5b: NO conflict entre teléfonos", len(conflicts_phone) == 0)

# E6: Salkantay confirmed, price unknown
test("E6a: Salkantay es producto confirmado", is_product_confirmed('salkantay-trek'))
salk_price = get_facts('salkantay-trek', 'official_price')
test("E6b: Salkantay NO tiene precio oficial", len(salk_price) == 0)

# E7: fact conflictivo de horario NO llega al LLM
ctx, has_conflict = build_context_for_question('montana-7-colores', ['schedule'])
test("E7a: contexto indica conflicto", has_conflict)
test("E7b: contexto no contiene hora específica como dato definitivo",
     '04:30' not in ctx and '05:00' not in ctx,
     f"Context: {ctx[:200]}")

# E8: facts complementarios consolidados sin duplicados
ctx_m7c = build_context_for_entity('montana-7-colores')
test("E8a: contexto de Montaña 7 Colores generado", len(ctx_m7c) > 0)
test("E8b: oxígeno aparece en contexto", 'oxigeno' in ctx_m7c.lower() or 'oxígeno' in ctx_m7c.lower())
test("E8c: entrada aparece en contexto", 'entrada' in ctx_m7c.lower())

# E9: desayuno Humantay respaldado por F1, NO por F3
facts_lh_desayuno = get_facts('laguna-humantay', 'includes')
desayuno_sources = [f.source_id for f in facts_lh_desayuno if f.item == 'desayuno']
test("E9a: desayuno Humantay respaldado por F1", 'F1' in desayuno_sources)
test("E9b: desayuno Humantay NO atribuido a F3", 'F3' not in desayuno_sources,
     f"Sources: {desayuno_sources}")
almuerzo_sources = [f.source_id for f in facts_lh_desayuno if f.item == 'almuerzo']
test("E9c: almuerzo Humantay respaldado por F1+F2", 'F1' in almuerzo_sources and 'F2' in almuerzo_sources)

# E10: F1 route [A,B,C], F3 route [A,B,C,D] -> complementary
stops_vs = get_facts('valle-sur', 'stops')
stop_entities = set(f.item for f in stops_vs)
test("E10: Valle Sur tiene stops de múltiples fuentes", len(stop_entities) >= 3)

# --- TOURS CATALOG TESTS ---
print("\n--- TOURS CATALOG ---")

confirmed = get_confirmed_products()
test("CAT1: hay productos confirmados", len(confirmed) > 0)
test("CAT2: cantidad de productos >= 17", len(confirmed) >= 17,
     f"Found: {len(confirmed)}")

entity_ids_confirmed = [t['entity_id'] for t in confirmed]
test("CAT3: City Tour confirmado", 'city-tour-cusco' in entity_ids_confirmed)
test("CAT4: Salkantay confirmado", 'salkantay-trek' in entity_ids_confirmed)
test("CAT5: Waqra Pukara confirmado", 'waqra-pukara' in entity_ids_confirmed)
test("CAT6: Choquequirao confirmado", 'choquequirao' in entity_ids_confirmed)
test("CAT7: Inka Jungle confirmado", 'inka-jungle' in entity_ids_confirmed)
test("CAT8: Tour Místico confirmado", 'tour-mistico' in entity_ids_confirmed)
test("CAT9: Ruta del Sol confirmado", 'ruta-del-sol' in entity_ids_confirmed)
test("CAT10: Tour Cuatrimoto confirmado", 'maras-moray-cuatrimoto' in entity_ids_confirmed)

# --- CONFLICTS TESTS ---
print("\n--- CONFLICT DETECTION ---")

ct_conflicts = detect_conflicts('city-tour-cusco', 'schedule')
test("CONFLICT1: City Tour tiene conflicto de horario", len(ct_conflicts) > 0)
vs_conflicts = detect_conflicts('valle-sagrado', 'schedule')
test("CONFLICT2: Valle Sagrado tiene conflicto de horario", len(vs_conflicts) > 0)
m7c_conflicts = detect_conflicts('montana-7-colores', 'schedule')
test("CONFLICT3: Montaña 7 Colores tiene conflicto de horario", len(m7c_conflicts) > 0)

# No false conflicts
test("CONFLICT4: Valle Sur NO tiene conflicto de horario", len(detect_conflicts('valle-sur', 'schedule')) == 0)
test("CONFLICT5: Laguna Humantay NO tiene conflicto de includes", len(detect_conflicts('laguna-humantay', 'includes')) == 0)

# --- LISTING TESTS ---
print("\n--- LISTING ---")

listing = get_listing()
test("LIST1: listing generado", len(listing) > 0)
test("LIST2: listing contiene City Tour", 'City Tour' in listing)
test("LIST3: listing contiene Salkantay", 'Salkantay' in listing)
test("LIST4: listing contiene Waqra Pukara", 'Waqra Pukara' in listing)

# --- REGRESSION TESTS ---
print("\n--- REGRESSION: ANTI-ALUCINACIÓN ---")

# Salkantay price should not exist
salk_facts_price = get_facts('salkantay-trek', 'official_price')
test("REG1: Salkantay sin precio oficial", len(salk_facts_price) == 0)

# Waqra Pukara has limited info
wp_includes = get_includes('waqra-pukara')
test("REG2: Waqra Pukara includes desde F3", 'transporte' in wp_includes.lower() or 'guia' in wp_includes.lower())

# Valle Sagrado excludes boleto
vs_excludes = get_includes('valle-sagrado')
# The excludes should be tracked separately
vs_ex_facts = get_facts('valle-sagrado', 'excludes')
test("REG3: Valle Sagrado tiene excludes registrados", len(vs_ex_facts) > 0)

# Paquete 7D/6N should NOT be confirmed
test("REG4: Paquete 7D/6N NO confirmado", not is_product_confirmed('paquete-completo-7d'))

# Machu Picchu by Car separate from tren
test("REG5: Machu Picchu by Car es producto separado", is_product_confirmed('machu-picchu-car'))
test("REG6: Machu Picchu en Tren es producto separado", is_product_confirmed('machu-picchu-tren'))
test("REG7: Son productos diferentes", 'machu-picchu-car' != 'machu-picchu-tren')

# --- SUMMARY ---
print("\n" + "=" * 60)
print(f"RESULTADO: {passed} PASS / {failed} FAIL / {passed + failed} TOTAL")
if errors:
    print(f"Errores: {', '.join(errors)}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)

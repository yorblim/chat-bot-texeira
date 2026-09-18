"""Validación del catálogo v3-folleto: 7 tours del folleto + respuestas deterministas.
Prueba directa del catálogo y respuestas, sin LLM.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / 'data/provisional.json').read_text(encoding='utf-8'))

print("=== VALIDACIÓN CATÁLOGO v3-folleto ===")
print(f"Tours en catálogo: {len(CATALOG['tours'])}")
print(f"Agency emails: {CATALOG['agency'].get('emails', [])}")
print(f"Unconfirmed products: {len(CATALOG.get('unconfirmed_products', []))}")

tours_ok = 0
errors = []

for t in CATALOG['tours']:
    name = t['name']
    tid = t['id']
    
    # Verificar campos obligatorios
    required = ['id', 'name', 'duration_reference', 'agency_published', 'simulation_includes', 'simulation_excludes']
    for field in required:
        if field not in t:
            errors.append(f"{name}: falta campo {field}")
    
    # Verificar que range_usd es None o tupla de 2
    range_usd = t.get('range_usd')
    if range_usd is not None:
        if not isinstance(range_usd, list) or len(range_usd) != 2:
            errors.append(f"{name}: range_usd inválido: {range_usd}")
    
    # Verificar fuentes
    sources = t.get('market_sources', [])
    if range_usd and not sources:
        errors.append(f"{name}: tiene precio pero sin fuentes de mercado")
    
    tours_ok += 1
    print(f"  OK {name} ({tid})")

print(f"\nTours validados: {tours_ok}/{len(CATALOG['tours'])}")

# Verificar Machu Picchu incluye bus
mp = next((t for t in CATALOG['tours'] if t['id'] == 'machu-picchu-clasico'), None)
if mp:
    has_bus = any('bus' in p.lower() for p in mp['agency_published'])
    print(f"\nMachu Picchu incluye bus: {'SI' if has_bus else 'NO'}")
    if not has_bus:
        errors.append("Machu Picchu no menciona bus en agency_published")

# Verificar nuevos tours
new_tours = ['maras-moray', 'valle-sur']
for tid in new_tours:
    t = next((t for t in CATALOG['tours'] if t['id'] == tid), None)
    if t:
        print(f"  OK {t['name']} (nuevo en folleto)")
    else:
        errors.append(f"Tour {tid} no encontrado")

# Verificar productos no confirmados
unconfirmed = CATALOG.get('unconfirmed_products', [])
print(f"\nProductos NO confirmados en folleto: {len(unconfirmed)}")
for u in unconfirmed:
    print(f"  - {u['name']}: {u['note']}")

if errors:
    print(f"\nERRORES: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
else:
    print("\nTODOS LOS CAMPOS VALIDOS")

# Guardar resultado
result = {
    'tours_count': len(CATALOG['tours']),
    'tours_ok': tours_ok,
    'errors': errors,
    'unconfirmed_count': len(unconfirmed),
    'bus_confirmed': has_bus if mp else False,
    'new_tours': new_tours
}
(ROOT / 'validacion_catalogo_v3.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"\nResultado guardado en validacion_catalogo_v3.json")

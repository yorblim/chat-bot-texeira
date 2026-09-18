import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Evitar que traducir una duración cambie la cantidad publicada."""
from verified_routes import english_duration
for days in (3,4,5,8):
    source=f'{days} días (itinerario publicado; confirmar variante y noches)'
    actual=english_duration(source)
    assert actual==f'{days} days (published itinerary; confirm variant and nights)',actual
assert english_duration('6 horas')=='6 hours'
print('PASS: traducción conserva cantidades y advertencias.')

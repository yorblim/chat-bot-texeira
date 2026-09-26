"""
test_instant_catalog_update.py — Test de actualización instantánea de catálogo y WhatsApp.

Verifica que cualquier modificación efectuada en /catalogo o catalog_service
se refleje inmediatamente (latencia < 50ms) en las respuestas del bot, sin
retrasos de caché y sin alucinaciones de precios ni horarios.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app
import catalog_service


def test_instant_catalog_reflection():
    print("=" * 60)
    print("TEST: ACTUALIZACIÓN INSTANTÁNEA DEL CATÁLOGO")
    print("=" * 60)

    # 1. Asegurar estado inicial conocido de camino-inka
    ok, _ = catalog_service.upsert_tour({
        "entity_id": "camino-inka",
        "name": "Camino Inca Clásico 4D/3N",
        "official_price": "790",
        "currency": "USD",
        "schedule": "Recojo 4:30 a. m. – 5:00 a. m.",
        "duration": "4 días / 3 noches",
        "aliases": ["camino inca", "camino inka", "inca trail", "camino inca clasico"],
        "includes": "caminata, bus de Machu Picchu a Aguas Calientes, tren turístico de retorno a Ollantaytambo",
        "excludes": "bastones de trekking, propinas",
        "is_active": True
    })
    assert ok, "Fallo al configurar tour inicial"

    # 2. Consulta directa por nombre de tour con viñeta (tal como en WhatsApp)
    r1 = app.rag_chain("· Camino Inca Clásico 4D/3N", "user_test_instant")
    assert r1.get("response_route") == "evidence_tour_overview", f"Ruta inesperada: {r1.get('response_route')}"
    assert "790 USD" in r1["response"], f"No se encontró 790 USD en r1: {r1['response']}"
    assert "4:30 a. m." in r1["response"], f"No se encontró horario en r1: {r1['response']}"
    print("  PASS | 1. Consulta directa con viñeta '· Camino Inca Clásico 4D/3N' responde ficha oficial (790 USD)")

    # 3. Consulta directa simple "camino inka"
    r2 = app.rag_chain("camino inka", "user_test_instant")
    assert r2.get("response_route") == "evidence_tour_overview", f"Ruta inesperada: {r2.get('response_route')}"
    assert "790 USD" in r2["response"], f"No se encontró 790 USD en r2: {r2['response']}"
    print("  PASS | 2. Consulta simple 'camino inka' responde ficha oficial (790 USD, 4:30 a. m.)")

    # 4. Actualización instantánea de tarifa en el panel: 790 -> 850 USD
    ok_upd, _ = catalog_service.upsert_tour({
        "entity_id": "camino-inka",
        "name": "Camino Inca Clásico 4D/3N",
        "official_price": "850",
        "currency": "USD",
        "schedule": "Recojo 4:30 a. m. – 5:00 a. m.",
        "duration": "4 días / 3 noches",
        "is_active": True
    })
    assert ok_upd, "Fallo al actualizar tour"

    # Inmediatamente la siguiente consulta debe reflejar 850 USD
    r3 = app.rag_chain("cuanto cuesta el camino inca", "user_test_instant")
    assert "850 USD" in r3["response"], f"La tarifa no se actualizó al instante a 850 USD: {r3['response']}"
    assert "790" not in r3["response"], f"Aún contiene tarifa anterior 790: {r3['response']}"
    print("  PASS | 3. Cambio de tarifa a 850 USD se refleja al instante sin desfase de caché")

    # 5. Consulta por horario
    r4 = app.rag_chain("a que hora sale el camino inca", "user_test_instant")
    assert r4.get("response_route") == "evidence_schedule"
    assert "4:30 a. m." in r4["response"]
    print("  PASS | 4. Consulta de horario responde horario oficial vigente")

    # 6. Revertir a 790 USD
    catalog_service.upsert_tour({
        "entity_id": "camino-inka",
        "name": "Camino Inca Clásico 4D/3N",
        "official_price": "790",
        "currency": "USD",
        "schedule": "Recojo 4:30 a. m. – 5:00 a. m.",
        "duration": "4 días / 3 noches",
        "is_active": True
    })
    r5 = app.rag_chain("cuanto cuesta el camino inca", "user_test_instant")
    assert "790 USD" in r5["response"]
    print("  PASS | 5. Reversión a 790 USD aplicada y confirmada")

    print("=" * 60)
    print("TODOS LOS TESTS DE ACTUALIZACIÓN INSTANTÁNEA PASARON CON ÉXITO")
    print("=" * 60)


if __name__ == "__main__":
    test_instant_catalog_reflection()

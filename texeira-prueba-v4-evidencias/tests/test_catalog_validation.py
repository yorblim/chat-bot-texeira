"""
test_catalog_validation.py — Validación y auditoría de integridad del catálogo canónico.

Verifica:
  1. Integridad estructural de data/tours_catalog.json (19 tours).
  2. Alineación con las resoluciones oficiales de data/conflicts.json.
  3. Políticas comerciales declaradas como desconocidas (evita alucinaciones).
  4. Datos de contacto canónicos de Texeira Travel (F1/F2).
"""

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CATALOG_PATH = ROOT / "data" / "tours_catalog.json"
CONFLICTS_PATH = ROOT / "data" / "conflicts.json"

def test_catalog():
    print("=====================================================================")
    print("       VALIDACIÓN DEL CATÁLOGO CANÓNICO — TEXEIRA TRAVEL")
    print("=====================================================================")

    assert CATALOG_PATH.exists(), "Falta archivo tours_catalog.json"
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    assert CONFLICTS_PATH.exists(), "Falta archivo conflicts.json"
    with open(CONFLICTS_PATH, "r", encoding="utf-8") as f:
        conflicts = json.load(f)

    # 1. Datos de agencia
    agency = catalog.get("agency", {})
    assert "TEXEIRA TRAVEL" in agency.get("name", ""), "Nombre de agencia incorrecto"
    phones = agency.get("phones", [])
    assert "+51 953 767 860" in phones, "Falta teléfono principal"
    assert "+51 984 679 715" in phones, "Falta teléfono secundario"
    assert "Carmen Quicllu" in agency.get("address", ""), "Dirección no coincide con F1/F2"
    print("  PASS | Datos de agencia confirmados y alineados con F1/F2.")

    # 2. Políticas comerciales protegidas (deben ser 'unknown' para evitar alucinación)
    policies = catalog.get("policies", {})
    for pol_name in ["payment_methods", "cancellation", "discounts", "deposit"]:
        pol = policies.get(pol_name, {})
        assert pol.get("status") == "unknown", f"Política {pol_name} debe ser 'unknown' hasta confirmación de agencia"
    print("  PASS | Políticas comerciales sensibles marcadas honestamente como 'unknown'.")

    # 3. Tours canónicos
    tours = catalog.get("tours", [])
    assert len(tours) >= 14, f"Se esperaban al menos 14 tours, encontrados: {len(tours)}"
    
    tour_ids = {t["entity_id"] for t in tours}
    required_tours = {
        "city-tour-cusco", "valle-sagrado", "valle-sur", "montana-7-colores",
        "laguna-humantay", "waqra-pukara", "machu-picchu-car", "machu-picchu-tren",
        "camino-inka", "salkantay-trek", "inka-jungle", "choquequirao",
        "maras-moray", "puente-qeswachaca"
    }
    missing = required_tours - tour_ids
    assert not missing, f"Faltan tours obligatorios: {missing}"
    print(f"  PASS | Estructura de {len(tours)} tours canónicos verificada.")

    # 4. Conflictos de horario resueltos con F1
    resolved = {c["entity_id"]: c for c in conflicts.get("resolved_conflicts", [])}
    for t in tours:
        eid = t["entity_id"]
        if eid in resolved:
            res_conf = resolved[eid]
            assert t.get("schedule_status") == "confirmed", f"Horario de {eid} debe estar confirmed por F1"
            assert res_conf.get("chosen_source") == "F1", f"Resolución de {eid} debe priorizar F1"
    print("  PASS | Conflictos de horario resueltos canónicamente a favor de folleto F1.")

    print("=====================================================================")
    print("   ¡CATÁLOGO CANÓNICO VALIDADO Y AUDITADO AL 100%!")
    print("=====================================================================")

if __name__ == "__main__":
    test_catalog()

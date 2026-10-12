"""sync_core_tours.py — Sincroniza y activa los tours principales de Cusco en Neon PostgreSQL.
Tours actualizados y activados:
  - city-tour-cusco (15 USD, Medio día, 13:30-18:30 / 10:00-14:00)
  - valle-sagrado (25 USD, Full Day, 07:30-18:30)
  - montana-7-colores (30 USD, Full Day, 04:30-17:00)
  - laguna-humantay (30 USD, Full Day, 04:30-17:00)
  - machu-picchu-tren (290 USD, Full Day, 04:00-05:00 recojo)
Preserva los ya activos: camino-inka, inka-jungle, maras-moray.
"""
import os
import sys
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

gcloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
REMOTE_DB = ""
try:
    res_db = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "1", "--secret=DATABASE_URL", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    if res_db.returncode == 0 and res_db.stdout.strip():
        REMOTE_DB = res_db.stdout.strip()
except Exception:
    pass

import catalog_service
from db_adapter import get_db_session

TOURS_A_ACTIVAR = [
    {
        "entity_id": "city-tour-cusco",
        "name": "City Tour Cusco",
        "official_price": "15",
        "currency": "USD",
        "schedule": "13:30-18:30 / 10:00-14:00",
        "duration": "Medio día",
        "includes": "Transporte turístico compartido, guía profesional bilingüe.",
        "excludes": "Boleto Turístico del Cusco (BTC), ingreso a Koricancha.",
        "is_active": True
    },
    {
        "entity_id": "valle-sagrado",
        "name": "Valle Sagrado de los Incas",
        "official_price": "25",
        "currency": "USD",
        "schedule": "07:30-18:30",
        "duration": "Full Day",
        "includes": "Transporte turístico compartido, guía profesional bilingüe, almuerzo buffet.",
        "excludes": "Boleto Turístico del Cusco (BTC), ingreso a Salineras de Maras.",
        "is_active": True
    },
    {
        "entity_id": "montana-7-colores",
        "name": "Montaña de 7 Colores",
        "official_price": "30",
        "currency": "USD",
        "schedule": "04:30-17:00",
        "duration": "Full Day",
        "includes": "Transporte turístico compartido ida y vuelta, guía profesional bilingüe, desayuno, almuerzo buffet, botiquín y balón de oxígeno.",
        "excludes": "Boleto de ingreso a la comunidad, alquiler de caballo opcional.",
        "is_active": True
    },
    {
        "entity_id": "laguna-humantay",
        "name": "Laguna Humantay",
        "official_price": "30",
        "currency": "USD",
        "schedule": "04:30-17:00",
        "duration": "Full Day",
        "includes": "Transporte turístico compartido ida y vuelta, guía profesional bilingüe, desayuno, almuerzo buffet, bastones de trekking, balón de oxígeno.",
        "excludes": "Boleto de ingreso a la comunidad de Mollepata, alquiler de caballo opcional.",
        "is_active": True
    },
    {
        "entity_id": "machu-picchu-tren",
        "name": "Machu Picchu en Tren",
        "official_price": "290",
        "currency": "USD",
        "schedule": "Recojo 04:00 a. m. - 05:00 a. m.",
        "duration": "Full Day",
        "includes": "Traslado Cusco - estación de tren ida y vuelta, ticket de tren turístico ida y vuelta, bus Consettur subida y bajada, boleto de ingreso a la Llaqta de Machu Picchu (circuito asignado), guía profesional bilingüe.",
        "excludes": "Almuerzo en Aguas Calientes, propinas.",
        "is_active": True
    }
]

def sincronizar_destino(nombre, db_url=None):
    if db_url:
        os.environ["DATABASE_URL"] = db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    import db_adapter
    db_adapter._ENGINE = None
    db_adapter._PG_INITIALIZED = False

    print(f"\n--- Sincronizando destino: {nombre} ---")
    catalog_service.init_catalog_db()

    with get_db_session() as conn:
        conn.execute("DELETE FROM catalog_field_overrides WHERE entity_id = 'city-tour-cusco' AND field = 'duration'")
        conn.execute("DELETE FROM catalog_field_overrides WHERE entity_id = 'city-tour-cusco' AND field = 'official_price'")

    for tour_data in TOURS_A_ACTIVAR:
        eid = tour_data["entity_id"]
        ok, msg = catalog_service.upsert_tour(tour_data)
        if ok:
            print(f"  [OK] {eid}: activado con precio {tour_data['official_price']} USD, {tour_data['duration']}")
        else:
            print(f"  [ERROR] {eid}: {msg}")

    catalog_service.invalidate_catalog_cache()
    activos = catalog_service.get_all_tours(active_only=True)
    print(f"  Total activos en {nombre}: {len(activos)}")

def sincronizar():
    print("=" * 70)
    print("  SINCRONIZANDO Y ACTIVANDO TOURS PRINCIPALES (LOCAL + NEON)")
    print("=" * 70)

    # 1. Sincronizar SQLite local
    sincronizar_destino("SQLite Local", db_url=None)

    # 2. Sincronizar Neon PostgreSQL si está disponible
    if REMOTE_DB:
        sincronizar_destino("Neon PostgreSQL (Remoto)", db_url=REMOTE_DB)

    print("\n" + "=" * 70)
    print("  SINCRONIZACIÓN DUAL COMPLETADA CON ÉXITO")
    print("=" * 70)

if __name__ == "__main__":
    sincronizar()

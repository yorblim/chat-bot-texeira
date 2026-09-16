"""
Prueba de /test-chat via HTTP.
Valida que los indicadores se devuelvan correctamente en la API.
"""
import os, sys, json, time
sys.path.insert(0, '.')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

import app

# Usar el test_client de FastAPI para probar sin levantar servidor
from fastapi.testclient import TestClient
client = TestClient(app.app)

print("=" * 60)
print("PRUEBA DE /test-chat VIA HTTP")
print("=" * 60)

cases = [
    # (mensaje, user_id, checks)
    ("Contacta a un asesor para consultar los detalles", "http-f1",
     {"is_escalation": False, "resolved_autonomously": True}),
    ("Te recomiendo contactar a un asesor", "http-f1b",
     {"is_escalation": False, "resolved_autonomously": True}),
    ("¿Hay cupos disponibles para mañana?", "http-f2",
     {"needs_agency_confirmation": True}),
    ("Is there availability for tomorrow?", "http-f2b",
     {"needs_agency_confirmation": True}),
    ("¿Cuál es el precio en soles de Salkantay?", "http-f3",
     {"resolved_autonomously": False, "needs_agency_confirmation": True}),
    ("¿Puedo pagar con Yape?", "http-f4",
     {"needs_agency_confirmation": True}),
    ("Can I pay with Yape?", "http-f4b",
     {"needs_agency_confirmation": True}),
]

ok_count = 0
fail_count = 0

for msg, uid, checks in cases:
    resp = client.post("/test-chat", json={"message": msg, "user_id": uid})
    data = resp.json()
    
    status = "OK"
    details = []
    for key, expected in checks.items():
        actual = data.get(key)
        if actual != expected:
            status = "FALLO"
            details.append(f"{key}={actual} (esperado {expected})")
    
    if status == "OK":
        ok_count += 1
        print(f"  [OK] {msg[:50]}...")
    else:
        fail_count += 1
        print(f"  [FALLO] {msg[:50]}...")
        for d in details:
            print(f"    {d}")
    print(f"    response: {data.get('response', '')[:100]}...")
    print()

print("=" * 60)
print(f"RESULTADO /test-chat: {ok_count}/{ok_count+fail_count} pasaron")
print("=" * 60)

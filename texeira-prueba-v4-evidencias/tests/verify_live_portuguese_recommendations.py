"""Two deterministic live PT turns, scoped auth and cleanup of our own rows.

No WhatsApp transport, handoff request, catalog writes, or deliberate LLM call.
This probe verifies the API and persistence, not actual model quality/delivery.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = "https://texeira-whatsapp-1038134693816.us-central1.run.app"
GCLOUD = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def secret(name, version):
    result = subprocess.run(
        [GCLOUD, "secrets", "versions", "access", str(version),
         "--secret=" + name, "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True, check=True,
    )
    value = result.stdout.strip()
    if not value:
        raise RuntimeError("Missing required secret: " + name)
    return value


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    password = secret("ADMIN_PASSWORD", 2)
    os.environ["DATABASE_URL"] = secret("DATABASE_URL", 1)
    headers = {"Authorization": "Basic " + base64.b64encode(
        ("admin:" + password).encode()).decode(), "Content-Type": "application/json"}
    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(BASE + "/api/catalog/tours", headers=headers)
    with opener.open(request, timeout=60) as response:
        assert response.status == 200
        tours = json.load(response)
    assert {tour["entity_id"] for tour in tours} == {"camino-inka", "inka-jungle", "maras-moray"}
    print("PASS catálogo activo: se mantienen los tres tours autorizados", flush=True)

    user_id = "synthetic-open-pt-live-" + uuid4().hex
    from db_adapter import get_db_session
    results = []
    try:
        for message in (
            "Recomende um passeio de meio dia, não quero fazer caminhadas.",
            "4 dias",
        ):
            payload = json.dumps({"user_id": user_id, "message": message}).encode()
            request = urllib.request.Request(BASE + "/test-chat", data=payload, headers=headers)
            with opener.open(request, timeout=60) as response:
                assert response.status == 200
                result = json.load(response)
            assert result["response_route"] == "evidence_recommendation", result["response_route"]
            assert result["detected_language"] == "pt"
            assert result["quick_buttons"]
            assert all(button["id"].endswith(":pt") for button in result["quick_buttons"])
            assert not result["escalated_to_human"]
            results.append(result)
        assert "Maras" in results[0]["response"] and "Meio dia" in results[0]["response"]
        assert results[0]["resolved_autonomously"] is True
        assert results[1]["resolved_autonomously"] is False
        assert results[1]["needs_confirmation"] is True
        assert "preferências" in results[1]["response"]
        print("PASS recomendación PT: Maras–Moray; respuesta y botones conservan PT", flush=True)
        print("PASS seguimiento '4 dias': conserva la restricción y queda pendiente", flush=True)
        with get_db_session() as conn:
            rows = conn.execute("SELECT detected_language FROM interactions WHERE user_id = ?", (user_id,)).fetchall()
            assert len(rows) == 2 and all(row[0] == "pt" for row in rows)
            memory = conn.execute("SELECT messages FROM conversation_memory WHERE user_id = ?", (user_id,)).fetchall()
            assert len(memory) == 1 and len(json.loads(memory[0][0])) == 4
        print("PASS persistencia: dos interacciones PT y cuatro turnos", flush=True)
    finally:
        with get_db_session() as conn:
            conn.execute("DELETE FROM interactions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM conversation_memory WHERE user_id = ?", (user_id,))
        print("CLEANUP: eliminadas únicamente nuestras filas sintéticas", flush=True)
    print("No se certifica calidad del LLM ni recepción real en WhatsApp.")


if __name__ == "__main__":
    main()

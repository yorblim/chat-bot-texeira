"""Tests locales del webhook WhatsApp v4 (sin Meta real)."""
import sys, os, json, hashlib, hmac
sys.path.insert(0, os.path.dirname(__file__))
os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'true'

from pathlib import Path
from dotenv import dotenv_values

vals = dotenv_values(Path(__file__).resolve().parent.parent / 'texeira-chatbot' / '.env')
APP_SECRET = vals.get('META_APP_SECRET', '')

import urllib.request, urllib.error

PASSED = 0
FAILED = 0

def sign(body_bytes):
    return 'sha256=' + hmac.new(APP_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()

def post(payload, sig=None):
    body = json.dumps(payload).encode()
    if sig is None:
        sig = sign(body)
    req = urllib.request.Request(
        'http://127.0.0.1:8022/webhook',
        data=body,
        headers={'Content-Type': 'application/json', 'X-Hub-Signature-256': sig}
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw.decode("utf-8", errors="replace") if raw else ""}
        return e.code, data

def test(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS | {name}")
    else:
        FAILED += 1
        print(f"  FAIL | {name} {detail}")

print("=" * 60)
print("WEBHOOK TESTS - v4-evidencias WhatsApp")
print("=" * 60)

# Test A: numeric phone as message
print("\n--- A: numeric phone message ---")
p = {"entry": [{"changes": [{"value": {
    "messages": [{"from": "51921484423", "text": {"body": "51921484423"}, "type": "text", "id": "test_a_001"}],
    "contacts": [{"wa_id": "51921484423"}],
    "metadata": {"phone_number_id": "test_pid"}
}}]}]}
status, resp = post(p)
test("A: status 200", status == 200, f"got {status}")
test("A: has response", "response" in resp, str(list(resp.keys())))
test("A: response is string", isinstance(resp.get("response", ""), str))

# Test B: second phone number
print("\n--- B: second phone number ---")
p = {"entry": [{"changes": [{"value": {
    "messages": [{"from": "51910779284", "text": {"body": "51910779284"}, "type": "text", "id": "test_b_001"}],
    "contacts": [{"wa_id": "51910779284"}],
    "metadata": {"phone_number_id": "test_pid"}
}}]}]}
status, resp = post(p)
test("B: status 200", status == 200, f"got {status}")
test("B: has response", "response" in resp)

# Test C: BSUID known
print("\n--- C: BSUID ---")
p = {"entry": [{"changes": [{"value": {
    "messages": [{"from": "0000000000000000", "text": {"body": "Hola"}, "type": "text", "id": "test_c_001"}],
    "contacts": [{"wa_id": "0000000000000000", "user_id": "test_bsuid_ABC"}],
    "metadata": {"phone_number_id": "test_pid"}
}}]}]}
status, resp = post(p)
test("C: status 200", status == 200, f"got {status}")
test("C: response has greeting", len(resp.get("response", "")) > 0)

# Test D: delivery statuses
print("\n--- D: delivery status ---")
p = {"entry": [{"changes": [{"value": {
    "statuses": [{"status": "sent", "id": "wamid.test_123", "recipient_id": "51921484423"}]
}}]}]}
status, resp = post(p)
test("D: status 200", status == 200, f"got {status}")

# Test E: empty message (no messages, no statuses)
print("\n--- E: empty webhook ---")
p = {"entry": [{"changes": [{"value": {
    "metadata": {"phone_number_id": "test_pid"}
}}]}]}
status, resp = post(p)
test("E: status 200 or 400", status in (200, 400), f"got {status}")

# Test F: invalid signature
print("\n--- F: invalid signature ---")
body = json.dumps({"test": True}).encode()
status, resp = post({"test": True}, sig="sha256=invalid_signature_abc123def456")
test("F: rejected (403)", status == 403, f"got {status}")

# Test G: tourism query (evidence layer)
print("\n--- G: tourism query (no LLM) ---")
p = {"entry": [{"changes": [{"value": {
    "messages": [{"from": "51999999999", "text": {"body": "Tienen Salkantay?"}, "type": "text", "id": "test_g_001"}],
    "contacts": [{"wa_id": "51999999999"}],
    "metadata": {"phone_number_id": "test_pid"}
}}]}]}
status, resp = post(p)
test("G: status 200", status == 200, f"got {status}")
test("G: mentions Salkantay", "salkantay" in resp.get("response", "").lower())

# Test H: conflict query (no LLM)
print("\n--- H: conflict query (no LLM) ---")
p = {"entry": [{"changes": [{"value": {
    "messages": [{"from": "51999999998", "text": {"body": "Cuál es el horario del City Tour?"}, "type": "text", "id": "test_h_001"}],
    "contacts": [{"wa_id": "51999999998"}],
    "metadata": {"phone_number_id": "test_pid"}
}}]}]}
status, resp = post(p)
test("H: status 200", status == 200, f"got {status}")
test("H: indicates conflict/confirm", any(w in resp.get("response", "").lower() for w in ["confirmar", "diferente", "conflicto"]))

# Test I: Yape query (unknown)
print("\n--- I: Yape query (unknown) ---")
p = {"entry": [{"changes": [{"value": {
    "messages": [{"from": "51999999997", "text": {"body": "Aceptan Yape?"}, "type": "text", "id": "test_i_001"}],
    "contacts": [{"wa_id": "51999999997"}],
    "metadata": {"phone_number_id": "test_pid"}
}}]}]}
status, resp = post(p)
test("I: status 200", status == 200, f"got {status}")
test("I: indicates unknown", any(w in resp.get("response", "").lower() for w in ["no hay", "confirmar", "agencia", "no hay info"]))

print(f"\n{'='*60}")
print(f"RESULTADO: {PASSED} PASS / {FAILED} FAIL / {PASSED+FAILED} TOTAL")
print(f"{'='*60}")

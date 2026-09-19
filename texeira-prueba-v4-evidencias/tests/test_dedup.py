"""Tests de deduplicacion de webhook WhatsApp - sin Groq."""
import sys, os, hashlib, hmac, json, sqlite3, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from dotenv import dotenv_values

vals = dotenv_values(Path(__file__).resolve().parent.parent / 'texeira-chatbot' / '.env')
APP_SECRET = vals.get('META_APP_SECRET', '') or 'test_dedup_secret'

os.environ['TEXEIRA_ENABLE_WHATSAPP'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

TEST_DB = Path(__file__).resolve().parent / 'test_dedup.db'
if TEST_DB.exists():
    TEST_DB.unlink()

import app

# Set META vars AFTER app import (app clears them when WHATSAPP=false)
app.META_APP_SECRET = APP_SECRET
os.environ['META_APP_SECRET'] = APP_SECRET
app.SQLITE_DB_PATH = str(TEST_DB)

import database
database.init_db(str(TEST_DB))

from fastapi.testclient import TestClient
client = TestClient(app.app)

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

def sign(body_bytes):
    return 'sha256=' + hmac.new(APP_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()

def make_wa_payload(message_id, text, from_phone="51921484423"):
    return {
        "entry": [{"changes": [{"value": {
            "messages": [{"from": from_phone, "text": {"body": text}, "type": "text", "id": message_id}],
            "contacts": [{"wa_id": from_phone}],
            "metadata": {"phone_number_id": "test_pid"}
        }}]}]
    }

def post_webhook(payload):
    body = json.dumps(payload).encode()
    sig = sign(body)
    return client.post("/webhook", content=body, headers={
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig
    })

# Track calls
rag_calls = []
send_calls = []
original_rag = app.rag_chain
original_send = app.send_whatsapp_message

def tracking_rag(question, user_id='default'):
    rag_calls.append({"question": question, "user_id": user_id})
    return original_rag(question, user_id)

def tracking_send(**kwargs):
    send_calls.append(kwargs)
    return True

app.rag_chain = tracking_rag
app.send_whatsapp_message = tracking_send

print("=" * 60)
print("TESTS DEDUPLICACION WEBHOOK - v4-evidencias")
print("=" * 60)

# TEST A: Same message_id 3 times
print("\n--- TEST A: 3x same message_id ---")
rag_calls.clear()
send_calls.clear()

p = make_wa_payload("wamid.TEST001", "Hola")
r1 = post_webhook(p)
time.sleep(0.5)
r2 = post_webhook(p)
time.sleep(0.5)
r3 = post_webhook(p)

test("A: all 3 return 200", r1.status_code == 200 and r2.status_code == 200 and r3.status_code == 200,
     f"statuses={r1.status_code},{r2.status_code},{r3.status_code}")
test("A: first not dedup", r1.json().get("dedup") != True, f"r1={r1.json()}")
test("A: second is dedup", r2.json().get("dedup") == True, f"r2={r2.json()}")
test("A: third is dedup", r3.json().get("dedup") == True, f"r3={r3.json()}")
test("A: rag_chain called exactly 1 time", len(rag_calls) == 1, f"calls={len(rag_calls)}")
test("A: send_whatsapp_message called exactly 1 time", len(send_calls) == 1, f"calls={len(send_calls)}")

# TEST B: Different message_ids, same text
print("\n--- TEST B: different message_ids, same text ---")
rag_calls.clear()
send_calls.clear()

p1 = make_wa_payload("wamid.TEST002", "Hola")
p2 = make_wa_payload("wamid.TEST003", "Hola")
r1 = post_webhook(p1)
time.sleep(0.5)
r2 = post_webhook(p2)

test("B: both return 200", r1.status_code == 200 and r2.status_code == 200)
test("B: neither is dedup", r1.json().get("dedup") != True and r2.json().get("dedup") != True)
test("B: rag_chain called 2 times", len(rag_calls) == 2, f"calls={len(rag_calls)}")
test("B: send_whatsapp_message called 2 times", len(send_calls) == 2, f"calls={len(send_calls)}")

# TEST C: status=sent -> 0 responses
print("\n--- TEST C: status=sent ---")
rag_calls.clear()
send_calls.clear()

p = {"entry": [{"changes": [{"value": {
    "statuses": [{"status": "sent", "id": "wamid.TEST_status", "recipient_id": "51921484423"}]
}}]}]}
r = post_webhook(p)
test("C: returns 200", r.status_code == 200)
test("C: rag_chain not called", len(rag_calls) == 0)
test("C: send not called", len(send_calls) == 0)

# TEST D: status=delivered -> 0 responses
print("\n--- TEST D: status=delivered ---")
rag_calls.clear()
send_calls.clear()

p = {"entry": [{"changes": [{"value": {
    "statuses": [{"status": "delivered", "id": "wamid.TEST_delivered", "recipient_id": "51921484423"}]
}}]}]}
r = post_webhook(p)
test("D: returns 200", r.status_code == 200)
test("D: rag_chain not called", len(rag_calls) == 0)

# TEST E: status=read -> 0 responses
print("\n--- TEST E: status=read ---")
rag_calls.clear()
send_calls.clear()

p = {"entry": [{"changes": [{"value": {
    "statuses": [{"status": "read", "id": "wamid.TEST_read", "recipient_id": "51921484423"}]
}}]}]}
r = post_webhook(p)
test("E: returns 200", r.status_code == 200)
test("E: rag_chain not called", len(rag_calls) == 0)

# TEST F: Duplicate survives server restart (SQLite persistence)
print("\n--- TEST F: persistence across restart ---")
rag_calls.clear()
send_calls.clear()

p = make_wa_payload("wamid.TEST001", "Hola")
r = post_webhook(p)
test("F: still detected as dedup after 'restart'", r.json().get("dedup") == True)
test("F: rag_chain not called", len(rag_calls) == 0)

# TEST G: Concurrent requests with same message_id
print("\n--- TEST G: concurrent requests ---")
rag_calls.clear()
send_calls.clear()

p = make_wa_payload("wamid.TEST_CONCURRENT", "Hola")
results = []
for _ in range(5):
    results.append(post_webhook(p))

dedup_count = sum(1 for r in results if r.json().get("dedup") == True)
non_dedup_count = sum(1 for r in results if r.json().get("dedup") != True)

test("G: all return 200", all(r.status_code == 200 for r in results))
test("G: exactly 1 non-dedup", non_dedup_count == 1, f"non_dedup={non_dedup_count}")
test("G: 4 dedup", dedup_count == 4, f"dedup={dedup_count}")
test("G: rag_chain called at most 1 time", len(rag_calls) <= 1, f"calls={len(rag_calls)}")

# Cleanup
app.rag_chain = original_rag
app.send_whatsapp_message = original_send

print(f"\n{'='*60}")
print(f"RESULTADO: {PASSED} PASS / {FAILED} FAIL / {PASSED+FAILED} TOTAL")
print(f"{'='*60}")

sys.exit(1 if FAILED else 0)

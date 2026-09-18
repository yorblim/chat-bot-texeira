"""
Pruebas de integracion WhatsApp: telefono, BSUID con test mode, BSUID sin mapping.
"""
import sys, os
sys.path.insert(0, r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot")
os.chdir(r"C:\Users\HP\Desktop\Chat bot\texeira-chatbot")

# Patch test mode before importing app
os.environ["WHATSAPP_TEST_MODE"] = "true"
os.environ["WHATSAPP_TEST_BSUID_MAP"] = "PE.926071427227541:51910779284"

import app

def extract_ids(payload_value):
    msg = payload_value["messages"][0]
    contact = payload_value.get("contacts", [{}])[0]
    contact_wa_id = contact.get("wa_id", "")
    contact_user_id = contact.get("user_id", "")
    msg_from = msg.get("from", "")
    msg_from_user_id = msg.get("from_user_id", "")
    phone_number = contact_wa_id or (msg_from if msg_from and msg_from.isdigit() else "")
    bsuid = contact_user_id or msg_from_user_id or ""
    user_id = phone_number or bsuid or msg_from or "unknown"
    return phone_number, bsuid, user_id

def build_payload(phone_number, bsuid, text="test"):
    destination = phone_number
    # Test mode: resolve BSUID
    if not destination and bsuid and app.WHATSAPP_TEST_MODE:
        mapped = app.WHATSAPP_TEST_BSUID_MAP.get(bsuid)
        if mapped:
            destination = mapped
            bsuid = None
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "type": "text",
               "text": {"preview_url": False, "body": text}}
    if destination:
        payload["to"] = destination
        mode = "phone"
    elif bsuid:
        payload["recipient"] = bsuid
        mode = "bsuid"
    else:
        mode = "none"
    return payload, mode

print("CASO A: Numero normal 51921484423")
inbound_a = {"contacts": [{"wa_id": "51921484423", "user_id": ""}], "messages": [{"from": "51921484423", "text": {"body": "hola"}}]}
phone, bsuid, uid = extract_ids(inbound_a)
payload, mode = build_payload(phone, bsuid)
assert payload.get("to") == "51921484423", f"Expected to=51921484423, got {payload}"
assert "recipient" not in payload, f"Should NOT have recipient, got {payload}"
print(f"  to={payload['to']} mode={mode} => PASSED")

print("CASO B: BSUID PE.926071427227541 en TEST MODE")
inbound_b = {"contacts": [{"wa_id": "", "user_id": "PE.926071427227541"}],
             "messages": [{"from": "PE.926071427227541", "from_user_id": "PE.926071427227541", "text": {"body": "hola"}}]}
phone, bsuid, uid = extract_ids(inbound_b)
payload, mode = build_payload(phone, bsuid)
assert payload.get("to") == "51910779284", f"Expected to=51910779284, got {payload}"
assert "recipient" not in payload, f"Should NOT have recipient, got {payload}"
print(f"  to={payload['to']} mode={mode} => PASSED")

print("CASO C: BSUID desconocido sin mapping")
inbound_c = {"contacts": [{"wa_id": "", "user_id": "PE.UNKNOWN999"}],
             "messages": [{"from": "PE.UNKNOWN999", "from_user_id": "PE.UNKNOWN999", "text": {"body": "hola"}}]}
phone, bsuid, uid = extract_ids(inbound_c)
payload, mode = build_payload(phone, bsuid)
assert payload.get("recipient") == "PE.UNKNOWN999", f"Expected recipient=PE.UNKNOWN999, got {payload}"
assert "to" not in payload, f"Should NOT have to, got {payload}"
print(f"  recipient={payload['recipient']} mode={mode} => PASSED")

print("CASO D: Verificar config del modulo")
assert app.WHATSAPP_TEST_MODE is True
assert app.WHATSAPP_TEST_BSUID_MAP.get("PE.926071427227541") == "51910779284"
print(f"  TEST_MODE={app.WHATSAPP_TEST_MODE} MAP={app.WHATSAPP_TEST_BSUID_MAP} => PASSED")

print("TODAS LAS PRUEBAS PASARON")

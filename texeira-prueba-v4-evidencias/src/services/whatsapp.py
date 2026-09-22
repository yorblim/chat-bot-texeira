"""Servicio de mensajería para WhatsApp Cloud API (Meta Graph API v26.0)."""
import os
from typing import Optional
import httpx

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")

# Modo de prueba WhatsApp: resolución de BSUID a número de teléfono mapeado
WHATSAPP_TEST_MODE = os.getenv("WHATSAPP_TEST_MODE", "false").lower() == "true"
_WHATSAPP_TEST_BSUID_MAP_RAW = os.getenv("WHATSAPP_TEST_BSUID_MAP", "")
WHATSAPP_TEST_BSUID_MAP = {}
if _WHATSAPP_TEST_BSUID_MAP_RAW:
    for pair in _WHATSAPP_TEST_BSUID_MAP_RAW.split(","):
        pair = pair.strip()
        if ":" in pair:
            bsuid, phone = pair.split(":", 1)
            WHATSAPP_TEST_BSUID_MAP[bsuid.strip()] = phone.strip()


def send_whatsapp_message(
    text: str,
    to_phone: Optional[str] = None,
    recipient_bsuid: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    to_number: Optional[str] = None,
) -> bool:
    """Envía un mensaje de texto de salida a la Graph API de Meta (WhatsApp Cloud API).

    Soporta dos modos de envío:
      1. Por teléfono: usar to_phone (o to_number para retrocompatibilidad).
         Genera payload con "to": "<phone>".
      2. Por BSUID: usar recipient_bsuid.
         Genera payload con "recipient": "<BSUID>".

    En WHATSAPP_TEST_MODE, los BSUIDs mapeados se resuelven a teléfono.
    """
    destination = to_phone or to_number

    # Test mode: resolve BSUID to mapped phone number
    if not destination and recipient_bsuid and WHATSAPP_TEST_MODE:
        mapped_phone = WHATSAPP_TEST_BSUID_MAP.get(recipient_bsuid)
        if mapped_phone:
            print(f"[WA TEST MAP] bsuid={recipient_bsuid} mapped_phone={mapped_phone}")
            destination = mapped_phone
            recipient_bsuid = None  # use phone path
        else:
            print(f"[WA TEST MAP] bsuid={recipient_bsuid} NOT in BSUID_MAP, falling back to recipient")

    token = os.getenv("META_ACCESS_TOKEN", "") or META_ACCESS_TOKEN
    if not token or token.startswith("tu-token"):
        mode = "phone" if destination else "bsuid"
        dest = destination or recipient_bsuid or "unknown"
        print('[WA] Envío no realizado: credenciales ausentes.')
        return False

    target_phone_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID", "") or META_PHONE_NUMBER_ID
    if not target_phone_id:
        print(f"[WA WARNING] No se configuro phone_number_id")
        return False

    url = f"https://graph.facebook.com/v26.0/{target_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    if destination:
        payload["to"] = destination
        mode = "phone"
    elif recipient_bsuid:
        payload["recipient"] = recipient_bsuid
        mode = "bsuid"
    else:
        print("[WA ERROR] No destination provided (neither phone nor BSUID)")
        return False

    dest = destination or recipient_bsuid
    print(f"[WA OUTBOUND] mode={mode} destination={dest} phone_number_id={target_phone_id}")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp_body = resp.text[:300]
            print(f"[WA SEND RESPONSE] status_code={resp.status_code} body={resp_body}")
            if resp.status_code in (200, 201):
                try:
                    resp_json = resp.json()
                    wamid = resp_json.get("messages", [{}])[0].get("id", "")
                    if wamid:
                        print(f"[WA MSG ID] wamid={wamid}")
                except Exception:
                    pass
                print(f"[WA] Mensaje enviado exitosamente a {dest} (mode={mode})")
                return True
            else:
                print(f"[WA ERROR] HTTP {resp.status_code}: {resp_body}")
                return False
    except Exception as e:
        print(f"[WA ERROR] Excepcion al enviar mensaje: {e}")
        return False


def send_whatsapp_image(
    image_url: str,
    caption: str = "",
    to_phone: Optional[str] = None,
    recipient_bsuid: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    to_number: Optional[str] = None,
) -> bool:
    """Envía un mensaje con imagen de alta calidad a WhatsApp Cloud API."""
    destination = to_phone or to_number
    if not destination and recipient_bsuid and WHATSAPP_TEST_MODE:
        mapped_phone = WHATSAPP_TEST_BSUID_MAP.get(recipient_bsuid)
        if mapped_phone:
            destination = mapped_phone
            recipient_bsuid = None

    token = os.getenv("META_ACCESS_TOKEN", "") or META_ACCESS_TOKEN
    if not token or token.startswith("tu-token"):
        return False

    target_phone_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID", "") or META_PHONE_NUMBER_ID
    if not target_phone_id:
        return False

    url = f"https://graph.facebook.com/v26.0/{target_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "image",
        "image": {
            "link": image_url,
        }
    }
    if caption:
        payload["image"]["caption"] = caption[:1024]

    if destination:
        payload["to"] = destination
    elif recipient_bsuid:
        payload["recipient"] = recipient_bsuid
    else:
        return False

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            print(f"[WA IMAGE OUTBOUND] status={resp.status_code} url={image_url[:60]}")
            return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[WA IMAGE ERROR] {e}")
        return False


def send_whatsapp_document(
    document_url: str,
    filename: str = "folleto.pdf",
    caption: str = "",
    to_phone: Optional[str] = None,
    recipient_bsuid: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    to_number: Optional[str] = None,
) -> bool:
    """Envía un documento PDF a WhatsApp Cloud API (Meta Graph API v26.0)."""
    destination = to_phone or to_number
    if not destination and recipient_bsuid and WHATSAPP_TEST_MODE:
        mapped_phone = WHATSAPP_TEST_BSUID_MAP.get(recipient_bsuid)
        if mapped_phone:
            destination = mapped_phone
            recipient_bsuid = None

    token = os.getenv("META_ACCESS_TOKEN", "") or META_ACCESS_TOKEN
    if not token or token.startswith("tu-token"):
        return False

    target_phone_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID", "") or META_PHONE_NUMBER_ID
    if not target_phone_id:
        return False

    url = f"https://graph.facebook.com/v26.0/{target_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "document",
        "document": {
            "link": document_url,
            "filename": filename or "folleto.pdf",
        }
    }
    if caption:
        payload["document"]["caption"] = caption[:1024]

    if destination:
        payload["to"] = destination
    elif recipient_bsuid:
        payload["recipient"] = recipient_bsuid
    else:
        return False

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            print(f"[WA DOCUMENT OUTBOUND] status={resp.status_code} filename={filename} url={document_url[:60]}")
            return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[WA DOCUMENT ERROR] {e}")
        return False


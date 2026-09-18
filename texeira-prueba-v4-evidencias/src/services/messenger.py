"""Servicio de mensajería para Facebook Messenger vía Graph API."""
import os
import httpx

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")


def send_messenger_message(text: str, psid: str) -> bool:
    """Envía un mensaje de texto a un usuario de Facebook Messenger vía Graph API.

    Requiere FB_PAGE_ACCESS_TOKEN configurado. Si está vacío, registra el intento
    y retorna False sin lanzar excepción.
    """
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "") or FB_PAGE_ACCESS_TOKEN
    if not token:
        print(f"[FB] Envío no realizado: FB_PAGE_ACCESS_TOKEN ausente (psid={psid}).")
        return False

    url = "https://graph.facebook.com/v26.0/me/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text},
    }
    print(f"[FB OUTBOUND] psid={psid} chars={len(text)}")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp_body = resp.text[:300]
            print(f"[FB SEND RESPONSE] status_code={resp.status_code} body={resp_body}")
            if resp.status_code in (200, 201):
                try:
                    mid = resp.json().get("message_id", "")
                    if mid:
                        print(f"[FB MSG ID] message_id={mid}")
                except Exception:
                    pass
                print(f"[FB] Mensaje enviado exitosamente a psid={psid}")
                return True
            else:
                print(f"[FB ERROR] HTTP {resp.status_code}: {resp_body}")
                return False
    except Exception as e:
        print(f"[FB ERROR] Excepcion al enviar mensaje: {e}")
        return False

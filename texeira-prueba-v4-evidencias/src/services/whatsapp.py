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


class WhatsAppSendResult:
    """Representa el resultado de un intento de envío a Meta WhatsApp Cloud API.

    Permite distinguir formalmente:
      - 'accepted': HTTP 200/201 recibido de Graph API (envío aceptado por Meta).
      - 'rejected': HTTP 4xx devuelto por Graph API (error de cliente/autenticación/parámetros).
      - 'uncertain': Resultado incierto por timeout de red (httpx.TimeoutException),
                     falla de transporte (httpx.RequestError) o HTTP 5xx del servidor.

    Implementa __bool__ para compatibilidad retroactiva total (evalúa a True solo si es 'accepted').
    """

    def __init__(
        self,
        status: str,
        accepted: bool = False,
        status_code: Optional[int] = None,
        wamid: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.status = status  # 'accepted', 'rejected', 'uncertain'
        self.accepted = bool(accepted)
        self.status_code = status_code
        self.wamid = wamid
        self.error = error

    @property
    def is_accepted(self) -> bool:
        return self.status == "accepted"

    @property
    def is_uncertain(self) -> bool:
        return self.status == "uncertain"

    @property
    def is_rejected(self) -> bool:
        return self.status == "rejected"

    def __bool__(self) -> bool:
        return self.is_accepted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, bool):
            return self.is_accepted == other
        if isinstance(other, str):
            return self.status == other
        if isinstance(other, WhatsAppSendResult):
            return self.status == other.status and self.wamid == other.wamid
        return False

    def __repr__(self) -> str:
        return f"<WhatsAppSendResult status={self.status} accepted={self.accepted} wamid={self.wamid}>"


def is_interactive_format_error(status_code: int, resp_body: str) -> bool:
    """Determina si un error 4xx de Meta es exclusivo del formato interactivo y amerita fallback a texto plano.

    No aplica fallback ante credenciales inválidas, ventanas comerciales de 24h caducadas,
    límites de cuota, ni errores de destinatario/teléfono inválido, ya que el mensaje de
    texto estándar fallaría por la misma causa y no se debe enmascarar el error.
    """
    if status_code != 400:
        return False
    body_lower = resp_body.lower()
    # Errores definitivos que NUNCA ameritan fallback de formato (fallarían idénticamente con texto):
    non_format_patterns = [
        "131047", "24 hours", "re-engagement",  # ventana de 24h caducada
        "oauth", "access token", "expired", "permission", "authorization",  # autenticación / permisos
        "rate limit", "throttled", "spam", "user not found",  # cuotas / límites
        "not a valid whatsapp", "not a valid number", "invalid phone",  # destinatario inválido
        "parameter to", "param to", "field to", "recipient", "131026",  # campo destinatario
    ]
    if any(pat in body_lower for pat in non_format_patterns):
        return False

    # Errores de botones / interactivo / estructura donde el texto plano sí resuelve el problema de formato:
    format_patterns = [
        "interactive", "button", "header", "footer", "action",
        "invalid parameter", "payload", "character", "length", "too long",
    ]
    return any(pat in body_lower for pat in format_patterns)


def send_whatsapp_message(
    text: str,
    to_phone: Optional[str] = None,
    recipient_bsuid: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    to_number: Optional[str] = None,
    buttons: Optional[list] = None,
) -> WhatsAppSendResult:
    """Envía un mensaje de texto de salida a la Graph API de Meta (WhatsApp Cloud API).

    Soporta dos modos de envío:
      1. Por teléfono: usar to_phone (o to_number para retrocompatibilidad).
         Genera payload con "to": "<phone>".
      2. Por BSUID: usar recipient_bsuid.
         Genera payload con "recipient": "<BSUID>".

    Si se especifica `buttons` (lista de hasta 3 botones), delega a
    send_whatsapp_interactive_buttons para renderizar botones de respuesta rápida nativos.

    En WHATSAPP_TEST_MODE, los BSUIDs mapeados se resuelven a teléfono.
    """
    if buttons:
        return send_whatsapp_interactive_buttons(
            text=text,
            buttons=buttons,
            to_phone=to_phone,
            recipient_bsuid=recipient_bsuid,
            phone_number_id=phone_number_id,
            to_number=to_number,
        )

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
        return WhatsAppSendResult(status="rejected", accepted=False, error="Credenciales ausentes")

    target_phone_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID", "") or META_PHONE_NUMBER_ID
    if not target_phone_id:
        print(f"[WA WARNING] No se configuro phone_number_id")
        return WhatsAppSendResult(status="rejected", accepted=False, error="phone_number_id no configurado")

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
        return WhatsAppSendResult(status="rejected", accepted=False, error="Destino no provisto")

    dest = destination or recipient_bsuid
    print(f"[WA OUTBOUND] mode={mode} destination={dest} phone_number_id={target_phone_id}")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp_body = resp.text[:300]
            print(f"[WA SEND RESPONSE] status_code={resp.status_code} body={resp_body}")
            if resp.status_code in (200, 201):
                wamid = None
                try:
                    resp_json = resp.json()
                    wamid = resp_json.get("messages", [{}])[0].get("id", "")
                    if wamid:
                        print(f"[WA MSG ID] wamid={wamid}")
                except Exception:
                    pass
                print(f"[WA] Mensaje enviado exitosamente a {dest} (mode={mode})")
                return WhatsAppSendResult(status="accepted", accepted=True, status_code=resp.status_code, wamid=wamid)
            elif resp.status_code >= 500:
                print(f"[WA SERVER ERROR] HTTP {resp.status_code}: {resp_body}. Resultado incierto.")
                return WhatsAppSendResult(status="uncertain", accepted=False, status_code=resp.status_code, error=resp_body)
            else:
                print(f"[WA ERROR] HTTP {resp.status_code}: {resp_body}")
                return WhatsAppSendResult(status="rejected", accepted=False, status_code=resp.status_code, error=resp_body)
    except (httpx.TimeoutException, httpx.RequestError) as e:
        print(f"[WA TIMEOUT/NETWORK ERROR] {type(e).__name__}: {e}. Resultado incierto.")
        return WhatsAppSendResult(status="uncertain", accepted=False, error=str(e))
    except Exception as e:
        print(f"[WA ERROR] Excepcion al enviar mensaje: {e}")
        return WhatsAppSendResult(status="rejected", accepted=False, error=str(e))


def send_whatsapp_interactive_buttons(
    text: str,
    buttons: list,
    to_phone: Optional[str] = None,
    recipient_bsuid: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    to_number: Optional[str] = None,
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None,
) -> WhatsAppSendResult:
    """Envía un mensaje interactivo con botones de respuesta rápida (Quick Reply Buttons) a Meta WhatsApp Cloud API.

    Reglas de la API de Meta Graph:
      - Máximo 3 botones permitidos.
      - El título de cada botón debe tener <= 20 caracteres (emojis incluidos).
      - El cuerpo del mensaje (body.text) debe tener <= 1024 caracteres.
      - Si excede 1024 caracteres o no hay botones válidos, recurre automáticamente a send_whatsapp_message().
      - Si Meta devuelve un error 400 de formato interactivo, recurre a send_whatsapp_message() como salvaguarda.
      - Si ocurre timeout o error de red, devuelve WhatsAppSendResult(status='uncertain') sin fallback.
    """
    destination = to_phone or to_number

    # Modo de prueba: mapear BSUID a número de teléfono
    if not destination and recipient_bsuid and WHATSAPP_TEST_MODE:
        mapped_phone = WHATSAPP_TEST_BSUID_MAP.get(recipient_bsuid)
        if mapped_phone:
            print(f"[WA TEST MAP] bsuid={recipient_bsuid} mapped_phone={mapped_phone}")
            destination = mapped_phone
            recipient_bsuid = None
        else:
            print(f"[WA TEST MAP] bsuid={recipient_bsuid} NOT in BSUID_MAP, falling back to recipient")

    token = os.getenv("META_ACCESS_TOKEN", "") or META_ACCESS_TOKEN
    if not token or token.startswith("tu-token"):
        print("[WA] Envío interactivo no realizado: credenciales ausentes.")
        return WhatsAppSendResult(status="rejected", accepted=False, error="Credenciales ausentes")

    target_phone_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID", "") or META_PHONE_NUMBER_ID
    if not target_phone_id:
        print("[WA WARNING] No se configuro phone_number_id para interactivo")
        return WhatsAppSendResult(status="rejected", accepted=False, error="phone_number_id no configurado")

    # Validar y truncar botones (máximo 3, id <= 256, title <= 20)
    formatted_buttons = []
    if buttons:
        for b in buttons[:3]:
            b_id = str(b.get("id", "")).strip()[:256]
            b_title = str(b.get("title", "")).strip()[:20]
            if b_id and b_title:
                formatted_buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": b_id,
                        "title": b_title
                    }
                })

    # Si no hay botones válidos o el texto excede 1024 caracteres, enviar como mensaje de texto estándar
    if not formatted_buttons or len(text) > 1024:
        return send_whatsapp_message(
            text=text,
            to_phone=to_phone,
            recipient_bsuid=recipient_bsuid,
            phone_number_id=phone_number_id,
            to_number=to_number,
            buttons=None,
        )

    interactive_payload = {
        "type": "button",
        "body": {
            "text": text
        },
        "action": {
            "buttons": formatted_buttons
        }
    }
    if header_text:
        interactive_payload["header"] = {"type": "text", "text": header_text[:60]}
    if footer_text:
        interactive_payload["footer"] = {"text": footer_text[:60]}

    url = f"https://graph.facebook.com/v26.0/{target_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "interactive",
        "interactive": interactive_payload,
    }

    if destination:
        payload["to"] = destination
        mode = "phone"
    elif recipient_bsuid:
        payload["recipient"] = recipient_bsuid
        mode = "bsuid"
    else:
        print("[WA ERROR] No destination provided for interactive")
        return WhatsAppSendResult(status="rejected", accepted=False, error="Destino ausente para interactivo")

    dest = destination or recipient_bsuid
    button_titles = [b["reply"]["title"] for b in formatted_buttons]
    safe_titles = [t.encode("ascii", "replace").decode("ascii") for t in button_titles]
    print(f"[WA INTERACTIVE OUTBOUND] mode={mode} destination={dest} buttons={safe_titles}")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp_body = resp.text[:300]
            print(f"[WA INTERACTIVE RESPONSE] status_code={resp.status_code} body={resp_body}")
            if resp.status_code in (200, 201):
                wamid = None
                try:
                    resp_json = resp.json()
                    wamid = resp_json.get("messages", [{}])[0].get("id", "")
                    if wamid:
                        print(f"[WA MSG ID] wamid={wamid} (interactive)")
                except Exception:
                    pass
                print(f"[WA] Mensaje interactivo enviado exitosamente a {dest}")
                return WhatsAppSendResult(status="accepted", accepted=True, status_code=resp.status_code, wamid=wamid)
            elif is_interactive_format_error(resp.status_code, resp_body):
                print(f"[WA INTERACTIVE REJECTED] HTTP {resp.status_code}: {resp_body}, fallback controlado a texto plano por error de formato interactivo...")
                return send_whatsapp_message(
                    text=text,
                    to_phone=to_phone,
                    recipient_bsuid=recipient_bsuid,
                    phone_number_id=phone_number_id,
                    to_number=to_number,
                    buttons=None,
                )
            elif 400 <= resp.status_code < 500:
                print(f"[WA INTERACTIVE REJECTED] HTTP {resp.status_code}: {resp_body}. Rechazado por Meta sin fallback (no es error de formato).")
                return WhatsAppSendResult(status="rejected", accepted=False, status_code=resp.status_code, error=resp_body)
            else:
                print(f"[WA INTERACTIVE SERVER ERROR] HTTP {resp.status_code}: {resp_body}. Resultado incierto; sin fallback para evitar duplicación.")
                return WhatsAppSendResult(status="uncertain", accepted=False, status_code=resp.status_code, error=resp_body)
    except (httpx.TimeoutException, httpx.RequestError) as e:
        print(f"[WA INTERACTIVE TIMEOUT/NETWORK ERROR] {type(e).__name__}: {e}. Resultado incierto; sin fallback a texto para evitar duplicación.")
        return WhatsAppSendResult(status="uncertain", accepted=False, error=str(e))
    except Exception as e:
        print(f"[WA INTERACTIVE ERROR] Excepcion inesperada al enviar interactivo: {e}. Sin fallback.")
        return WhatsAppSendResult(status="rejected", accepted=False, error=str(e))


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


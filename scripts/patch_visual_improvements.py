import re

app_path = r"c:\Users\HP\Desktop\Chat bot\texeira-prueba-v4-evidencias\app.py"
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Patch the send_whatsapp_message / send_messenger_message block
start_marker = 'dest = destination or recipient_bsuid\n    print(f"[WA OUTBOUND] mode={mode} destination={dest} phone_number_id={target_phone_id}")'
end_marker = '# Mensaje de fallback estricto'

idx_start = content.find(start_marker)
idx_end = content.find(end_marker)

if idx_start != -1 and idx_end != -1:
    idx_start_replace = idx_start + len(start_marker)
    new_middle_block = '''
    try:
        import httpx
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
    to_phone: str = None,
    recipient_bsuid: str = None,
    phone_number_id: str = None,
    to_number: str = None,
) -> bool:
    """Envía un mensaje con imagen de alta calidad a WhatsApp Cloud API."""
    destination = to_phone or to_number
    if not destination and recipient_bsuid and WHATSAPP_TEST_MODE:
        mapped_phone = WHATSAPP_TEST_BSUID_MAP.get(recipient_bsuid)
        if mapped_phone:
            destination = mapped_phone
            recipient_bsuid = None

    if not META_ACCESS_TOKEN or META_ACCESS_TOKEN.startswith("tu-token"):
        return False

    target_phone_id = phone_number_id or META_PHONE_NUMBER_ID
    if not target_phone_id:
        return False

    url = f"https://graph.facebook.com/v26.0/{target_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
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
        import httpx
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            print(f"[WA IMAGE OUTBOUND] status={resp.status_code} url={image_url[:60]}")
            return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[WA IMAGE ERROR] {e}")
        return False


def get_tour_image_data(text: str):
    """Detecta tours o intención en la conversación y retorna (url_imagen, caption_elegante)."""
    t = text.lower()
    images = {
        'machu_picchu': (
            'https://images.unsplash.com/photo-1526392060635-9d6019884377?w=800&q=80',
            '🏔️ *Machu Picchu Mágico* — ¡La Maravilla del Mundo te espera con Texeira Travel Tour! ✨'
        ),
        'montana_7_colores': (
            'https://images.unsplash.com/photo-1589802829985-817e51171b92?w=800&q=80',
            '🌈 *Montaña de 7 Colores (Vinicunca)* — Paisajes andinos únicos a más de 5,000 m.s.n.m.'
        ),
        'laguna_humantay': (
            'https://images.unsplash.com/photo-1580619305218-8423a7ef79b4?w=800&q=80',
            '💎 *Laguna Humantay* — Espejo de aguas turquesas y nevados sagrados de Cusco.'
        ),
        'valle_sagrado': (
            'https://images.unsplash.com/photo-1509299349698-dd22323b5963?w=800&q=80',
            '🌾 *Valle Sagrado de los Incas* — Tradición viva, fortalezas y paisajes imponentes.'
        ),
        'maras_moray': (
            'https://images.unsplash.com/photo-1589308078059-be1415eab4c3?w=800&q=80',
            '🧂 *Maras y Moray* — Salineras milenarias y laboratorio agrícola inca.'
        ),
        'city_tour': (
            'https://images.unsplash.com/photo-1587595431973-160d0d94add1?w=800&q=80',
            '🏛️ *City Tour Cusco* — Plaza de Armas, templos sagrados y centros arqueológicos.'
        ),
        'cusco_general': (
            'https://images.unsplash.com/photo-1568402102990-bc541580b59f?w=800&q=80',
            '✨ *Texeira Travel Tour* — Tu mejor experiencia de viaje en el corazón de los Andes. 🇵🇪'
        ),
    }

    if any(k in t for k in ['machu picchu', 'aguas calientes', 'tren a machu', 'ciudadela']):
        return images['machu_picchu']
    elif any(k in t for k in ['7 colores', 'montaña de 7', 'vinicunca', 'rainbow']):
        return images['montana_7_colores']
    elif any(k in t for k in ['humantay', 'laguna']):
        return images['laguna_humantay']
    elif any(k in t for k in ['valle sagrado', 'pisac', 'ollantaytambo', 'urubamba']):
        return images['valle_sagrado']
    elif any(k in t for k in ['maras', 'moray', 'salineras']):
        return images['maras_moray']
    elif any(k in t for k in ['city tour', 'koricancha', 'sacsayhuam', 'tambomachay', 'qenqo']):
        return images['city_tour']
    elif any(k in t for k in ['tour', 'tours', 'paquete', 'paquetes', 'cusco', 'viaje', 'precio', 'opcion', 'visitar']):
        return images['cusco_general']
    return None


def format_whatsapp_text(text: str) -> str:
    """Mejora la estética visual de los mensajes para WhatsApp."""
    if not text:
        return text

    # 1. Eliminar etiquetas de markdown image ![...](...) para que no se vean como texto roto
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # 2. Corregir asteriscos anidados comunes producidos por LLMs
    emoji_replacements = [
        (r'(?i)\*\s*\*(?:horario|horarios):\*', '🕒 *Horarios:*'),
        (r'(?i)\*\s*\*(?:itinerario|recorrido|visitas):\*', '📍 *Recorrido:*'),
        (r'(?i)\*\s*\*(?:incluye|servicios incluidos):\*', '🎒 *Incluye:*'),
        (r'(?i)\*\s*\*(?:no incluye|exclusiones|excluye):\*', '❌ *No incluye:*'),
        (r'(?i)\*\s*\*(?:precio|precios|tarifa|costo):\*', '🏷️ *Tarifa:*'),
        (r'(?i)\*\s*\*(?:recomendaci[oó]n|recomendaciones):\*', '💡 *Recomendación:*'),
        (r'(?i)\*\s*\*(?:importante|nota):\*', '⚠️ *Nota:*'),
        (r'(?i)\*\s*\*(?:duraci[oó]n):\*', '⏱️ *Duración:*'),
    ]
    for pattern, repl in emoji_replacements:
        text = re.sub(pattern, repl, text)

    # 3. Limpiar viñetas restantes '* *Texto*' -> '• *Texto*'
    text = re.sub(r'^\s*\*\s+\*(.*?)\*', r'• *\1*', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\*\s+(?!\*)', r'• ', text, flags=re.MULTILINE)

    # 4. Asignar emojis elegantes a listas numeradas
    tour_number_emojis = {
        '1': '🏛️', '2': '🚆', '3': '🌈', '4': '💎', '5': '🌾', '6': '🧂', '7': '🥾', '8': '☀️'
    }
    def _add_num_emoji(match):
        num = match.group(1)
        rest = match.group(2)
        em = tour_number_emojis.get(num, '📍')
        return f"\\n{em} *{num}. {rest.strip()}*"

    text = re.sub(r'(?m)^\s*(\d+)\.\s*\*+(.*?)\*+', _add_num_emoji, text)

    # 5. Reducir saltos de línea repetidos
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def send_messenger_message(text: str, psid: str) -> bool:
    """
    Envía un mensaje de texto a un usuario de Facebook Messenger vía Graph API.

    Requiere FB_PAGE_ACCESS_TOKEN configurado. Si está vacío, registra el intento
    y retorna False sin lanzar excepción (mismo patrón que send_whatsapp_message).

    Args:
        text: Texto a enviar.
        psid: Page-Scoped User ID del destinatario (identificador de Messenger).

    Returns:
        True si la API devuelve 200/201, False en caso contrario.
    """
    if not FB_PAGE_ACCESS_TOKEN:
        print(f"[FB] Envío no realizado: FB_PAGE_ACCESS_TOKEN ausente (psid={psid}).")
        return False

    url = "https://graph.facebook.com/v26.0/me/messages"
    headers = {
        "Authorization": f"Bearer {FB_PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text},
    }
    print(f"[FB OUTBOUND] psid={psid} chars={len(text)}")
    try:
        import httpx
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

'''
    content = content[:idx_start_replace] + new_middle_block + "\n\n" + content[idx_end:]
    print("Direct slice replacement successful!")
else:
    print(f"Could not find markers: {idx_start}, {idx_end}")

# 2. Patch SYSTEM_PROMPT rule 3
old_rule_3 = '''REGLA #3 — FORMATO E IMÁGENES:
Usa un formato conciso con viñetas para precios, itinerarios y horarios. Sé amable pero profesional.
IMPORTANTE: Cuando el contexto incluya URLs de imágenes (campo "images" del catálogo), incluye SIEMPRE una imagen representativa del tour al FINAL de tu respuesta, usando este formato exacto:
![Descripción corta de la imagen](URL de la imagen)
Incluye SOLO UNA imagen principal por tour (la primera del catálogo). Si el contexto no contiene imágenes, no inventes URLs.'''

new_rule_3 = '''REGLA #3 — DISEÑO VISUAL Y ESTÉTICA PARA WHATSAPP:
Tus respuestas deben tener un diseño visual premium, estructurado y atractivo, ideal para WhatsApp:
- Usa encabezados amables y elegantes con emojis turísticos (✨, 🏔️, 🏛️, 🌈, 🚆, 🎒, 📍, 🕒).
- Resalta títulos de tours siempre en *Negrita*.
- Usa viñetas con emojis temáticos en vez de guiones o asteriscos feos:
  🕒 *Horarios:* ...
  📍 *Recorrido:* ...
  🎒 *Incluye:* ...
  🎟️ *Entradas:* ...
  💡 *Recomendación:* ...
  NUNCA uses asteriscos anidados como '* *Horarios:*'.
- Si el turista consulta sobre presupuesto ("no es mucho mi presupuesto", "económico", "barato", "descuentos"):
  Sé sumamente empático, cálido y orientador. Menciona que en Texeira Travel Tour contamos con opciones ideales y accesibles (como City Tour Cusco de medio día o Valle Sagrado), e invítalo cordialmente a coordinar con un asesor humano para consultar ofertas y promociones personalizadas a su presupuesto.
- Concluye con un mensaje cálido de invitación o pregunta de seguimiento (ejemplo: "¿Te gustaría consultar disponibilidad o cotizar alguno de estos destinos? ✨").'''

if old_rule_3 in content:
    content = content.replace(old_rule_3, new_rule_3)
    print("Replaced SYSTEM_PROMPT REGLA #3 successfully!")
else:
    print("Could not find old REGLA #3 in SYSTEM_PROMPT!")

# 3. Patch _process_message to clean text and send images
old_wa_process = '''                if channel == "whatsapp":
                    accepted = user_id != 'unknown' and send_whatsapp_message(
                        text=bot_response,
                        to_phone=phone_number if phone_number else None,
                        recipient_bsuid=bsuid if bsuid else None,
                        phone_number_id=phone_number_id,
                    )
                    operational.finish(event_id, 'api_accepted' if accepted else 'send_failed',
                                       generation_ms, (time.perf_counter()-metric_start)*1000, rag_result)'''

new_wa_process = '''                if channel == "whatsapp":
                    bot_response_clean = format_whatsapp_text(bot_response)
                    accepted = user_id != 'unknown' and send_whatsapp_message(
                        text=bot_response_clean,
                        to_phone=phone_number if phone_number else None,
                        recipient_bsuid=bsuid if bsuid else None,
                        phone_number_id=phone_number_id,
                    )
                    # Enviar imagen temática relevante de alta calidad para embellecer visualmente el chat
                    try:
                        tour_img_info = get_tour_image_data(user_message + " " + bot_response)
                        if tour_img_info and accepted:
                            img_url, img_caption = tour_img_info
                            send_whatsapp_image(
                                image_url=img_url,
                                caption=img_caption,
                                to_phone=phone_number if phone_number else None,
                                recipient_bsuid=bsuid if bsuid else None,
                                phone_number_id=phone_number_id,
                            )
                    except Exception as img_err:
                        print(f"[WA IMAGE SEND ATTEMPT] {img_err}")

                    operational.finish(event_id, 'api_accepted' if accepted else 'send_failed',
                                       generation_ms, (time.perf_counter()-metric_start)*1000, rag_result)'''

if old_wa_process in content:
    content = content.replace(old_wa_process, new_wa_process)
    print("Replaced _process_message successfully!")
else:
    print("Could not find old_wa_process in content!")

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Finished writing patched app.py")

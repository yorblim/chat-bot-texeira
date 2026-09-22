"""Motor visual y formateo estilizado para WhatsApp.

Incluye la selección inteligente de imágenes oficiales verificadas y el formateo
estético de viñetas, horarios, recorridos, emojis de listas y bloques de contacto.
"""
import os
import re


def is_photo_requested(user_msg: str) -> bool:
    """Determina si el usuario solicita explícitamente ver fotos o imágenes."""
    if not user_msg:
        return False
    u = user_msg.lower()
    # Descartar si el usuario especifica una negación hacia las fotos
    if re.search(r"\b(no|sin|without|don't|do not)\b.*?\b(fotos?|im[aá]genes?|photos?|pictures?)\b", u):
        return False
    return bool(re.search(r"\b(fotos?|im[aá]genes?|fotograf[ií]as?|photos?|pictures?|images?)\b", u))


def is_brochure_requested(user_msg: str) -> bool:
    """Determina si el usuario solicita explícitamente un folleto, brochure o documento PDF."""
    if not user_msg:
        return False
    u = user_msg.lower()
    # Descartar si el usuario especifica una negación hacia los folletos
    if re.search(r"\b(no|sin|without|don't|do not)\b.*?\b(folletos?|brochures?|pdfs?|documentos?)\b", u):
        return False
    return bool(re.search(r"\b(folletos?|brochures?|pdfs?|documentos?|itinerario\s+en\s+pdf|gu[ií]a\s+en\s+pdf)\b", u))


def get_tour_image_data(text: str, user_msg: str = "", entity_id: str = ""):
    """Detecta tours o intención en la conversación y retorna (url_imagen, caption_elegante).
    Usa tanto las imágenes cargadas dinámicamente en el catálogo como las canónicas verificadas.
    """
    base_url = os.getenv('APP_BASE_URL', 'https://texeira-whatsapp-1038134693816.us-central1.run.app').rstrip('/')

    canonical_images = {
        'machu-picchu-tren': (f"{base_url}/images/machu_picchu.jpg", '🏔️ *Machu Picchu Mágico* — ¡La Maravilla del Mundo te espera con Texeira Travel Tour! ✨'),
        'machu-picchu-car': (f"{base_url}/images/machu_picchu.jpg", '🏔️ *Machu Picchu By Car* — Aventura escénica hacia la Maravilla del Mundo con Texeira Travel. ✨'),
        'montana-7-colores': (f"{base_url}/images/montana_7_colores.jpg", '🌈 *Montaña de 7 Colores (Vinicunca)* — Paisajes andinos únicos a más de 5,000 m.s.n.m.'),
        'laguna-humantay': (f"{base_url}/images/laguna_humantay.jpg", '💎 *Laguna Humantay* — Espejo de aguas turquesas y nevados sagrados de Cusco.'),
        'valle-sagrado': (f"{base_url}/images/valle_sagrado.jpg", '🌾 *Valle Sagrado de los Incas* — Tradición viva, fortalezas y paisajes imponentes.'),
        'valle-sur': (f"{base_url}/images/cusco_general.jpg", '🏺 *Valle Sur Cusco* — Tipón, Pikillacta y la Capilla Sixtina de América en Andahuaylillas.'),
        'maras-moray': (f"{base_url}/images/maras_moray.jpg", '🧂 *Maras y Moray* — Salineras milenarias y laboratorio agrícola inca.'),
        'maras-moray-cuatrimoto': (f"{base_url}/images/maras_moray.jpg", '🏍️ *Maras y Moray en Cuatrimoto* — Adrenalina, paisajes y cultura en el Valle Sagrado.'),
        'city-tour-cusco': (f"{base_url}/images/city_tour_cusco.jpg", '🏛️ *City Tour Cusco* — Plaza de Armas, templos sagrados y centros arqueológicos.'),
    }

    # 1. Identificar la entidad
    target_eid = entity_id or ""
    if not target_eid:
        try:
            from trial_support import detect_entity_from_question
            detected = detect_entity_from_question(user_msg or text)
            if detected and detected != "unknown":
                target_eid = detected
        except Exception:
            pass

    # 2. Consultar si hay foto dinámica registrada en catalog_service
    if target_eid:
        try:
            import catalog_service
            tour = catalog_service.get_tour(target_eid)
            if tour and tour.get("photo_filename"):
                photo_file = tour["photo_filename"]
                caption = f"📸 *{tour.get('name', target_eid)}* — ¡Descubre esta maravilla con Texeira Travel Tour! ✨"
                return (f"{base_url}/images/{photo_file}", caption)
        except Exception:
            pass

        # Si no hay foto dinámica cargada, usar el asset canónico si existe
        if target_eid in canonical_images:
            return canonical_images[target_eid]

    # 3. Si el usuario pidió fotos expresamente y no se detectó un tour particular
    if is_photo_requested(user_msg):
        return (f"{base_url}/images/cusco_general.jpg", '✨ *Texeira Travel Tour* — Tu mejor experiencia de viaje en el corazón de los Andes. 🇵🇪')

    return None


def get_tour_brochure_data(text: str, user_msg: str = "", entity_id: str = ""):
    """Detecta tours y retorna (url_folleto, nombre_archivo_display, caption) si existe un folleto PDF oficial."""
    base_url = os.getenv('APP_BASE_URL', 'https://texeira-whatsapp-1038134693816.us-central1.run.app').rstrip('/')

    target_eid = entity_id or ""
    if not target_eid:
        try:
            from trial_support import detect_entity_from_question
            detected = detect_entity_from_question(user_msg or text)
            if detected and detected != "unknown":
                target_eid = detected
        except Exception:
            pass

    if not target_eid:
        return None

    try:
        import catalog_service
        tour = catalog_service.get_tour(target_eid)
        if tour and tour.get("brochure_filename"):
            pdf_file = tour["brochure_filename"]
            tour_name = tour.get("name", target_eid)
            safe_name = re.sub(r"[^\w\s\-]", "", tour_name).strip().replace(" ", "_")
            display_name = f"Folleto_{safe_name}.pdf"
            caption = f"📄 *Folleto Informativo Oficial: {tour_name}*\n_Texeira Travel Tour Agency E.I.R.L._"
            return (f"{base_url}/brochures/{pdf_file}", display_name, caption)
    except Exception as e:
        print(f"[VISUAL BROCHURE RESOLVE ERROR] {e}")

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
        return f"\n{em} *{num}. {rest.strip()}*"

    text = re.sub(r'(?m)^\s*(\d+)\.\s*\*+(.*?)\*+', _add_num_emoji, text)

    # 5. Embellecer listado general de tours del evidence layer
    if 'Tours documentados (cupos por confirmar):' in text or 'Tours documentados por Texeira Travel:' in text:
        text = text.replace(
            'Tours documentados (cupos por confirmar):',
            '✨ *Tours y Paquetes Disponibles — Texeira Travel Tour* 🇵🇪\n_(Cupos y fechas sujetos a confirmación de la agencia)_\n'
        ).replace(
            'Tours documentados por Texeira Travel:',
            '✨ *Tours y Paquetes Disponibles — Texeira Travel Tour* 🇵🇪\n_(Cupos y fechas sujetos a confirmación de la agencia)_\n'
        )
        tour_emojis_map = {
            'city tour': '🏛️', 'valle sagrado': '🌾', 'valle sur': '🏺',
            '7 colores': '🌈', 'vinicunca': '🌈', 'humantay': '💎',
            'waqra': '🏰', 'by car': '🚐', 'tren': '🚆',
            'camino inka': '🥾', 'salkantay': '🥾', 'inka jungle': '🚴',
            'choquequirao': '🏕️', 'místico': '🔮', 'mistico': '🔮',
            'titicaca': '⛵', 'colca': '🦅', 'ruta del sol': '☀️',
            'maras': '🧂', 'cuatrimoto': '🏍️', 'q’eswachaca': '🌉',
            'qeswachaca': '🌉',
        }
        def _format_tour_bullet(match):
            name = match.group(1).strip()
            lower_name = name.lower()
            icon = '📍'
            for k, em in tour_emojis_map.items():
                if k in lower_name:
                    icon = em
                    break
            return f"• {icon} *{name}*"

        text = re.sub(r'(?m)^[-•]\s+([^\n]+)$', _format_tour_bullet, text)
        if '💬' not in text:
            text = text.strip() + '\n\n💬 *¿Cuál de estos destinos te gustaría conocer o cotizar?* ✨\n_Indícanos el tour y con gusto te daremos todos los detalles._'

    # 6. Embellecer bloque de contacto y dirección de la agencia
    if '+51 953 767 860' in text and 'Carmen Quicllu' in text:
        if len(text.strip()) < 180:
            text = (
                "📞 *Contacto Oficial — Texeira Travel Tour:*\n"
                "• 📱 WhatsApp / Teléfono: +51 953 767 860 / +51 984 679 715\n"
                "• 📧 Email: texeiratraveltour@hotmail.com\n"
                "• 📍 Oficina: Calle Carmen Quicllu N° 250, Centro Histórico de Cusco, Perú 🇵🇪\n"
                "• 🏢 Texeira Travel — Travel Agency E.I.R.L."
            )
        else:
            contact_formatted = (
                "\n\n📞 *Contacto Oficial — Texeira Travel Tour:*\n"
                "• 📱 WhatsApp / Teléfono: +51 953 767 860 / +51 984 679 715\n"
                "• 📍 Oficina: Calle Carmen Quicllu N° 250, Cusco 🇵🇪"
            )
            text = re.sub(r'Para contactar a la agencia:[\s\S]*?(?=Para registrar|$)', contact_formatted + '\n', text)
    elif 'carmen quicllu' in text.lower() and len(text.strip()) < 50:
        text = "📍 *Dirección de Oficina:*\nCalle Carmen Quicllu N° 250, Centro Histórico de Cusco, Perú 🇵🇪"

    # 7. Embellecer mensajes de confirmación de agencia
    if 'Este dato requiere confirmacion con la agencia:' in text:
        text = text.replace(
            'Este dato requiere confirmacion con la agencia:',
            'ℹ️ *Información por Confirmar con la Agencia:*\nEste dato requiere confirmación directa con Texeira Travel:'
        )
        text = text.replace(
            'Para registrar una solicitud de atención humana, escribe: asesor.',
            '\n💬 _Para solicitar atención personalizada con un asesor humano, escribe: *asesor*._'
        )

    # 8. Reducir saltos de línea repetidos
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

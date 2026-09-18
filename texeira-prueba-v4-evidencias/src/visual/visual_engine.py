"""Motor visual y formateo estilizado para WhatsApp.

Incluye la selección inteligente de imágenes oficiales verificadas y el formateo
estético de viñetas, horarios, recorridos, emojis de listas y bloques de contacto.
"""
import os
import re


def get_tour_image_data(text: str, user_msg: str = ""):
    """Detecta tours o intención en la conversación y retorna (url_imagen, caption_elegante).
    Usa las imágenes reales y verificadas de los atractivos de Cusco alojadas en el propio servidor.
    """
    base_url = os.getenv('APP_BASE_URL', 'https://texeira-whatsapp-a5uzavilla-uc.a.run.app').rstrip('/')

    images = {
        'machu_picchu': (
            f"{base_url}/images/machu_picchu.jpg",
            '🏔️ *Machu Picchu Mágico* — ¡La Maravilla del Mundo te espera con Texeira Travel Tour! ✨'
        ),
        'montana_7_colores': (
            f"{base_url}/images/montana_7_colores.jpg",
            '🌈 *Montaña de 7 Colores (Vinicunca)* — Paisajes andinos únicos a más de 5,000 m.s.n.m.'
        ),
        'laguna_humantay': (
            f"{base_url}/images/laguna_humantay.jpg",
            '💎 *Laguna Humantay* — Espejo de aguas turquesas y nevados sagrados de Cusco.'
        ),
        'valle_sagrado': (
            f"{base_url}/images/valle_sagrado.jpg",
            '🌾 *Valle Sagrado de los Incas* — Tradición viva, fortalezas y paisajes imponentes.'
        ),
        'maras_moray': (
            f"{base_url}/images/maras_moray.jpg",
            '🧂 *Maras y Moray* — Salineras milenarias y laboratorio agrícola inca.'
        ),
        'city_tour': (
            f"{base_url}/images/city_tour_cusco.jpg",
            '🏛️ *City Tour Cusco* — Plaza de Armas, templos sagrados y centros arqueológicos.'
        ),
        'cusco_general': (
            f"{base_url}/images/cusco_general.jpg",
            '✨ *Texeira Travel Tour* — Tu mejor experiencia de viaje en el corazón de los Andes. 🇵🇪'
        ),
    }

    t = text.lower()
    u = user_msg.lower() if user_msg else t

    # 1. Si el usuario preguntó específicamente por un destino/tour puntual:
    if any(k in u for k in ['machu picchu', 'aguas calientes', 'tren a machu', 'ciudadela']):
        return images['machu_picchu']
    if any(k in u for k in ['7 colores', 'montaña de 7', 'vinicunca', 'rainbow']):
        return images['montana_7_colores']
    if any(k in u for k in ['humantay', 'laguna']):
        return images['laguna_humantay']
    if any(k in u for k in ['valle sagrado', 'pisac', 'ollantaytambo', 'urubamba']):
        return images['valle_sagrado']
    if any(k in u for k in ['maras', 'moray', 'salineras']):
        return images['maras_moray']
    if any(k in u for k in ['city tour', 'koricancha', 'sacsayhuam', 'tambomachay', 'qenqo']):
        return images['city_tour']

    # 2. Si el texto de respuesta describe exclusiva o principalmente un tour puntual:
    if any(k in t for k in ['machu picchu', 'aguas calientes', 'ciudadela']):
        return images['machu_picchu']
    if any(k in t for k in ['7 colores', 'montaña de 7', 'vinicunca']):
        return images['montana_7_colores']
    if any(k in t for k in ['humantay', 'laguna humantay']):
        return images['laguna_humantay']
    if any(k in t for k in ['valle sagrado']):
        return images['valle_sagrado']
    if any(k in t for k in ['salineras de maras', 'maras y moray']):
        return images['maras_moray']

    # 3. Si el usuario pide explícitamente ver fotos o imágenes:
    if any(k in u for k in ['foto', 'fotos', 'imagen', 'imagenes', 'fotografia', 'photos', 'pictures']):
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

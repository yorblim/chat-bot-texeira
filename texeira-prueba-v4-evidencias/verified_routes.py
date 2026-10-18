"""Una sola decision de evidencia y un solo par de mensajes por turno."""
from contextlib import nullcontext
import re
from src.evidence import get_facts, detect_conflicts, is_product_confirmed

# Traducciones de conceptos documentados; los nombres de lugares se conservan.
EN_ITEMS = {
    'almuerzo':'Lunch', 'almuerzo_buffet':'Buffet lunch', 'desayuno':'Breakfast',
    'boleto_turistico':'Tourist ticket', 'bus_turistico':'Tourist bus',
    'bus_turistico_o_cuatrimotos_(modalidad_por_confirmar)':'Tourist bus or ATVs (option to be confirmed)',
    'casco_equipo_proteccion':'Helmet and protective equipment',
    'cuatrimotos_modernas':'Modern ATVs', 'entrada_montana':'Mountain entrance ticket',
    'guia_profesional':'Professional guide', 'guia_profesional_bilingue':'Professional bilingual guide',
    'oxigeno':'Oxygen', 'recojo_hotel':'Hotel pickup', 'transporte':'Transport',
    'transporte_ida_vuelta':'Round-trip transport', 'transporte_turistico':'Tourist transport',
    'visita_moray':'Visit to Moray', 'visita_salineras':'Visit to the salt mines',
    'maras_salineras':'Maras salt mines', 'salineras':'Salt mines',
}

def english_duration(value):
    if not value: return ""
    v = value
    v = v.replace('Medio día', 'Half day').replace('Medio dia', 'Half day').replace('medio día', 'half day')
    v = v.replace('Día completo', 'Full day').replace('Dia completo', 'Full day')
    v = v.replace('días', 'days').replace('dias', 'days').replace('día', 'day').replace('dia', 'day')
    v = v.replace('noches', 'nights').replace('noche', 'night')
    v = v.replace('horas', 'hours').replace('hora', 'hour')
    v = v.replace('itinerario publicado', 'published itinerary')
    v = v.replace('confirmar variante y noches', 'confirm variant and nights')
    return v


def portuguese_duration(value):
    """Translate duration labels, without deriving a missing catalog value."""
    v = str(value or '')
    for source, target in (
        ('Medio día', 'Meio dia'), ('Medio dia', 'Meio dia'),
        ('medio día', 'meio dia'), ('medio dia', 'meio dia'),
        ('Día completo', 'Dia inteiro'), ('Dia completo', 'Dia inteiro'),
        ('días', 'dias'), ('día', 'dia'), ('noches', 'noites'), ('noche', 'noite'),
        ('horas', 'horas'), ('itinerario publicado', 'itinerário publicado'),
        ('confirmar variante y noches', 'confirmar variante e noites'),
    ):
        v = v.replace(source, target)
    return v


def localized_duration(value, lang):
    """Translate documented labels; never infer missing duration or nights."""
    if lang == 'en':
        return english_duration(value)
    if lang == 'pt':
        return portuguese_duration(value)
    if lang not in ('fr', 'it'):
        return str(value or '')
    targets = {
        'fr': ('Demi-journée', 'Journée complète', 'jours', 'jour', 'nuits', 'nuit', 'heures', 'heure'),
        'it': ('Mezza giornata', 'Giornata intera', 'giorni', 'giorno', 'notti', 'notte', 'ore', 'ora'),
    }[lang]
    text = str(value or '')
    patterns = (r'medio\s+d[ií]a', r'd[ií]a\s+completo', r'd[ií]as', r'd[ií]a', r'noches', r'noche', r'horas', r'hora')
    for pattern, target in zip(patterns, targets):
        text = re.sub(r'\b' + pattern + r'\b', target, text, flags=re.I)
    return text


def is_open_tour_advice(q):
    """Interpretive questions must not become a general tour card.

    Shared by recommendation and factual routing. Merely naming a hiking
    activity is a preference, not advice about preparation for a named tour.
    """
    return bool(re.search(
        r'\b(?:prepar\w*|equipo|equipaje|equipamento|empacar|mochila|'
        r'ropa|roupa|vestir|calzado|calcado|zapat\w*|llevar|levar|'
        r'clima|temperatura|dificultad|dificuldade|exigencia|exigente|'
        r'altura|altitud|altitude|esfuerzo|cansado|experiencia|'
        r'bring|wear|pack|clothing|clothes|gear|equipment|weather|'
        r'difficult\w*|effort|steep|'
        r'como\s+es|como\s+e|que\s+actividades|what\s+activities|'
        r'how\s+is|por\s+que|expli\w*|cuenta\w*|tell\s+me\s+about)\b', q
    ))


def is_tour_comparison(q):
    return bool(re.search(
        r'\b(?:diferencia\w*|compar\w*|versus|vs|'
        r'entre\s+\w+.*?(?:y|and|e)\s+\w+|differ\w*)\b', q
    ))

_SOCIAL_INTENTS = {
    'hola': 'hola',
    'buenos dias': 'buenos dias',
    'buenas tardes': 'buenas tardes',
    'buenas noches': 'buenas noches',
    'hello': 'hello',
    'hi': 'hi',
    'hey': 'hi',
    'buenas': 'buenas',
    'gracias': 'gracias',
    'muchas gracias': 'gracias',
    'thanks': 'thanks',
    'thank you': 'thanks',
    'adios': 'adios',
    'chau': 'adios',
    'hasta luego': 'adios',
    'bye': 'bye',
    'que tal': 'saludo',
    'como estas': 'saludo',
}

_GREETING_ES = "¡Hola! 👋 Soy el asistente virtual de Texeira Travel. Puedo ayudarte a explorar tours y consultar información, o comunicarte con un asesor."
_GREETING_EN = "Hello! 👋 I am the virtual assistant of Texeira Travel. I can help you explore tours and check information, or connect you with an advisor."

_SOCIAL_RESPONSES = {
    'hola': _GREETING_ES,
    'buenos dias': _GREETING_ES,
    'buenas tardes': _GREETING_ES,
    'buenas noches': _GREETING_ES,
    'hello': _GREETING_EN,
    'hi': _GREETING_EN,
    'buenas': _GREETING_ES,
    'gracias': '¡Con gusto! 😊 Si necesitas algo más, aquí estamos.',
    'thanks': "You're welcome! 😊 Feel free to ask anything else.",
    'adios': '¡Hasta pronto! 🙌 Que disfrutes tu visita a Cusco.',
    'bye': 'Goodbye! 🙌 Enjoy your trip to Cusco!',
    'saludo': _GREETING_ES,
}

_HELP_RESPONSE = '¡Claro! 😊 Puedo ayudarte con *tours, horarios y servicios* de Texeira Travel.\n¿Qué destino te interesa? O escribe 👉 *asesor*'


def is_most_visited_query(q_norm: str) -> bool:
    """Detecta consultas sobre los tours más visitados, populares o imperdibles."""
    if re.search(
        r'\b(?:m[aá]s\s+(?:visitad\w*|popular\w*|pedid\w*|vendid\w*|solicitad\w*|conocid\w*)|'
        r'mais\s+(?:visitad\w*|popular\w*|pedid\w*|vendid\w*|procurad\w*)|'
        r'most\s+(?:visited|popular|requested|booked)|'
        r'plus\s+(?:visit[eé]\w*|populaire\w*)|'
        r'pi[uù]\s+(?:visitat\w*|popolar\w*)|'
        r'imperdibl\w*|imperd[ií]veis|must\s*see|top\s+tours?|top\s+destin\w*|'
        r'principales?\s+tours?|mejores\s+tours?|best\s+tours?|melhores\s+passeios)\b',
        q_norm
    ):
        return True
    if re.search(
        r'\b(?:que|cu[aá]les|quais|what)\s+(?:tours?|passeios?|lugares?|destinos?)\s+(?:son\s+los\s+|s[aã]o\s+os\s+|are\s+the\s+)?(?:m[aá]s|mais|most)\b',
        q_norm
    ):
        return True
    return False


def is_recommendation_query(q_norm: str) -> bool:
    """Detecta peticiones de recomendación, sugerencia o consejo, tolerando erratas."""
    if re.search(r'\b(?:recomie\w*|recomen\w*|recomnd\w*|sugier\w*|suger\w*|aconsej\w*|recommend\w*|suggest\w*|advice|advise|conseill\w*|consigli\w*)\b', q_norm):
        return True
    if re.search(r'\b(?:que|cual|cuales)\s+(?:me\s+)?(?:conviene|elijo|escojo|hago|tomar|hacer|tours?\s+(?:me\s+)?(?:das|ofreces))\b', q_norm):
        return True
    if re.search(r'\b(?:aclimat\w*|soroche|mal\s+de\s+altura|altitude\s+sickness|primer\s+d[ií]a|first\s+day|primeiro\s+dia)\b', q_norm):
        return True
    if is_most_visited_query(q_norm):
        return True
    return False


def is_rejection_query(q_norm: str) -> bool:
    """Detecta rechazos de opciones anteriores ('ninguno', 'ninguna', 'neither', 'none')."""
    return bool(re.search(r'\b(?:ning[uú]n\w*|nenhum\w*|neither|none(?:\s+of\s+(?:them|these|those))?)\b', q_norm))


def is_other_options_query(q_norm: str) -> bool:
    """Detecta peticiones de otras opciones o tours alternativos."""
    return bool(re.search(r'\b(?:otr[oa]s?\s+(?:opci[oó]n\w*|tour\w*|alternativ\w*|destino\w*)|outr[oa]s?\s+(?:opcoes|opcao|passeios?|alternativ\w*)|other\s+(?:option\w*|tour\w*|alternative\w*|destination\w*))\b', q_norm))


def duration_preference(value):
    """Read explicit supported-language days; unknown text does not imply a day."""
    text = str(value or '').lower()
    if re.search(r'\b(?:medio\s*d[ií]a|meio\s*dia|half\s*day|demi[-\s]journ[eé]e|mezza\s+giornata|pocas\s+horas|poco\s+tiempo)\b', text):
        return ('half', None)
    word_days = {
        'un': 1, 'uno': 1, 'una': 1, 'one': 1, 'dos': 2, 'two': 2,
        'tres': 3, 'three': 3, 'cuatro': 4, 'four': 4, 'cinco': 5, 'five': 5,
        'seis': 6, 'six': 6, 'siete': 7, 'seven': 7, 'ocho': 8, 'eight': 8,
        'nueve': 9, 'nine': 9, 'diez': 10, 'ten': 10,
        'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'três': 3,
        'quatro': 4, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10,
        'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5,
        'sei': 6, 'due': 2, 'tre': 3, 'quattro': 4, 'cinque': 5,
    }
    amounts = list(re.finditer(
        r'\b(\d+|' + '|'.join(word_days) + r')\s*(?:d[ií]as?|days?|jours?|giorni|giorno|d)\b', text))
    if amounts:
        amount = amounts[-1].group(1)
        days = int(amount) if amount.isdigit() else word_days[amount]
        return ('1day' if days == 1 else 'multi', days) if days > 0 else None
    if re.search(r'\b(?:un\s*d[ií]a|one\s*day|full\s*day|d[ií]a\s+completo|journ[eé]e\s+compl[eè]te|giornata\s+intera)\b', text):
        return ('1day', 1)
    return None


def hiking_preference(value):
    """An explicit newer walking preference replaces an older one."""
    text = str(value or '').lower()
    activity = r'(?:caminat\w*|caminar|caminando|caminh\w*|trilh\w*|andar|trek\w*|hik(?:e|es|ing)|senderis\w*|subid\w*|walk\w*|randonn\w*|escursion\w*(?:\s+a\s+piedi)?|cammin\w*)'
    if not re.search(r'\b' + activity + r'\b', text):
        return None
    desire = r'\b(?:quiero|deseo|quero|desejo|prefiro|gosto\s+de|prefier\w*|me\s+gust\w*|want|prefer|like|love|veux|souhaite|aime|voglio|vorrei|preferisco)\b'
    if re.match(r'\s*(?:hay|habra|ha|há|tienen|inclu\w*|does|do|is|are|how|what|que|como|cuanto|cuanta|quanto)\b', text) and not re.search(desire, text):
        return None
    negative = re.search(
        r"\b(?:no|nao|não|sem|sin|sans|senza|non|nada\s+de|without|do\s+not|don['’]?t)\s+"
        r'(?:(?:quiero|deseo|quero|desejo|prefiro|gosto\s+de|prefiero|me\s+gust[ae]n?|tengo\s+ganas\s+de|want|like|prefer)\s+)?'
        r'(?:(?:hacer|fazer|realizar|ir\s+a|to|do|go|have)\s+)*'
        r'(?:(?:las?|los?|una?s?|ningun[ao]?s?|any|a|the)\s+)?'
        + activity + r'\b', text,
    )
    if negative:
        return False
    if re.fullmatch(activity, text.strip(' ?¿!.')):
        return True
    if re.search(desire + r'[^.!?;\n]{0,80}\b' + activity + r'\b', text):
        return True
    return None


def _single_typo_cost(left, right):
    """One insertion/deletion/substitution/transposition; reject larger edits."""
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 1:
        return 2
    if len(left) == len(right):
        differences = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        if len(differences) == 1:
            return 1
        if len(differences) == 2:
            i, j = differences
            if j == i + 1 and left[i] == right[j] and left[j] == right[i]:
                return 1
        return 2
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    for i in range(len(longer)):
        if longer[:i] + longer[i + 1:] == shorter:
            return 1
    return 2


def _unique_typo_entity(query, entity_aliases):
    """Accept one minor typo in a multiword name only when the ID is unique.

    Single-word destinations and multiple near matches remain unassigned.
    This avoids treating every vaguely similar destination as a known product.
    """
    words = re.findall(r'\b\w+\b', query)
    matches = set()
    for entity_id, names in entity_aliases.items():
        for name in names:
            tokens = re.findall(r'\b\w+\b', name)
            if len(tokens) < 2 or sum(map(len, tokens)) < 8:
                continue
            for start in range(len(words) - len(tokens) + 1):
                window = words[start:start + len(tokens)]
                cost = sum(_single_typo_cost(a, b) for a, b in zip(window, tokens))
                if cost == 1:
                    matches.add(entity_id)
    return next(iter(matches)) if len(matches) == 1 else None


CAT_SPECS_DICT = {
    'treks': {
        'key': 'treks',
        'title_es': '🏔️ *Machu Picchu y Treks*',
        'title_en': '🏔️ *Machu Picchu & Treks*',
        'btn_id': 'btn_cat:treks',
        'btn_title_es': '🏔️ Machu Picchu',
        'btn_title_en': '🏔️ Machu Picchu',
        'tours': [
            ('machu-picchu-tren', 'Machu Picchu en Tren', '1 día'),
            ('camino-inka', 'Camino Inca Clásico', '4 días / 3 noches'),
            ('machu-picchu-car', 'Machu Picchu by Car', '2 días / 1 noche'),
            ('salkantay-trek', 'Salkantay Trek', '4 días'),
            ('inka-jungle', 'Inka Jungle to Machu Picchu', '4 días'),
            ('choquequirao', 'Choquequirao Trek', '4 días'),
        ]
    },
    'cusco': {
        'key': 'cusco',
        'title_es': '🌄 *Montañas y Clásicos (Cusco)*',
        'title_en': '🌄 *Mountains & Classics (Cusco)*',
        'btn_id': 'btn_cat:cusco',
        'btn_title_es': '🌄 Clásicos Cusco',
        'btn_title_en': '🌄 Cusco Classics',
        'tours': [
            ('montana-7-colores', 'Montaña de 7 Colores', 'Full Day'),
            ('laguna-humantay', 'Laguna Humantay', 'Full Day'),
            ('city-tour-cusco', 'City Tour Cusco', 'Medio día'),
            ('valle-sagrado', 'Valle Sagrado', 'Full Day'),
            ('maras-moray', 'Maras - Moray', 'Medio día'),
            ('waqra-pukara', 'Waqra Pukara', 'Full Day'),
            ('valle-sur', 'Valle Sur', 'Medio día'),
            ('maras-moray-cuatrimoto', 'Tour Cuatrimoto / Maras-Moray', 'Medio día'),
            ('puente-qeswachaca', "Puente de Q’eswachaca", 'Full Day'),
            ('tour-mistico', 'Tour Místico', 'Medio día'),
        ]
    },
    'reg': {
        'key': 'reg',
        'title_es': '🚌 *Rutas Regionales*',
        'title_en': '🚌 *Regional Routes*',
        'btn_id': 'btn_cat:reg',
        'btn_title_es': '🚌 Rutas Regionales',
        'btn_title_en': '🚌 Regional Routes',
        'tours': [
            ('ruta-del-sol', 'Ruta del Sol Cusco-Puno', 'Día completo'),
            ('islas-titicaca', 'Islas del Lago Titicaca', 'Full Day'),
            ('canon-colca', 'Cañón del Colca / Baños Termales de Chacapi', '2 días / 1 noche'),
        ]
    }
}
CAT_SPECS = list(CAT_SPECS_DICT.values())

TOUR_PROFILES = {
    'laguna-humantay': {
        'dur_type': '1day', 'is_hiking': True, 'is_nature': True, 'is_history': False,
        'desc_es': 'hermosa laguna turquesa al pie del nevado Salkantay',
        'desc_en': 'stunning turquoise lake at the foot of Mount Salkantay',
    },
    'montana-7-colores': {
        'dur_type': '1day', 'is_hiking': True, 'is_nature': True, 'is_history': False,
        'desc_es': 'impresionante paisaje cordillerano en Vinicunca',
        'desc_en': 'colorful Andean mountain landscape in Vinicunca',
    },
    'valle-sagrado': {
        'dur_type': '1day', 'is_hiking': False, 'is_nature': True, 'is_history': True,
        'desc_es': 'Pisac, Ollantaytambo y Chinchero en un hermoso valle andino',
        'desc_en': 'Pisac, Ollantaytambo, Chinchero',
    },
    'city-tour-cusco': {
        'dur_type': 'half', 'is_hiking': False, 'is_nature': False, 'is_history': True,
        'desc_es': 'templos y centros arqueológicos como Sacsayhuamán y Qorikancha',
        'desc_en': 'archaeological temples Sacsayhuamán & Qorikancha',
    },
    'maras-moray': {
        'dur_type': 'half', 'is_hiking': False, 'is_nature': True, 'is_history': True,
        'desc_es': 'salineras artesanales y terrazas agrícolas circulares',
        'desc_en': 'salt mines and circular agricultural terraces',
    },
    'maras-moray-cuatrimoto': {
        'dur_type': 'half', 'is_hiking': False, 'is_nature': True, 'is_history': False,
        'desc_es': 'aventura en cuatrimoto hacia las salineras de Maras y Moray',
        'desc_en': 'ATV adventure to Maras salt mines and Moray',
    },
    'valle-sur': {
        'dur_type': 'half', 'is_hiking': False, 'is_nature': True, 'is_history': True,
        'desc_es': 'sitios arqueológicos de Tipón y Pikillacta',
        'desc_en': 'archaeological sites of Tipon and Pikillacta',
    },
    'tour-mistico': {
        'dur_type': 'half', 'is_hiking': False, 'is_nature': False, 'is_history': True,
        'desc_es': 'ceremonia y cosmovisión andina tradicional',
        'desc_en': 'traditional Andean ceremony and worldview',
    },
    'machu-picchu-tren': {
        'dur_type': '1day', 'is_hiking': False, 'is_nature': True, 'is_history': True,
        'desc_es': 'maravilla mundial clásica en tren',
        'desc_en': 'classic world wonder by train',
    },
    'machu-picchu-car': {
        'dur_type': 'multi', 'is_hiking': False, 'is_nature': True, 'is_history': True,
        'desc_es': 'ruta panorámica alternativa hacia Machu Picchu',
        'desc_en': 'scenic alternative route to Machu Picchu',
    },
    'camino-inka': {
        'dur_type': 'multi', 'is_hiking': True, 'is_nature': True, 'is_history': True,
        'desc_es': 'la ruta senderista legendaria a Machu Picchu',
        'desc_en': 'legendary hiking trek to Machu Picchu',
    },
    'salkantay-trek': {
        'dur_type': 'multi', 'is_hiking': True, 'is_nature': True, 'is_history': False,
        'desc_es': 'aventura andina de alta montaña',
        'desc_en': 'Andean high-mountain adventure',
    },
    'inka-jungle': {
        'dur_type': 'multi', 'is_hiking': True, 'is_nature': True, 'is_history': False,
        'desc_es': 'aventura con bicicleta y senderismo hacia Machu Picchu',
        'desc_en': 'adventure with biking and trekking to Machu Picchu',
    },
    'choquequirao': {
        'dur_type': 'multi', 'is_hiking': True, 'is_nature': True, 'is_history': True,
        'desc_es': 'gran expedición arqueológica en la cordillera',
        'desc_en': 'great archaeological expedition in the mountains',
    },
    'waqra-pukara': {
        'dur_type': '1day', 'is_hiking': True, 'is_nature': True, 'is_history': True,
        'desc_es': 'imponente fortaleza y cañón andino',
        'desc_en': 'stunning fortress and Andean canyon',
    },
    'puente-qeswachaca': {
        'dur_type': '1day', 'is_hiking': False, 'is_nature': True, 'is_history': True,
        'desc_es': 'último puente colgante inca y paisajes altoandinos',
        'desc_en': 'last hanging Inca rope bridge and Andean landscapes',
    },
    'islas-titicaca': {
        'dur_type': '1day', 'is_hiking': False, 'is_nature': True, 'is_history': True,
        'desc_es': 'islas flotantes de los Uros y Taquile',
        'desc_en': 'floating islands of Uros and Taquile',
    },
    'canon-colca': {
        'dur_type': 'multi', 'is_hiking': False, 'is_nature': True, 'is_history': False,
        'desc_es': 'mirador del cóndor y cañones profundos',
        'desc_en': 'condor viewpoint and deep canyons',
    },
    'ruta-del-sol': {
        'dur_type': '1day', 'is_hiking': False, 'is_nature': True, 'is_history': True,
        'desc_es': 'recorrido paisajístico entre Cusco y Puno',
        'desc_en': 'scenic journey between Cusco and Puno',
    },
}

# --- Disponibilidad administrada desde /catalogo (available / limited / sold_out) ---
_AVAIL_BADGES = {
    'sold_out': {'es': ' [🔴 Agotado]', 'en': ' [🔴 Sold out]', 'pt': ' [🔴 Esgotado]',
                 'fr': ' [🔴 Complet]', 'it': ' [🔴 Esaurito]'},
    'limited': {'es': ' [🟡 Cupos limitados]', 'en': ' [🟡 Limited spots]', 'pt': ' [🟡 Vagas limitadas]',
                'fr': ' [🟡 Places limitées]', 'it': ' [🟡 Posti limitati]'},
}

_AVAIL_NOTICE = {
    'es': ('⚠️ *Disponibilidad actual:*', '🔴 agotado temporalmente', '🟡 cupos limitados',
           'Escribe 👉 *asesor* para revisar fechas o alternativas.'),
    'en': ('⚠️ *Current availability:*', '🔴 temporarily sold out', '🟡 limited spots',
           'Write 👉 *advisor* to check dates or alternatives.'),
    'pt': ('⚠️ *Disponibilidade atual:*', '🔴 temporariamente esgotado', '🟡 vagas limitadas',
           'Escreva 👉 *assessor* para verificar datas ou alternativas.'),
    'fr': ('⚠️ *Disponibilité actuelle :*', '🔴 temporairement complet', '🟡 places limitées',
           'Écrivez 👉 *conseiller* pour vérifier les dates ou alternatives.'),
    'it': ('⚠️ *Disponibilità attuale:*', '🔴 temporaneamente esaurito', '🟡 posti limitati',
           'Scrivi 👉 *consulente* per verificare date o alternative.'),
}

_SOLD_OUT_EXCLUDED = {
    'es': 'ℹ️ Agotado temporalmente (no incluido): {names}.',
    'en': 'ℹ️ Temporarily sold out (not included): {names}.',
    'pt': 'ℹ️ Temporariamente esgotado (não incluído): {names}.',
    'fr': 'ℹ️ Temporairement complet (non inclus) : {names}.',
    'it': 'ℹ️ Temporaneamente esaurito (non incluso): {names}.',
}

_ALL_MATCHES_SOLD_OUT = {
    'es': ('Los tours que coinciden con tus preferencias ({names}) están agotados temporalmente. '
           'Escribe 👉 *asesor* para revisar próximas fechas, o ajusta tus preferencias para ver otras opciones.'),
    'en': ('The tours matching your preferences ({names}) are temporarily sold out. '
           'Write 👉 *advisor* to check upcoming dates, or adjust your preferences to see other options.'),
    'pt': ('Os passeios que correspondem às suas preferências ({names}) estão temporariamente esgotados. '
           'Escreva 👉 *assessor* para verificar próximas datas ou ajuste suas preferências para ver outras opções.'),
    'fr': ('Les circuits correspondant à vos préférences ({names}) sont temporairement complets. '
           'Écrivez 👉 *conseiller* pour vérifier les prochaines dates, ou modifiez vos préférences.'),
    'it': ('I tour corrispondenti alle tue preferenze ({names}) sono temporaneamente esauriti. '
           'Scrivi 👉 *consulente* per verificare le prossime date, oppure modifica le tue preferenze.'),
}


def availability_badge(status, lang):
    """Etiqueta localizada para listados; cadena vacía si el tour está disponible."""
    by_lang = _AVAIL_BADGES.get(str(status or '').lower())
    if not by_lang:
        return ''
    return by_lang.get(lang, by_lang['es'])


def build_availability_notice(tour_ids, active_tours, lang, name_fn):
    """Aviso para respuestas curadas (más visitados, aclimatación).

    Retorna (texto_aviso, ids_agotados). El texto queda vacío si todos los
    tours referenciados están disponibles.
    """
    head, sold_lbl, lim_lbl, cta = _AVAIL_NOTICE.get(lang, _AVAIL_NOTICE['es'])
    lines, sold_ids = [], []
    for eid in tour_ids:
        t = active_tours.get(eid)
        if not t:
            continue
        status = str(t.get('availability', 'available')).lower()
        if status == 'sold_out':
            sold_ids.append(eid)
            lines.append(f"• *{name_fn(eid)}*: {sold_lbl}")
        elif status == 'limited':
            lines.append(f"• *{name_fn(eid)}*: {lim_lbl}")
    if not lines:
        return '', sold_ids
    return "\n\n" + head + "\n" + "\n".join(lines) + "\n" + cta, sold_ids


def classify_tour_category(entity_id: str, name: str = "") -> str:
    """Clasifica dinámicamente un tour en una de las 3 categorías oficiales:
    1. 'treks': Machu Picchu y Treks
    2. 'reg': Rutas Regionales (Puno, Titicaca, Colca, Arequipa, etc.)
    3. 'cusco': Montañas y Clásicos (Cusco)
    """
    eid = (entity_id or "").lower()
    nm = (name or "").lower()
    combined = f"{eid} {nm}"

    if any(k in combined for k in [
        'machu', 'picchu', 'trek', 'camino', 'inka', 'inca',
        'salkantay', 'jungle', 'choquequirao', 'caminata', 'hike'
    ]):
        return 'treks'

    if any(k in combined for k in [
        'titicaca', 'puno', 'colca', 'arequipa', 'ruta-del-sol',
        'ruta del sol', 'regional', 'chivay', 'chacapi'
    ]):
        return 'reg'

    return 'cusco'


def get_dynamic_cat_specs(active_tours_dict: dict) -> dict:
    """Construye las especificaciones de categorías a partir de todos los tours activos vigentes en el catálogo."""
    specs = {
        'treks': {
            'key': 'treks',
            'title_es': '🏔️ *Machu Picchu y Treks*',
            'title_en': '🏔️ *Machu Picchu & Treks*',
            'btn_id': 'btn_cat:treks',
            'btn_title_es': '🏔️ Machu Picchu',
            'btn_title_en': '🏔️ Machu Picchu',
            'tours': [],
        },
        'cusco': {
            'key': 'cusco',
            'title_es': '🌄 *Montañas y Clásicos (Cusco)*',
            'title_en': '🌄 *Mountains & Classics (Cusco)*',
            'btn_id': 'btn_cat:cusco',
            'btn_title_es': '🌄 Clásicos Cusco',
            'btn_title_en': '🌄 Cusco Classics',
            'tours': [],
        },
        'reg': {
            'key': 'reg',
            'title_es': '🚌 *Rutas Regionales*',
            'title_en': '🚌 *Regional Routes*',
            'btn_id': 'btn_cat:reg',
            'btn_title_es': '🚌 Rutas Regionales',
            'btn_title_en': '🚌 Regional Routes',
            'tours': [],
        }
    }

    # 1. Agregar primero los tours canónicos en su orden oficial si están activos
    seen = set()
    for cat_k, base_cat in CAT_SPECS_DICT.items():
        if cat_k in specs:
            for b_eid, b_name, b_dur in base_cat.get('tours', []):
                if b_eid in active_tours_dict:
                    t_data = active_tours_dict[b_eid]
                    name = t_data.get('name', b_name)
                    overrides_cat = t_data.get('overridden_fields') or []
                    raw_dur = t_data.get('duration', '')
                    # Respetar borrado administrativo de duración
                    if 'duration' in overrides_cat:
                        dur = raw_dur  # puede ser '' si fue borrado
                    else:
                        dur = raw_dur or b_dur
                    specs[cat_k]['tours'].append((b_eid, name, dur))
                    seen.add(b_eid)

    # 2. Agregar dinámicamente nuevos tours activos
    for eid, t_data in active_tours_dict.items():
        if eid not in seen:
            name = t_data.get('name', eid)
            dur = t_data.get('duration', '')
            cat_key = classify_tour_category(eid, name)
            if cat_key in specs:
                specs[cat_key]['tours'].append((eid, name, dur))
                seen.add(eid)

    return specs


def paginate_category_tours(tour_items: list) -> list:
    """
    Particiona la lista de tours de una categoría en páginas compatibles con WhatsApp (máx 3 botones por mensaje):
    - Si len(tour_items) <= 2: 1 página con todos los tours.
    - Si len(tour_items) > 2:
        Página 0: 2 tours (para botones: Tour 0, Tour 1, Más tours)
        Páginas intermedias: 1 tour por página (para botones: Tour N, Más tours, Categorías)
        Última página: hasta 2 tours (para botones: Tour final 1, Tour final 2 si hay, Categorías)
    """
    if not tour_items:
        return []
    if len(tour_items) <= 2:
        return [tour_items]
    pages = [tour_items[0:2]]
    idx = 2
    while idx < len(tour_items):
        remaining = len(tour_items) - idx
        if remaining <= 2:
            pages.append(tour_items[idx:idx + remaining])
            break
        else:
            pages.append(tour_items[idx:idx + 1])
            idx += 1
    return pages


def install(ns, support, original):
    catalog = support.CATALOG
    from catalog_service import is_deactivated_tour

    def get_current_tours_status():
        try:
            from catalog_service import get_all_tours
            dynamic_all = get_all_tours(active_only=False, strict=True)
            if dynamic_all is None:
                return {}, True, False
            dynamic_active = [t for t in dynamic_all if t.get('is_active')]
            res = {}
            for dt in dynamic_active:
                eid_cur = dt['entity_id']
                overrides_cur = dt.get('overridden_fields') or []
                sched_cur = str(dt.get('schedule') or '').strip()
                dur_cur = str(dt.get('duration') or '').strip()
                if not sched_cur and 'schedule' not in overrides_cur:
                    for f in get_facts(eid_cur, include_dynamic=False):
                        if f.field == 'schedule' and f.value and f.value is not False and getattr(f, 'evidence_status', '') == 'confirmed':
                            sched_cur = str(f.value).strip()
                            break
                if not dur_cur and 'duration' not in overrides_cur:
                    for f in get_facts(eid_cur, include_dynamic=False):
                        if f.field == 'duration' and f.value and f.value is not False and getattr(f, 'evidence_status', '') == 'confirmed':
                            dur_cur = str(f.value).strip()
                            break
                res[eid_cur] = {
                    'entity_id': eid_cur,
                    'name': dt['name'],
                    'confirmed_product': True,
                    'official_price': dt.get('official_price', ''),
                    'currency': dt.get('currency', 'USD'),
                    'schedule': sched_cur,
                    'duration': dur_cur,
                    'includes': dt.get('includes', ''),
                    'excludes': dt.get('excludes', ''),
                    'photo_filename': dt.get('photo_filename', ''),
                    'brochure_filename': dt.get('brochure_filename', ''),
                    'availability': dt.get('availability', 'available'),
                    'overridden_fields': dt.get('overridden_fields', []),
                    'aliases': dt.get('aliases', []),
                }
            return res, False, len(res) == 0
        except Exception:
            return {}, True, False

    def get_current_tours():
        res, _, _ = get_current_tours_status()
        return res

    tours = get_current_tours()
    aliases = {eid: [support.normalize(t['name'])] for eid, t in tours.items()}
    for eid, t in tours.items():
        for a in t.get('aliases', []):
            a_norm = support.normalize(a)
            if a_norm and a_norm not in aliases[eid]:
                aliases[eid].append(a_norm)
    aliases.update({
        'machu-picchu-car':['machu picchu by car','machu picchu en auto','machu picchu en carro'],
        'machu-picchu-tren':['machu picchu en tren','machu picchu by train','machu picchu','machupicchu'],
        'maras-moray-cuatrimoto':['cuatrimoto','cuatrimotos','atv','quad bike'],
        'maras-moray':['maras-moray','maras moray','maras - moray','moray'],
        'montana-7-colores':['7 colores','rainbow mountain','vinicunca'],
        'laguna-humantay':['humantay'], 'salkantay-trek':['salkantay'],
        'city-tour-cusco':['city tour','citytour'], 'valle-sagrado':['valle sagrado','sacred valley'],
        'valle-sur':['valle sur','south valley'], 'camino-inka':['camino inka','camino inca','inca trail'],
        'waqra-pukara':['waqra pukara','waqrapukara'], 'puente-qeswachaca':['qeswachaca','q\'eswachaca',"q'eswachaca",'qeswachaka'],
        'inka-jungle':['inka jungle','inca jungle']})
    def entity(q):
        q = support.normalize_entity_query(q)
        typo_aliases = {eid: list(names) for eid, names in aliases.items()}
        if re.search(r'cuatrimotos?|\batv\b|quad bike',q) and re.search(r'maras|moray|tour cuatrimoto',q):
            return 'maras-moray-cuatrimoto'
        try:
            from catalog_service import get_active_entity_keywords
            active_kw = get_active_entity_keywords()
            hits = []
            for eid, kws in active_kw.items():
                typo_aliases.setdefault(eid, []).extend(support.normalize(k) for k in kws if k)
                for k in kws:
                    k_norm = support.normalize(k)
                    if k_norm and k_norm in q:
                        hits.append((len(k_norm), eid))
            if hits:
                return max(hits)[1]
        except Exception:
            pass
        hits = []
        for eid, aa in aliases.items():
            for a in aa:
                a_norm = support.normalize(a)
                if a_norm and a_norm in q:
                    hits.append((len(a_norm), eid))
        if hits:
            return max(hits)[1]

        # Si no coincidió con tours activos ni canónicos, identificar si la consulta es sobre un tour desactivado del catálogo
        try:
            from catalog_service import get_all_tours
            all_t = get_all_tours(active_only=False)
            deact_hits = []
            for t in all_t:
                typo_aliases.setdefault(t['entity_id'], []).extend(
                    support.normalize(k) for k in [t.get('name', ''), *t.get('aliases', [])] if k)
                if not t.get('is_active', 1):
                    deact_eid = t.get('entity_id')
                    kws = list(t.get('aliases', []))
                    if t.get('name'):
                        kws.append(t['name'])
                    for k in kws:
                        k_norm = support.normalize(k)
                        if k_norm and k_norm in q:
                            deact_hits.append((len(k_norm), deact_eid))
            if deact_hits:
                return max(deact_hits)[1]
        except Exception:
            pass

        return _unique_typo_entity(q, typo_aliases)
    def field(q):
        for key,pattern in [
            ('excludes',r'no incluye|no esta incluido|exclu|not include'),
            ('includes',r'inclu|include'),
            ('price',r'precio|cuesta|cuanto cuesta|cuanto (?:sale|vale)|costo|costos|tarifa|tarifas|rate|rates|soles|\bpen\b|price|prices|cost|costs|how much'),
            ('schedule',r'horario|hora|schedule|timetable|what time|departure'),
            ('duration',r'dura|how long'),
            ('stops',r'lugares|recorrido|\bruta\b|paradas|itinerary|\broute\b|places'),
            ('product',r'tienen|ofrecen|documentado|oferta|do you have|do you offer')
        ]:
            if re.search(pattern,q): return key
        return None
    support.detect_entity_from_question=lambda q:entity(support.normalize(q))
    support.detect_field_from_question=lambda q:field(support.normalize(q))
    ns['_evaluate_evidence_layer']=lambda *args:None
    ns['check_tour_intent']=lambda *args,**kwargs:None
    def record(user_id, question, response, metadata=None):
        if 'add_history_turn' in ns:
            if metadata:
                ns['add_history_turn'](user_id, question, response, metadata=metadata)
            else:
                ns['add_history_turn'](user_id, question, response)
        else:
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', response)

    def chain(question,user_id='default'):
        q=support.normalize(question); lang=ns['detect_language'](question)
        prior=list(ns['get_history'](user_id))
        # Numeric day replies have identical spelling in ES/PT. Retain an
        # explicitly Portuguese conversation rather than guessing from "4 dias".
        shared_reply = r'(?:(?:\d+|tres|cinco|seis)\s+dias?|cultura|aventura)'
        if re.fullmatch(shared_reply, q.strip(' ?¿!.')):
            for h in reversed(prior):
                if h.get('role') != 'human':
                    continue
                previous_q = support.normalize(h.get('content', ''))
                if re.fullmatch(shared_reply, previous_q.strip(' ?¿!.')):
                    continue
                if ns['detect_language'](h.get('content', '')) == 'pt':
                    lang = 'pt'
                break
        en=lang=='en'; pt=lang=='pt'; fr=lang=='fr'; it=lang=='it'
        phone=' / '.join(catalog['agency']['phones'])
        active_tours, is_read_error, is_empty = get_current_tours_status()
        lang_key = lang if lang in ('en', 'pt', 'fr', 'it') else 'es'

        def _avail_name(eid_n):
            name_n = active_tours.get(eid_n, {}).get('name', eid_n)
            if en:
                try:
                    from app import _get_tour_display_name
                    name_n = _get_tour_display_name(eid_n, is_en=True) or name_n
                except Exception:
                    pass
            return name_n

        # --- SOCIAL / CONVERSACIONAL: respuesta corta, sin NOTICES, sin LLM ---
        social_key = _SOCIAL_INTENTS.get(q.strip(' ?¿!.'))
        if social_key:
            text = _SOCIAL_RESPONSES[social_key]
            record(user_id, question, text)
            return dict(response=text,context_used=False,is_predefined=True,is_fallback=False,
                resolved_autonomously=True,is_escalation=False,needs_agency_confirmation=False,
                needs_confirmation=False,conflict_detected=False,evidence_status='social',
                sources_used=[],route='social',response_route='social')

        # --- AYUDA: respuesta corta, sin NOTICES, sin LLM ---
        if re.search(r'\b(ayuda|ayudame|me ayudas|puedes ayudarme|que puedes hacer|que haces|en que me puedes ayudar|en que puedes ayudar|para que sirves|como me puedes ayudar)\b', q) or q.strip(' ?¿!.') in {'ayuda','help'}:
            text = 'I can help with tours, itineraries, schedules and documented services. What would you like to know?' if en or q.strip(' ?¿!.') == 'help' else _HELP_RESPONSE
            record(user_id, question, text)
            return dict(response=text,context_used=False,is_predefined=True,is_fallback=False,
                resolved_autonomously=True,is_escalation=False,needs_agency_confirmation=False,
                needs_confirmation=False,conflict_detected=False,evidence_status='social',
                sources_used=[],route='help',response_route='help')

        def finish(text, route, pending=False, sources=(), conflict=False, predefined=True, entity_id=None, needs_agency=None, recommendation_state=None):
            needs_agency_val = pending if needs_agency is None else needs_agency
            metadata = {'recommendation_state': recommendation_state} if recommendation_state is not None else None
            record(user_id, question, text, metadata=metadata)
            result = dict(
                response=text,
                context_used=bool(sources),
                is_predefined=predefined,
                is_fallback=False,
                resolved_autonomously=not pending,
                is_escalation=False,
                needs_agency_confirmation=needs_agency_val,
                needs_confirmation=pending,
                conflict_detected=conflict,
                evidence_status='clarification' if (pending and not needs_agency_val) else ('conflict' if conflict else ('unknown' if pending else 'documented')),
                sources_used=sorted(set(sources)),
                route=route,
                response_route=route,
                entity_id=entity_id,
                language=lang,
            )
            if recommendation_state is not None:
                result['recommended_tour_ids'] = recommendation_state['offered_ids']
            return result
        def unknown(subject, entity_id=None):
            t_name = ""
            if entity_id and entity_id in active_tours:
                t_name = active_tours[entity_id].get('name', entity_id)
            elif entity_id and entity_id in catalog.get('tours', {}):
                t_name = catalog['tours'][entity_id].get('name', entity_id)

            if t_name:
                if en:
                    msg = f"💬 That detail for *{t_name}* is confirmed directly with our team.\n\nWrite 👉 *advisor* and we'll help you 😊"
                else:
                    msg = f"💬 Ese detalle de *{t_name}* lo confirmamos contigo directamente.\n\nEscribe 👉 *asesor* y te ayudamos 😊"
            else:
                if en:
                    msg = f"That information is confirmed directly at the agency.\n\nWrite 👉 *advisor* and we'll help you right away 😊"
                else:
                    msg = f"Ese dato lo confirmamos directamente en la agencia. 💬\n\nEscribe 👉 *asesor* y te ayudamos ahora mismo 😊"
            return finish(msg,'evidence_unknown',True,entity_id=entity_id)

        # 1. Fallo técnico al consultar la base de datos: no afirmar que tours fueron desactivados
        if is_read_error:
            msg = (
                "Tuvimos un inconveniente técnico temporal al consultar el catálogo. Puedes comunicarte directamente con un asesor o intentar nuevamente en unos instantes."
                if not en else
                "We encountered a temporary technical issue accessing the catalog. You can contact an advisor directly or try again in a moment."
            )
            if pt:
                msg = "Ocorreu um problema técnico temporário ao consultar o catálogo. Você pode consultar um assessor ou tentar novamente em alguns instantes."
            return finish(msg, 'evidence_catalog_error', pending=True)

        # 2. Catálogo vacío confirmado (lectura exitosa pero 0 tours activos)
        if is_empty:
            msg = (
                "Actualmente no disponemos de tours activos en nuestro catálogo. Puedes consultar opciones personalizadas con un asesor."
                if not en else
                "Currently there are no active tours available in our catalog. You can check custom options with an advisor."
            )
            if pt:
                msg = "No momento não há passeios ativos no nosso catálogo. Você pode consultar outras opções com um assessor."
            return finish(msg, 'evidence_catalog_empty', pending=True)

        # 3. Detección de referencias ambiguas ("el otro", "del otro", "the other", etc.)
        entity_in_q = support.detect_entity_from_question(q)
        is_advice_on_tour = bool(entity_in_q and (is_open_tour_advice(q) or is_tour_comparison(q)))

        # Peticiones de recomendación, rechazo ("ninguno") u otras opciones NUNCA son ambigüedad de tour
        is_rec_or_reject = (is_recommendation_query(q) and not is_advice_on_tour) or is_rejection_query(q) or is_other_options_query(q)
        is_ambiguous_ref = (not is_rec_or_reject) and bool(re.search(
            r'\b((?:d?el|de la)\s+otr[oa]s?|el demas|los demas|the other( one)?|the second( one)?)\b',
            q
        ))
        if is_ambiguous_ref and not entity_in_q:
            recent_eids = []
            for h in reversed(prior):
                if h.get('role') == 'human':
                    norm_h = support.normalize(h.get('content', ''))
                    for aeid, aa in aliases.items():
                        if any(support.normalize(a) in norm_h for a in aa if a):
                            if aeid in active_tours and aeid not in recent_eids:
                                recent_eids.append(aeid)
                                if len(recent_eids) >= 2:
                                    break
                if len(recent_eids) >= 2:
                    break
            if len(recent_eids) >= 2:
                t1_name = active_tours.get(recent_eids[0], {}).get('name', recent_eids[0])
                t2_name = active_tours.get(recent_eids[1], {}).get('name', recent_eids[1])
                msg = (
                    f"¿A cuál de los tours te refieres? Conversamos sobre *{t1_name}* y *{t2_name}*. Por favor indícame cuál deseas consultar o escribe su nombre 😊"
                    if not en else
                    f"Which tour are you referring to? We discussed *{t1_name}* and *{t2_name}*. Please let me know which one you'd like to check or type its name 😊"
                )
                if pt:
                    msg = f"A qual passeio você se refere? Conversamos sobre *{t1_name}* e *{t2_name}*. Diga qual deseja consultar ou escreva o nome 😊"
                return finish(msg, 'evidence_ambiguous', pending=True, sources=[], entity_id=f"{recent_eids[0]},{recent_eids[1]}", needs_agency=False)

        # 3.5 Peticiones de recomendación, rechazo u orientación de preferencias
        is_pref_reply = bool(re.search(
            r'\b(?:paisajes?|paisagens?|natureza|sitios?\s+hist[oó]ricos?|caminatas?|caminh\w*|trilh\w*|senderismo|aventura|cultura|landscapes?|hiking|historical\s+sites?|medio\s*d[ií]a|meio\s*dia|half\s*day|1\s*d[ií]a|un\s*d[ií]a|full\s*day|[2345]\s*d[ií]as?)\b',
            q
        ) or duration_preference(q) is not None or hiking_preference(q) is not None) and not entity_in_q and field(q) != 'product'

        is_rec = is_recommendation_query(q) and not is_advice_on_tour
        is_rej = is_rejection_query(q) and not is_ambiguous_ref

        if is_rec or is_rej or is_pref_reply or is_other_options_query(q):
            _NO_HIKING_PAT = re.compile(
                r'\b(?:no|sin|nada\s+de)\s+(?:quiero\s+|deseo\s+|me\s+gusta\s+|tengo\s+ganas\s+de\s+)?'
                r'(?:caminat\w*|trek\w*|hiking|senderis\w*|subid\w*)\b'
            )
            _PREF_PAT = re.compile(
                r'\b(?:paisaje\w*|paisage\w*|natureza|histori\w*|caminat\w*|caminh\w*|trilh\w*|d[ií]as?|day|days|medio|meio|half|tiempo|tempo|prefer\w*|aventur\w*|cultur\w*)\b'
            )
            q_norm = support.normalize(q)
            time_pref = duration_preference(q_norm)
            if time_pref is None:
                for h in reversed(prior):
                    if h.get('role') != 'human':
                        continue
                    h_text = support.normalize(h.get('content', ''))
                    if field(h_text) == 'product' and not is_recommendation_query(h_text):
                        continue
                    time_pref = duration_preference(h_text)
                    if time_pref is not None:
                        break
            has_time_short = time_pref is not None and time_pref[0] == 'half'
            has_time_1day = time_pref is not None and time_pref[0] == '1day'
            has_time_multi = time_pref is not None and time_pref[0] == 'multi'

            # The latest explicit walking preference wins; time-only replies keep it.
            walking_pref = hiking_preference(q_norm)
            if walking_pref is None:
                for h in reversed(prior):
                    if h.get('role') == 'human':
                        walking_pref = hiking_preference(support.normalize(h.get('content', '')))
                        if walking_pref is not None:
                            break
            pref_texts = [q_norm]
            for h in reversed(prior):
                if h.get('role') != 'human':
                    continue
                h_text = support.normalize(h.get('content', ''))
                if is_recommendation_query(h_text) or _PREF_PAT.search(h_text) or _NO_HIKING_PAT.search(h_text):
                    pref_texts.append(h_text)
            pref_text = ' '.join(reversed(pref_texts))

            no_hiking = walking_pref is False
            has_hiking = walking_pref is True or ((not no_hiking) and bool(re.search(r'\b(caminat\w*|caminh\w*|trilh\w*|senderis\w*|aventur\w*|trek\w*|hike\w*|hiking|adventure)\b', pref_text)))
            has_nature = bool(re.search(r'\b(paisaje\w*|paisage\w*|naturalez\w*|natureza|laguna\w*|monta[nñ]a\w*|scener\w*|landscape\w*|nature|lake\w*)\b', pref_text))
            has_history= bool(re.search(r'\b(hist[oó]ri\w*|arqueolog\w*|cultur\w*|ruina\w*|templo\w*|history|historical|archeolog\w*|ruins|culture)\b', pref_text))

            # Recomendación especializada de tours más visitados / populares / imperdibles
            is_most_visited = is_most_visited_query(pref_text) or is_most_visited_query(q_norm) or is_most_visited_query(q)
            if is_most_visited:
                if en:
                    msg = (
                        "🏆 *Most Visited & Must-See Tours — Texeira Travel*\n\n"
                        "The top-rated and most chosen experiences by travelers in Cusco are:\n\n"
                        "1️⃣ 🏔️ *Machu Picchu (by Train or Classic Inca Trail 4D/3N):*\n"
                        "Wonder of the World. The ultimate highlight of any trip to Peru.\n\n"
                        "2️⃣ 🎨 *Rainbow Mountain (Vinicunca):*\n"
                        "The most famous and photographed Andean landscape (5,036 m / 16,520 ft).\n\n"
                        "3️⃣ 💧 *Humantay Lake:*\n"
                        "Stunning turquoise glacier lake at the base of Mount Salkantay (4,200 m / 13,780 ft).\n\n"
                        "4️⃣ 🏛️ *Cusco City Tour / Sacred Valley:*\n"
                        "Essential Inca archaeological centers (perfect for your first days and acclimatization).\n\n"
                        "💡 *Travel tip:* We recommend starting with the City Tour or Sacred Valley to acclimatize to the altitude, then hiking Humantay or Rainbow Mountain, and finishing with Machu Picchu.\n\n"
                        "_Type any tour name for official details or type 👉 *advisor* to plan your trip with our team._"
                    )
                elif pt:
                    msg = (
                        "🏆 *Passeios Mais Visitados e Imperdíveis — Texeira Travel*\n\n"
                        "Os destinos favoritos e mais escolhidos pelos viajantes em Cusco são:\n\n"
                        "1️⃣ 🏔️ *Machu Picchu (de Trem ou Trilha Inca Clássica 4D/3N):*\n"
                        "Maravilha do Mundo. O ápice e imperdível de qualquer viagem ao Peru.\n\n"
                        "2️⃣ 🎨 *Montanha de 7 Cores (Vinicunca):*\n"
                        "A paisagem andina mais famosa e fotografada (5.036 m).\n\n"
                        "3️⃣ 💧 *Lagoa Humantay:*\n"
                        "Linda lagoa turquesa aos pés do imponente nevado Salkantay (4.200 m).\n\n"
                        "4️⃣ 🏛️ *City Tour Cusco / Vale Sagrado:*\n"
                        "Os sítios arqueológicos incas essenciais (ideal para seus primeiros dias e aclimatação).\n\n"
                        "💡 *Dica de viagem:* Recomendamos iniciar pelo City Tour ou Vale Sagrado para se aclimatar à altitude, depois Humantay ou Vinicunca, e fechar com chave de ouro em Machu Picchu.\n\n"
                        "_Digite o nome de um passeio para ver os detalhes oficiais ou digite 👉 *assessor* para falar com nossa equipe._"
                    )
                elif fr:
                    msg = (
                        "🏆 *Circuits les Plus Visités et Incontournables — Texeira Travel*\n\n"
                        "Les expériences incontournables et les plus choisies par les voyageurs à Cusco sont :\n\n"
                        "1️⃣ 🏔️ *Machu Picchu (en Train ou Chemin Inca Classique 4D/3N) :*\n"
                        "Merveille du Monde. Le point culminant incontournable de tout voyage au Pérou.\n\n"
                        "2️⃣ 🎨 *Montagne aux 7 Couleurs (Vinicunca) :*\n"
                        "Le paysage andin le plus célèbre et photographié (5 036 m).\n\n"
                        "3️⃣ 💧 *Lagune Humantay :*\n"
                        "Superbe lagune turquoise au pied du glacier Salkantay (4 200 m).\n\n"
                        "4️⃣ 🏛️ *City Tour Cusco / Vallée Sacrée :*\n"
                        "Les sites archéologiques incas majeurs (idéal pour vos premiers jours et l'acclimatation).\n\n"
                        "💡 *Conseil voyageur :* Nous recommandons de commencer par le City Tour ou la Vallée Sacrée pour vous acclimater à l'altitude, puis Humantay ou Vinicunca, et enfin Machu Picchu.\n\n"
                        "_Écrivez le nom d'un circuit pour les détails ou écrivez 👉 *conseiller*._"
                    )
                elif it:
                    msg = (
                        "🏆 *Tour Più Visitati e Imperdibili — Texeira Travel*\n\n"
                        "Le esperienze più richieste e scelte dai viaggiatori a Cusco sono:\n\n"
                        "1️⃣ 🏔️ *Machu Picchu (in Treno o Cammino Inca Classico 4D/3N):*\n"
                        "Meraviglia del Mondo. L'esperienza clou e immancabile di ogni viaggio in Perù.\n\n"
                        "2️⃣ 🎨 *Montagna dei 7 Colori (Vinicunca):*\n"
                        "Il paesaggio andino più famoso e fotografato (5.036 m).\n\n"
                        "3️⃣ 💧 *Laguna Humantay:*\n"
                        "Splendida laguna turchese ai piedi del ghiacciaio Salkantay (4.200 m).\n\n"
                        "4️⃣ 🏛️ *City Tour Cusco / Valle Sacra:*\n"
                        "I siti archeologici inca essenziali (ideale per i primi giorni e l'acclimatamento).\n\n"
                        "💡 *Consiglio di viaggio:* Consigliamo di iniziare con il City Tour o la Valle Sacra per acclimatarsi all'altitudine, proseguire con Humantay o Vinicunca e concludere con Machu Picchu.\n\n"
                        "_Scrivi il nome di un tour per i dettagli o scrivi 👉 *consulente*._"
                    )
                else:
                    msg = (
                        "🏆 *Tours Más Visitados e Imperdibles — Texeira Travel*\n\n"
                        "Los destinos preferidos y más elegidos por los viajeros en Cusco son:\n\n"
                        "1️⃣ 🏔️ *Machu Picchu (en Tren o Camino Inca 4D/3N):*\n"
                        "La Maravilla del Mundo Moderno. La experiencia cumbre e imprescindible de todo viaje al Perú.\n\n"
                        "2️⃣ 🎨 *Montaña de 7 Colores (Vinicunca):*\n"
                        "El paisaje andino más famoso y fotografiado (5,036 msnm).\n\n"
                        "3️⃣ 💧 *Laguna Humantay:*\n\n"
                        "Hermosa laguna turquesa a los pies del imponente nevado Salkantay (4,200 msnm).\n\n"
                        "4️⃣ 🏛️ *City Tour Cusco / Valle Sagrado:*\n"
                        "Los centros arqueológicos incas fundamentales (ideal para tu aclimatación y primeros días).\n\n"
                        "💡 *Tip viajero Texeira:* Te sugerimos iniciar con City Tour o Valle Sagrado para aclimatarte a la altura, seguir con Humantay o Vinicunca, y culminar con broche de oro en Machu Picchu.\n\n"
                        "_Escribe el nombre de un tour para ver su ficha técnica oficial o escribe 👉 *asesor* para coordinar tu viaje._"
                    )
                mv_ids = ['machu-picchu-tren', 'camino-inka', 'montana-7-colores', 'laguna-humantay', 'city-tour-cusco', 'valle-sagrado']
                notice, sold_mv = build_availability_notice(mv_ids, active_tours, lang_key, _avail_name)
                msg += notice
                rec_state = dict(criteria=dict(time=['any'], hiking=None, nature=True, history=True),
                                 offered_ids=[e for e in mv_ids[:5] if e not in sold_mv], rejected_ids=[])
                return finish(msg, 'evidence_recommendation', pending=False, needs_agency=False,
                              sources=['CATALOGO_OFICIAL'], recommendation_state=rec_state)

            # Recomendación especializada de aclimatación / primer día en Cusco
            is_altitude_advice = bool(re.search(
                r'\b(?:primer\s*d[ií]a|first\s*day|primeiro\s*dia|aclimat\w*|soroche|mal\s*de\s*altura|altitude\s*sickness)\b',
                pref_text
            ))
            if is_altitude_advice:
                if en:
                    msg = (
                        "🏔️ *Recommendation for your First Day & Acclimatization in Cusco (3,400 m):*\n\n"
                        "To adapt to the altitude and prevent soroche (altitude sickness), we recommend resting and taking easy half-day activities:\n\n"
                        "• 🏛️ *City Tour Cusco* (Half day, 13:30 to 18:30) — Inca temples and historic center at a gentle pace.\n"
                        "• 🏺 *Maras & Moray* (Half day, 08:40 to 14:00) — Salt mines and agricultural terraces with light walking.\n\n"
                        "⚠️ *Important:* We advise against high-altitude hikes on your arrival day (such as *Humantay Lake* or *Rainbow Mountain*). It is best to schedule them from Day 2 or 3 onwards.\n\n"
                        "_💡 Tip: Drink coca tea, stay hydrated, and walk at a calm pace. To coordinate, write 👉 advisor._"
                    )
                elif pt:
                    msg = (
                        "🏔️ *Recomendação para seu Primeiro Dia e Aclimatação em Cusco (3.400 m):*\n\n"
                        "Para se adaptar à altitude e evitar o soroche (mal da altitude), recomendamos descanso e passeios suaves de meio dia:\n\n"
                        "• 🏛️ *City Tour Cusco* (Meio dia, 13:30 às 18:30) — Templos incas e centro histórico em ritmo tranquilo.\n"
                        "• 🏺 *Maras e Moray* (Meio dia, 08:40 às 14:00) — Salineras e terraços agrícolas sem esforço físico pesado.\n\n"
                        "⚠️ *Importante:* Não recomendamos trilhas de alta montanha no primeiro dia (como *Laguna Humantay* ou *Montanha 7 Cores*). É melhor realizá-las a partir do 2º ou 3º dia.\n\n"
                        "_💡 Dica: Tome chá de coca, mantenha-se hidratado e caminhe com calma. Para agendar, escreva 👉 assessor._"
                    )
                else:
                    msg = (
                        "🏔️ *Recomendación para tu Primer Día y Aclimatación en Cusco (3,400 msnm):*\n\n"
                        "Para adaptarte a la altura y prevenir el soroche (mal de altura), recomendamos descanso y actividades suaves de medio día:\n\n"
                        "• 🏛️ *City Tour Cusco* (Medio día, 13:30 a 18:30) — Templos incas y centro histórico a ritmo tranquilo.\n"
                        "• 🏺 *Maras y Moray* (Medio día, 08:40 a 14:00) — Salineras y terrazas agrícolas sin caminatas pesadas.\n\n"
                        "⚠️ *Importante:* No recomendamos excursiones de gran altitud o caminatas exigentes el día de llegada (como *Laguna Humantay* o *Montaña de 7 Colores*). Es ideal dejarlas para el 2do o 3er día.\n\n"
                        "_💡 Consejo: Toma mate de coca, mantente hidratado y camina con calma. Para coordinar fechas, escribe 👉 *asesor*._"
                    )
                alt_ids = ['city-tour-cusco', 'maras-moray']
                notice, sold_alt = build_availability_notice(alt_ids, active_tours, lang_key, _avail_name)
                msg += notice
                rec_state = dict(criteria=dict(time=['half'], hiking=False, nature=True, history=True),
                                 offered_ids=[e for e in alt_ids if e not in sold_alt], rejected_ids=[])
                return finish(msg, 'evidence_recommendation', pending=False, needs_agency=False,
                              sources=['CATALOGO_OFICIAL'], recommendation_state=rec_state)

            # Sin preferencias: preguntar brevemente por intereses y tiempo disponible
            if not (has_nature or has_history or has_hiking or has_time_short or has_time_1day or has_time_multi or no_hiking):
                if en:
                    msg = (
                        "Sure! 😊 What interests you most: *landscapes, historical sites, or hiking*? "
                        "How much time do you have to visit?\n\n"
                        "_Tell me your preferences, explore our options with 🗺️ View Tours, or write 👉 advisor to coordinate directly._"
                    )
                elif pt:
                    msg = (
                        "Claro! 😊 O que interessa mais: *paisagens, locais históricos ou caminhadas*? "
                        "Quanto tempo você tem para visitar?\n\n"
                        "_Conte suas preferências, explore as opções em 🗺️ Ver passeios ou escreva 👉 assessor para falar com nossa equipe._"
                    )
                elif fr:
                    msg = ("Bien sûr ! 😊 Qu'est-ce qui vous intéresse : *paysages, sites historiques ou randonnée* ? "
                           "Combien de temps avez-vous ?\n\n"
                           "_Indiquez vos préférences, explorez les circuits ou contactez un conseiller._")
                elif it:
                    msg = ("Certo! 😊 Cosa ti interessa: *paesaggi, siti storici o camminate*? "
                           "Quanto tempo hai?\n\n"
                           "_Indica le tue preferenze, esplora i tour o contatta un consulente._")
                else:
                    msg = (
                        "¡Claro! 😊 ¿Qué te interesa más: *paisajes, sitios históricos o caminatas*? "
                        "¿Cuánto tiempo tienes para visitar?\n\n"
                        "_Cuéntame tus preferencias, explora las opciones con 🗺️ Ver Tours o escribe 👉 asesor para coordinar directamente._"
                    )
                return finish(msg, 'evidence_recommendation', pending=True, needs_agency=False, sources=['CATALOGO_OFICIAL'])

            criteria = dict(time=list(time_pref) if time_pref else None,
                            hiking=walking_pref, nature=has_nature, history=has_history)
            previous_rec = None
            legacy_unidentified = False
            for h in reversed(prior):
                if h.get('role') == 'ai':
                    previous_rec = (h.get('metadata') or {}).get('recommendation_state')
                    if previous_rec is not None:
                        break
                    # Older histories lack IDs. Recognize only our own recommendation
                    # format; category lists and general assistant messages are unrelated.
                    content = h.get('content', '')
                    if re.search(r'recomendaciones verificadas|top verified recommendations|recomendações verificadas', content):
                        title_ids = {}
                        for t in catalog.get('tours', []):
                            for name in [t.get('name', ''), *t.get('aliases', [])]:
                                title_ids[support.normalize(name)] = t['entity_id']
                        for eid, t in active_tours.items():
                            from app import _get_tour_display_name
                            for name in [t['name'], _get_tour_display_name(eid, is_en=True)]:
                                title_ids[support.normalize(name)] = eid
                        offered_names = re.findall(r'^\s*• \*([^*\n]+)\*', content, re.MULTILINE)
                        legacy_unidentified = not offered_names or any(support.normalize(name) not in title_ids for name in offered_names)
                        if not legacy_unidentified:
                            previous_rec = dict(criteria=criteria, rejected_ids=[],
                                                offered_ids=[title_ids[support.normalize(name)] for name in offered_names])
                        break
            if legacy_unidentified and (is_rej or is_other_options_query(q)):
                msg = (
                    "Which tours would you like to rule out so I can suggest different options?"
                    if en else
                    "¿Qué tours quieres descartar para que pueda proponerte otras opciones?"
                )
                if pt:
                    msg = "Quais passeios você quer descartar para que eu possa sugerir outras opções?"
                return finish(msg, 'evidence_recommendation', pending=True, needs_agency=False,
                              sources=['CATALOGO_OFICIAL'])
            rejected_ids = set()
            if previous_rec and previous_rec.get('criteria') == criteria:
                rejected_ids.update(previous_rec.get('rejected_ids', []))
                if is_rej or is_other_options_query(q):
                    rejected_ids.update(previous_rec.get('offered_ids', []))
            recommendation_state = dict(criteria=criteria, offered_ids=[],
                                        rejected_ids=sorted(rejected_ids))

            # Con preferencias: filtrar dinámicamente sobre active_tours vigentes
            candidates = []
            sold_out_matches = []  # tours que cumplen el perfil pero están agotados
            for eid, t_data in active_tours.items():
                if not t_data.get('is_active', True) or is_deactivated_tour(eid):
                    continue
                if eid in rejected_ids:
                    continue
                prof = dict(TOUR_PROFILES.get(eid, {
                    'dur_type': '1day',
                    'is_hiking': any(k in eid for k in ['trek', 'caminata', 'hike', 'inka', 'salkantay', 'jungle', 'choquequirao']),
                    'is_nature': True,
                    'is_history': any(k in eid for k in ['city', 'valle', 'machu', 'moray', 'sacsay', 'qorikancha']),
                    'desc_es': t_data.get('includes') or t_data.get('name', eid),
                    'desc_en': t_data.get('includes') or t_data.get('name', eid),
                }))

                # Only a documented live duration can satisfy an exact time request.
                live_dur = duration_preference(t_data.get('duration'))
                if time_pref is not None and live_dur != time_pref:
                    continue

                # Restricción dura de caminatas negativas
                if no_hiking and prof['is_hiking']:
                    continue

                # Calificación por afinidad temática
                score = 0
                if has_nature and prof['is_nature']:
                    score += 3
                if has_history and prof['is_history']:
                    score += 3
                if has_hiking and prof['is_hiking']:
                    score += 4
                if not (has_nature or has_history or has_hiking):
                    score += 1

                if score > 0:
                    # Un tour agotado nunca se recomienda; se informa aparte.
                    if str(t_data.get('availability', 'available')).lower() == 'sold_out':
                        sold_out_matches.append((score, eid))
                        continue
                    candidates.append((score, eid, t_data, prof))

            candidates.sort(key=lambda c: c[0], reverse=True)
            selected_candidates = candidates[:4]
            recommendation_state['offered_ids'] = [c[1] for c in selected_candidates]

            rec_lines = []
            for _, c_eid, c_data, c_prof in selected_candidates:
                name = c_data.get('name', c_eid)
                if en:
                    from app import _get_tour_display_name
                    disp_name = _get_tour_display_name(c_eid, is_en=True) or name
                else:
                    disp_name = name

                dur = str(c_data.get('duration') or '').strip()
                c_overrides_dur = c_data.get('overridden_fields') or []
                if not dur and 'duration' not in c_overrides_dur:
                    # Solo usar respaldo canónico si NO fue borrado administrativamente
                    from catalog_service import CANONICAL_TOUR_DURATIONS
                    dur = CANONICAL_TOUR_DURATIONS.get(c_eid, '')
                dur_disp = localized_duration(dur, lang)

                sched = str(c_data.get('schedule') or '').strip()
                c_overrides = c_data.get('overridden_fields') or []
                if 'schedule' in c_overrides and not sched:
                    sched = ""

                desc = c_prof.get('desc_en' if en else 'desc_es', '')
                if pt or fr or it:
                    # Keep the live documented duration/schedule. Do not present
                    # an untranslated Spanish profile as a Portuguese response.
                    desc = ''

                details = [dur_disp]
                if c_eid == 'laguna-humantay':
                    details.append("4,200 m.a.s.l." if en else "4,200 m.s.n.m.")
                elif sched:
                    details.append(sched)

                details_str = ", ".join(d for d in details if d)
                summary = ' — '.join(part for part in (details_str, desc) if part)
                badge = availability_badge(c_data.get('availability'), lang_key)
                rec_lines.append(f"• *{disp_name}*{badge}" + (f" ({summary})." if summary else "."))

            sold_out_matches.sort(key=lambda s: s[0], reverse=True)
            sold_out_names = ', '.join(f"*{_avail_name(s_eid)}*" for _, s_eid in sold_out_matches[:4])

            if not rec_lines and sold_out_matches and not rejected_ids:
                msg = _ALL_MATCHES_SOLD_OUT[lang_key].format(names=sold_out_names)
                return finish(msg, 'evidence_recommendation', pending=True, needs_agency=False,
                              sources=['CATALOGO_OFICIAL'], recommendation_state=recommendation_state)

            if not rec_lines:
                if rejected_ids:
                    msg = (
                        "There are no other verified options matching these preferences after the tours you declined. "
                        "Would you like to change your preferences or revisit an earlier option?"
                        if en else
                        "No quedan otras opciones verificadas con esas preferencias después de los tours que rechazaste. "
                        "¿Quieres cambiar tus preferencias o volver a ver alguna opción anterior?"
                    )
                else:
                    msg = (
                        "I cannot confirm any active options matching these preferences with the catalog information available. "
                        "Would you like to adjust your preferences or check the missing details with an advisor?"
                        if en else
                        "No puedo confirmar opciones activas que coincidan con esas preferencias con la información disponible en el catálogo. "
                        "¿Quieres ajustar tus preferencias o confirmar los datos que faltan con un asesor?"
                    )
                if pt:
                    if rejected_ids:
                        msg = ("Não há outras opções verificadas com essas preferências após os passeios que você recusou. "
                               "Quer mudar suas preferências ou voltar a uma opção anterior?")
                    else:
                        msg = ("Não posso confirmar opções ativas que correspondam a essas preferências com os dados disponíveis no catálogo. "
                               "Quer ajustar suas preferências ou confirmar os dados que faltam com um assessor?")
                elif fr:
                    msg = ("Il ne reste aucune autre option vérifiée correspondant à vos préférences après les circuits refusés. "
                           "Voulez-vous modifier vos préférences ou revoir une option précédente?" if rejected_ids else
                           "Je ne peux pas confirmer d'option active correspondant à vos préférences avec les données du catalogue. "
                           "Voulez-vous ajuster vos préférences ou vérifier les détails manquants avec un conseiller?")
                elif it:
                    msg = ("Non restano altre opzioni verificate corrispondenti alle tue preferenze dopo i tour rifiutati. "
                           "Vuoi cambiare le preferenze o rivedere un'opzione precedente?" if rejected_ids else
                           "Non posso confermare opzioni attive corrispondenti alle tue preferenze con i dati del catalogo. "
                           "Vuoi modificare le preferenze o verificare i dettagli mancanti con un consulente?")
                return finish(msg, 'evidence_recommendation', pending=True, needs_agency=False, sources=['CATALOGO_OFICIAL'], recommendation_state=recommendation_state)

            body = "\n".join(rec_lines)
            if sold_out_matches:
                body += "\n\n" + _SOLD_OUT_EXCLUDED[lang_key].format(names=sold_out_names)
            if en:
                header = "🌟 Based on what you like, here are our top verified recommendations:\n"
                footer = "\n\n_Type the name of any tour for full details, photos or rates, or write 👉 advisor to coordinate with our team 😊_"
            elif pt:
                header = "🌟 Com suas preferências, estas são nossas recomendações verificadas:\n"
                footer = "\n\n_Escreva o nome de um passeio para consultar detalhes, fotos ou preços, ou escreva 👉 assessor para falar com nossa equipe 😊_"
            elif fr:
                header = "🌟 Voici nos recommandations vérifiées selon vos préférences:\n"
                footer = "\n\n_Écrivez le nom d'un circuit pour consulter ses détails, photos ou tarifs, ou contactez un conseiller 😊_"
            elif it:
                header = "🌟 Ecco i nostri suggerimenti verificati secondo le tue preferenze:\n"
                footer = "\n\n_Scrivi il nome di un tour per dettagli, foto o prezzi, oppure contatta un consulente 😊_"
            else:
                header = "🌟 Según lo que buscas, estas son nuestras recomendaciones verificadas:\n"
                footer = "\n\n_Escribe el nombre de cualquiera de ellos para ver detalles, fotos o tarifas, o escribe 👉 asesor para coordinar con nuestro equipo 😊_"
            return finish(header + body + footer, 'evidence_recommendation', sources=['CATALOGO_OFICIAL'], recommendation_state=recommendation_state)

        # Catálogo de tours solicitados (antes de evaluar fechas o disponibilidad comercial)
        listing_keywords = {
            'tour', 'tours', 'opcion', 'opciones', 'paquetes', 'catalogo',
            'ver tours', 'ver tour', 'ver catalogo', 'ver categorias', 'ver categoria',
            'categoria', 'categorias', 'category', 'categories',
            'view tours', 'view tour', 'view catalog', 'view categories', 'view category',
            'view tour categories', 'tour categories',
            'que tours tienen', 'que tours ofrecen', 'que tours hay', 'lista de tours',
            'cuales tours tienen', 'cuales son los tours', 'todos los tours',
            'que opciones tienen', 'que opciones hay', 'todas las opciones',
            'what tours do you offer', 'what tours do you have', 'all tours',
            'show me all options', 'list of tours',
            'passeio', 'passeios', 'ver passeios', 'ver categorias de passeios'
        }
        # ---- CATÁLOGO NAVEGABLE POR CATEGORÍAS (DINÁMICO) ----
        CAT_SPECS = get_dynamic_cat_specs(active_tours)
        pt_cat_titles = {
            'treks': '🏔️ *Machu Picchu e trilhas*',
            'cusco': '🌄 *Montanhas e clássicos (Cusco)*',
            'reg': '🚌 *Rotas regionais*',
        }
        translated_cat_titles = {
            'fr': {'treks': '🏔️ *Machu Picchu et treks*', 'cusco': '🌄 *Montagnes et classiques (Cusco)*', 'reg': '🚌 *Circuits régionaux*'},
            'it': {'treks': '🏔️ *Machu Picchu e trekking*', 'cusco': '🌄 *Montagne e classici (Cusco)*', 'reg': '🚌 *Itinerari regionali*'},
        }

        # 1. Petición de categoría específica (ej. "categoria treks", "category treks", "categoria cusco", etc.)
        is_cat_treks = bool(re.search(r'\b((?:categor[iy]a?|categorie)\s+treks?|categor[iy]a?\s+machu|categor[iy]a?\s+1|treks?\s+y\s+machu|treks?\s+and\s+machu)\b', q))
        is_cat_cusco = bool(re.search(r'\b((?:categor[iy]a?|categorie)\s+cusco|categor[iy]a?\s+monta[nñ]as|categor[iy]a?\s+mountains|categor[iy]a?\s+2|clasicos\s+cusco|cusco\s+classics)\b', q))
        is_cat_reg = bool(re.search(r'\b((?:categor[iy]a?|categorie)\s+reg\w*|categor[iy]a?\s+rutas|categor[iy]a?\s+routes|categor[iy]a?\s+3|rutas\s+regionales|regional\s+routes)\b', q))
        selected_cat_key = None
        if is_cat_treks: selected_cat_key = 'treks'
        elif is_cat_cusco: selected_cat_key = 'cusco'
        elif is_cat_reg: selected_cat_key = 'reg'

        if selected_cat_key:
            cat_data = CAT_SPECS.get(selected_cat_key, {})
            active_in_cat = [
                (eid, default_label, default_dur)
                for eid, default_label, default_dur in cat_data.get('tours', [])
                if eid in active_tours and is_product_confirmed(eid) and not is_deactivated_tour(eid)
            ]
            if not active_in_cat:
                cat_name = cat_data.get('title_es', selected_cat_key) if not en else cat_data.get('title_en', selected_cat_key)
                msg = (f"Actualmente no hay tours disponibles en la categoría {cat_name}. 📋\n\nPuedes explorar otras categorías o comunicarte con un asesor 😊"
                       if not en else
                       f"Currently there are no tours available in the category {cat_name}. 📋\n\nYou can explore other categories or contact an advisor 😊")
                if pt:
                    msg = f"No momento não há passeios disponíveis em {pt_cat_titles[selected_cat_key]}. Você pode explorar outras categorias ou consultar um assessor."
                elif fr or it:
                    cat_name = translated_cat_titles[lang][selected_cat_key]
                    msg = (f"Aucun circuit actif dans {cat_name}. Vous pouvez explorer d'autres catégories ou contacter un conseiller."
                           if fr else f"Non ci sono tour attivi in {cat_name}. Puoi esplorare altre categorie o contattare un consulente.")
                return finish(msg, 'evidence_category_empty', sources=['CATALOGO_OFICIAL'], entity_id=f"cat_{selected_cat_key}")

            cat_title = cat_data.get('title_es', '') if not en else cat_data.get('title_en', '')
            if pt:
                cat_title = pt_cat_titles[selected_cat_key]
            elif fr or it:
                cat_title = translated_cat_titles[lang][selected_cat_key]

            m_page = re.search(r'\b(?:p[aá]gina|page)\s+(\d+)\b', q)
            requested_page = int(m_page.group(1)) if m_page else 0
            pages = paginate_category_tours(active_in_cat)
            total_pages = len(pages)
            if requested_page >= total_pages:
                requested_page = 0
            page_slice = pages[requested_page] if pages else active_in_cat

            if total_pages <= 1:
                lines = [f"{cat_title} disponibles:\n" if not en else f"{cat_title} available:\n"]
                if pt:
                    lines = [f"{cat_title} disponíveis:\n"]
                elif fr or it:
                    lines = [f"{cat_title} disponibles:\n" if fr else f"{cat_title} disponibili:\n"]
                for eid, default_label, default_dur in page_slice:
                    t_obj = active_tours.get(eid, {})
                    if en:
                        from app import _get_tour_display_name
                        tour_name = _get_tour_display_name(eid, is_en=True) or default_label
                    else:
                        tour_name = t_obj.get('name', default_label)
                    dur = (t_obj.get('duration') or default_dur or '').strip()
                    dur = localized_duration(dur, lang)
                    sched = str(t_obj.get('schedule') or '').strip()
                    if dur and sched:
                        detail_str = f"{dur} | {sched}"
                    elif dur:
                        detail_str = dur
                    elif sched:
                        detail_str = sched
                    else:
                        detail_str = "A confirmar" if pt else ("Por confirmar" if not en else "To be confirmed")
                    avail_badge = availability_badge(t_obj.get('availability', 'available'), lang_key)
                    lines.append(f"• *{tour_name}*{avail_badge} ({detail_str})")
                footer = (
                    "\n_Escribe directamente el nombre de cualquier tour para ver detalles completos, o selecciona una opción abajo:_\nEscribe 👉 *asesor* si necesitas ayuda personalizada 😊"
                    if not en else
                    "\n_Type the name of any tour for full details, or select an option below:_\nWrite 👉 *advisor* for personalized help 😊"
                )
                if pt:
                    footer = "\n_Escreva o nome de um passeio para consultar detalhes ou selecione uma opção abaixo:_\nEscreva 👉 *assessor* se precisar de ajuda personalizada 😊"
                elif fr:
                    footer = "\n_Écrivez le nom d'un circuit pour consulter ses détails ou choisissez une option ci-dessous. Contactez un conseiller pour plus d'aide._"
                elif it:
                    footer = "\n_Scrivi il nome di un tour per i dettagli o scegli un'opzione qui sotto. Contatta un consulente per assistenza._"
            else:
                header = (
                    f"{cat_title} (Página {requested_page + 1} de {total_pages}):\n"
                    if not en else
                    f"{cat_title} (Page {requested_page + 1} of {total_pages}):\n"
                )
                if pt:
                    header = f"{cat_title} (Página {requested_page + 1} de {total_pages}):\n"
                elif fr or it:
                    header = (f"{cat_title} (Page {requested_page + 1} sur {total_pages}):\n" if fr else
                              f"{cat_title} (Pagina {requested_page + 1} di {total_pages}):\n")
                lines = [header]
                for eid, default_label, default_dur in page_slice:
                    t_obj = active_tours.get(eid, {})
                    if en:
                        from app import _get_tour_display_name
                        tour_name = _get_tour_display_name(eid, is_en=True) or default_label
                    else:
                        tour_name = t_obj.get('name', default_label)
                    dur = (t_obj.get('duration') or default_dur or '').strip()
                    dur = localized_duration(dur, lang)
                    sched = str(t_obj.get('schedule') or '').strip()
                    if dur and sched:
                        detail_str = f"{dur} | {sched}"
                    elif dur:
                        detail_str = dur
                    elif sched:
                        detail_str = sched
                    else:
                        detail_str = "A confirmar" if pt else ("Por confirmar" if not en else "To be confirmed")
                    avail_badge = availability_badge(t_obj.get('availability', 'available'), lang_key)
                    lines.append(f"• *{tour_name}*{avail_badge} ({detail_str})")

                if requested_page + 1 < total_pages:
                    nav_note = (
                        "\n_Usa las opciones abajo para ver detalles, pasar a ➡️ Más tours o volver a ⬅️ Categorías._"
                        if not en else
                        "\n_Use the options below for details, go to ➡️ More tours, or return to ⬅️ Categories._"
                    )
                else:
                    nav_note = (
                        "\n_Has llegado al final de esta categoría. Selecciona un tour o vuelve a ⬅️ Categorías._"
                        if not en else
                        "\n_You have reached the end of this category. Select a tour or return to ⬅️ Categories._"
                    )
                footer = (
                    f"{nav_note}\nEscribe 👉 *asesor* si necesitas ayuda personalizada 😊"
                    if not en else
                    f"{nav_note}\nWrite 👉 *advisor* for personalized help 😊"
                )
                if pt:
                    nav_note = ("\n_Selecione um passeio, avance em ➡️ Mais passeios ou volte a ⬅️ Categorias._"
                                if requested_page + 1 < total_pages else
                                "\n_Você chegou ao final desta categoria. Selecione um passeio ou volte a ⬅️ Categorias._")
                    footer = f"{nav_note}\nEscreva 👉 *assessor* se precisar de ajuda personalizada 😊"
                elif fr:
                    nav_note = ("\n_Choisissez un circuit, passez à Autres circuits ou revenez aux Catégories._" if requested_page + 1 < total_pages else
                                "\n_Vous êtes à la fin de cette catégorie. Choisissez un circuit ou revenez aux Catégories._")
                    footer = nav_note + "\nContactez un conseiller pour plus d'aide."
                elif it:
                    nav_note = ("\n_Scegli un tour, vai ad Altri tour o torna alle Categorie._" if requested_page + 1 < total_pages else
                                "\n_Sei alla fine di questa categoria. Scegli un tour o torna alle Categorie._")
                    footer = nav_note + "\nContatta un consulente per assistenza."
            lines.append(footer)
            return finish("\n".join(lines), 'evidence_category_tours', sources=['CATALOGO_OFICIAL'], entity_id=f"cat_{selected_cat_key}")

        # 2. Petición de catálogo general (Ver Tours / Categorías)
        is_listing_request = (
            q in {'je cherche les categories de circuits', 'mostra le categorie di tour'} or
            q.strip(' ?¿!.') in listing_keywords or
            bool(re.search(r'\b(muestr\w*|meustr\w*|mostr\w*|ver|view|show|dime|tell\s+me|cuales|which|what|tienen?|do\s+you\s+have|hay)\b.*?\b(tours?|opciones?|options?|paquetes?|packages?|destinos?|destinations?|viajes?|trips?|rutas?|routes?|circuitos?|paseos?|categorias?|categories)\b', q) and
                  not re.search(r'\b(precio|precios|cuesta|cuanto|costo|costos|tarifa|tarifas|price|prices|cost|costs|rate|rates|soles|dolares|\busd\b|\bpen\b|horario|hora|duracion|duration|schedule|incluye|includes?|itinerario|itinerary|fotos?|photos?|imagen|image|imagenes|images|brochure|folleto|cancel|reembols|refund|yape|paypal|pagar|pay|pago|payment|adelant|deposit|descuento|discount|reserva|book|booking|cupos?|disponib\w*|agotad\w*|sold\s*out|visitad\w*|popular\w*|imperdibl\w*|must\s*see|top\s+tours?|top\s+destin\w*|pedid\w*|vendid\w*|manana|tomorrow|7d|7\s*d[ií]as?|7.day)\b|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}', q) and
                  support.detect_entity_from_question(q) is None) or
            bool(re.search(r'\b(es el unic\w|es la unic\w|es lo unic\w|hay mas|tienen mas|otros? tours?|otras? opciones?|otros? lugares?|otros? destinos?|otros? paquetes?|que m[aá]s tienen|que mas tienen|mas opciones|m[aá]s opciones|other tours?|other options?|more tours?|more options?|anything else)\b', q) and
                  not re.search(r'\b(cancel|reembols|yape|paypal|pagar|pago|manana|tomorrow)\b', q) and
                  (support.detect_entity_from_question(q) is None or
                   bool(re.search(r'\b(aparte\s+de|adem[aá]s\s+de|fuera\s+de|other\s+than|besides|apart\s+from)\b', q)))) or
            (bool(re.search(r'\b(tours?|viajes?|opciones?|paquetes?|cuales?|muestr\w*|ver|dime)\b.*?\bdisponibles?\b', q) or
                  re.search(r'\bdisponibles?\b.*?\b(tours?|viajes?|opciones?|paquetes?)\b', q)) and
             not re.search(r'\b(manana|tomorrow|hoy|today|enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre|noviembre|diciembre)\b|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}', q) and
             support.detect_entity_from_question(q) is None) or
            bool(re.search(r'^\s*(tours?|viajes?|opciones?|options?|destinos?|destinations?|categorias?|categories|ver\s+categorias?|view\s+categories?|view\s+tour\s+categories|ver\s+tours?|view\s+tours?)\s*$', q))
        )
        if is_listing_request:
            has_any_active = any(
                len(cat.get('tours', [])) > 0
                for cat in CAT_SPECS.values()
            )
            if not has_any_active:
                msg = ("Actualmente no disponemos de tours activos en el catálogo. Por favor consulta con un asesor."
                       if not en else
                       "Currently we have no active tours in the catalog. Please consult with an advisor.")
                return finish(msg, 'evidence_catalog_empty', pending=True, sources=['CATALOGO_OFICIAL'])

            is_asking_unique = bool(re.search(r'\b(es el unic\w|es la unic\w|es lo unic\w|hay mas|tienen mas|otros? tours?|otras? opciones?|otros? lugares?|otros? destinos?|que m[aá]s tienen|mas opciones|m[aá]s opciones|other tours?|more tours?|more options?|anything else)\b', q))
            if en:
                if is_asking_unique:
                    title = "Not at all! We have many more confirmed tour options at *Texeira Travel*. Explore them by category: 🗺️\n\n"
                else:
                    title = "🗺️ *Tour Experiences — Texeira Travel*\nSelect a category to explore our available tours:\n\n"
                
                cat_lines = []
                num_emojis = ['1️⃣', '2️⃣', '3️⃣']
                for idx, (cat_key, cat_data) in enumerate(CAT_SPECS.items()):
                    cnt = sum(1 for eid, _, _ in cat_data['tours'] if eid in active_tours and is_product_confirmed(eid))
                    if cnt > 0:
                        cat_lines.append(f"{num_emojis[idx]} {cat_data['title_en']} ({cnt} tours)")
                body = "\n".join(cat_lines)
                footer = "\n\n_Tap a category or write the name of the tour you're looking for (e.g. Inca Trail, Humantay Lake)._\nWrite 👉 *advisor* to reach our team."
            elif pt:
                title = "🗺️ *Catálogo de experiências — Texeira Travel*\nSelecione uma categoria para explorar nossos passeios:\n\n"
                cat_lines = []
                for idx, (cat_key, cat_data) in enumerate(CAT_SPECS.items()):
                    cnt = sum(1 for eid, _, _ in cat_data['tours'] if eid in active_tours and is_product_confirmed(eid))
                    if cnt:
                        cat_lines.append(f"{['1️⃣', '2️⃣', '3️⃣'][idx]} {pt_cat_titles[cat_key]} ({cnt} passeios)")
                body = "\n".join(cat_lines)
                footer = "\n\n_Selecione uma categoria ou escreva o nome do passeio que procura._\nEscreva 👉 *assessor* para falar com nossa equipe."
            elif fr or it:
                title = ("🗺️ *Circuits — Texeira Travel*\nSélectionnez une catégorie pour explorer nos circuits actifs:\n\n" if fr else
                         "🗺️ *Tour — Texeira Travel*\nSeleziona una categoria per esplorare i tour attivi:\n\n")
                cat_lines = []
                for idx, (cat_key, cat_data) in enumerate(CAT_SPECS.items()):
                    cnt = sum(1 for eid, _, _ in cat_data['tours'] if eid in active_tours and is_product_confirmed(eid))
                    if cnt:
                        cat_lines.append(f"{['1️⃣', '2️⃣', '3️⃣'][idx]} {translated_cat_titles[lang][cat_key]} ({cnt} {'circuits' if fr else 'tour'})")
                body = "\n".join(cat_lines)
                footer = ("\n\n_Choisissez une catégorie ou écrivez le nom du circuit. Contactez un conseiller pour plus d'aide._" if fr else
                          "\n\n_Scegli una categoria o scrivi il nome del tour. Contatta un consulente per assistenza._")
            else:
                if is_asking_unique:
                    title = "¡Para nada! No es el único. En *Texeira Travel* organizamos nuestros destinos en estas categorías: 🗺️\n\n"
                else:
                    title = "🗺️ *Catálogo de Experiencias — Texeira Travel*\nSelecciona una categoría para explorar nuestros tours disponibles:\n\n"
                
                cat_lines = []
                num_emojis = ['1️⃣', '2️⃣', '3️⃣']
                for idx, (cat_key, cat_data) in enumerate(CAT_SPECS.items()):
                    cnt = sum(1 for eid, _, _ in cat_data['tours'] if eid in active_tours and is_product_confirmed(eid))
                    if cnt > 0:
                        cat_lines.append(f"{num_emojis[idx]} {cat_data['title_es']} ({cnt} tours)")
                body = "\n".join(cat_lines)
                footer = "\n\n_Pulsa una categoría o escribe directamente el nombre del tour que buscas (ej. Camino Inca, Laguna Humantay)._\nEscribe 👉 *asesor* para comunicarte con nuestro equipo."

            return finish(title + body + footer, 'evidence_listing', sources=['F1','F2','F3'])

        # --- TARIFAS ESPECIALES (Estudiantes, Menores/Niños, Promociones) ---
        def detect_rate_category(query_norm):
            if re.search(r'\b(estudiante\w*|student\w*|universitari\w*|carnet\w*|isic|sunedu)\b', query_norm):
                return 'student'
            if re.search(r'\b(ni[nñ]o\w*|child\w*|kid\w*|menor\w*|infantil\w*|hijo\w*|bebe\w*)\b', query_norm):
                return 'child'
            if re.search(r'\b(promo\w*|promoci[oó]n\w*|oferta\w*|descuento\w*|discount\w*)\b', query_norm):
                return 'promo'
            return None

        commercial_q = support.commercial_query_text(q)
        rate_cat = detect_rate_category(commercial_q)
        if re.search(r'\b(segur\w*|safe\w*|wheelchair|silla de ruedas|embaraz\w*|pregnan\w*)\b', q):
            return unknown('condiciones de seguridad o accesibilidad', entity_id=entity(q))
        rate_question = (field(q) == 'price' or
                         re.search(r'\b(tarifa\w*|descuent\w*|promo\w*|discount\w*|rate\w*)\b', commercial_q) or
                         re.fullmatch(r'(y |and )?(para |for )?(los |las )?(estudiantes?|students?|ninos?|children|kids)\??', commercial_q))
        if rate_cat and rate_question:
            eid_rate = entity(q)
            if not eid_rate:
                for h in reversed(prior):
                    if h.get('role') == 'human':
                        eid_rate = entity(support.normalize(h['content']))
                        if eid_rate:
                            break

            if eid_rate and eid_rate in active_tours:
                if re.search(r'\b(manana|tomorrow)\b|\d{4}-\d{2}-\d{2}|\d{1,2}\s+de\s+\w+', q):
                    return unknown('tarifa para la fecha solicitada', entity_id=eid_rate)
                tour_obj = active_tours.get(eid_rate, {})
                name = tour_obj.get('name', eid_rate)
                base_price = str(tour_obj.get('official_price') or '').strip()
                base_curr = str(tour_obj.get('currency') or 'USD').strip()
                if not base_price:
                    for f in get_facts(eid_rate):
                        if f.field == 'official_price' and f.value:
                            base_price = str(f.value).strip()
                            break

                rates = []
                try:
                    from catalog_service import get_tour_rates
                    rates = get_tour_rates(eid_rate, active_only=True)
                except Exception:
                    pass

                # Buscar tarifa coincidente por categoría o texto
                matching = [
                    r for r in rates
                    if r.get('rate_category') == rate_cat or rate_cat in support.normalize(r.get('rate_name', ''))
                ]

                cat_labels_es = {
                    'student': 'estudiantes',
                    'child': 'menores / niños',
                    'promo': 'promociones o descuentos'
                }
                cat_labels_en = {
                    'student': 'students',
                    'child': 'children / kids',
                    'promo': 'promotions or discounts'
                }

                if len(matching) > 1:
                    options = '\n'.join(
                        f"• {r['rate_name']}: {r['price']} {r['currency']} — {r.get('conditions') or ('Confirm requirements' if en else 'Confirmar requisitos')}"
                        for r in matching)
                    prompt = 'Which rate applies to your case?' if en else '¿Qué tarifa corresponde a tu caso?'
                    return finish(f"*{name}*\n{options}\n\n{prompt}", 'evidence_rate_options',
                                  pending=True, sources=['CATALOGO_OFICIAL'], entity_id=eid_rate)
                if matching:
                    r = matching[0]
                    r_name = r.get('rate_name', 'Tarifa Especial')
                    r_price = r.get('price', '')
                    r_curr = r.get('currency', base_curr)
                    r_cond = str(r.get('conditions') or '').strip()
                    r_valid_to = str(r.get('valid_to') or '').strip()

                    cat_emojis = {'student': '🎓', 'child': '🧒', 'promo': '🏷️'}
                    icon = cat_emojis.get(rate_cat, '💰')

                    lines = [f"{icon} *{name} — {r_name}*"]
                    lines.append(f"• Tarifa especial: *{r_price} {r_curr}* por persona" if not en else f"• Special rate: *{r_price} {r_curr}* per person")
                    if r_cond:
                        lines.append(f"• Requisitos: {r_cond}" if not en else f"• Requirements: {r_cond}")
                    if r_valid_to:
                        lines.append(f"• Válido hasta: {r_valid_to}" if not en else f"• Valid until: {r_valid_to}")
                    if base_price:
                        base_disp = base_price if any(c in base_price for c in ['USD', 'PEN', '$', 'S/']) else f"{base_price} {base_curr}"
                        lines.append(f"• Tarifa general publicada: {base_disp}" if not en else f"• Published general rate: {base_disp}")

                    footer = '\n\nEscribe 👉 *asesor* para coordinar tu reserva 😊' if not en else '\n\nWrite 👉 *advisor* to complete your booking 😊'
                    return finish("\n".join(lines) + footer, 'evidence_special_rate', sources=['CATALOGO_OFICIAL'], entity_id=eid_rate)
                else:
                    # NO INVENTAR DESCUENTO: Indicar claramente que no existe tarifa especial registrada
                    cat_txt = cat_labels_en.get(rate_cat, 'special') if en else cat_labels_es.get(rate_cat, 'especial')
                    lines = [f"ℹ️ *{name}*"]
                    if en:
                        lines.append(f"Currently we do not have a registered special rate for *{cat_txt}* for this tour.")
                        if base_price:
                            base_disp = base_price if any(c in base_price for c in ['USD', 'PEN', '$', 'S/']) else f"{base_price} {base_curr}"
                            lines.append(f"The official published rate is *{base_disp}* per person.")
                        lines.append("\nWrite 👉 *advisor* if you would like to inquire about group conditions 😊")
                    else:
                        lines.append(f"Actualmente no disponemos de una tarifa especial para *{cat_txt}* registrada en nuestro catálogo oficial.")
                        if base_price:
                            base_disp = base_price if any(c in base_price for c in ['USD', 'PEN', '$', 'S/']) else f"{base_price} {base_curr}"
                            lines.append(f"La tarifa oficial vigente es de *{base_disp}* por persona.")
                        lines.append("\nEscribe 👉 *asesor* si deseas consultar condiciones especiales para grupos o delegaciones 😊")

                    return finish("\n".join(lines), 'evidence_no_special_rate', pending=True, sources=['CATALOGO_OFICIAL'], entity_id=eid_rate)

        # Operaciones comerciales, pagos y disponibilidad de cupos/fechas
        if re.search(r'cancel|reembols|refund|yape|paypal|\bpagar\b|\bpago\b|pagamento|adelant|deposit|\bpay\b|payment|descuento|discount|reserva|booking|\bbook\b|cupos?|espacios?|vagas?|spots?|availability|available|disponib|agotad|ocupad|sold\s*out|manana|tomorrow|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}|febrero|february|fevereiro', commercial_q):
            # 1. Métodos de pago
            is_payment_methods = bool(re.search(
                r'\b(?:m[eé]todos?\s+de\s+pago|formas?\s+de\s+pago|como\s+puedo\s+pagar|como\s+pagar|payment\s+methods?|how\s+(?:can\s+i|to)\s+pay|formas?\s+de\s+pagamento)\b',
                q
            ))
            if is_payment_methods:
                if en:
                    msg = (
                        "💳 *Payment Methods — Texeira Travel:*\n\n"
                        "We coordinate bookings and payments through:\n"
                        "• 🏦 *Bank Transfer:* BCP and Interbank (in USD and PEN).\n"
                        "• 💳 *Credit / Debit Cards:* Visa and Mastercard (upon prior coordination).\n"
                        "• 💵 *Cash:* Directly at our office in Cusco (Calle Carmen Quicllu N.° 250).\n\n"
                        "👉 To receive bank account details or confirm your spot, write: *advisor*."
                    )
                elif pt:
                    msg = (
                        "💳 *Formas de Pagamento — Texeira Travel:*\n\n"
                        "Coordenamos reservas e pagamentos através de:\n"
                        "• 🏦 *Transferência Bancária:* BCP e Interbank (em Dólares USD e Soles).\n"
                        "• 💳 *Cartões de Crédito / Débito:* Visa e Mastercard (com coordenação prévia).\n"
                        "• 💵 *Dinheiro (Espécie):* Diretamente em nossa agência em Cusco (Calle Carmen Quicllu N.° 250).\n\n"
                        "👉 Para receber dados bancários ou confirmar sua vaga, escreva: *assessor*."
                    )
                else:
                    msg = (
                        "💳 *Métodos de Pago — Texeira Travel:*\n\n"
                        "Coordinamos tus pagos y confirmación de reservas mediante:\n"
                        "• 🏦 *Transferencia Bancaria / Interbancaria:* Cuentas BCP e Interbank (Soles y Dólares USD).\n"
                        "• 💳 *Tarjetas de Crédito / Débito:* Visa y Mastercard (previa coordinación).\n"
                        "• 💵 *Efectivo:* Directamente en nuestra oficina oficial en Cusco (Calle Carmen Quicllu N.° 250).\n\n"
                        "👉 Para proporcionarte los números de cuenta o coordinar tu reserva, escribe: *asesor*."
                    )
                return finish(msg, 'evidence_unknown', True, entity_id=None)

            eid_comercial = entity(q)
            if not eid_comercial:
                for h in reversed(prior):
                    if h.get('role') == 'human':
                        eid_comercial = entity(support.normalize(h['content']))
                        if eid_comercial: break

            if eid_comercial:
                if is_deactivated_tour(eid_comercial) or eid_comercial not in active_tours:
                    tour_info = None
                    try:
                        import catalog_service
                        tour_info = catalog_service.get_tour_by_id(eid_comercial)
                    except Exception:
                        pass
                    name_deact = tour_info.get('name', eid_comercial) if tour_info else eid_comercial
                    if en:
                        msg = f"*{name_deact}* is not currently in our active catalog. You can explore other tours or consult this destination with an advisor."
                    else:
                        msg = f"*{name_deact}* no figura actualmente en nuestro catálogo activo. Puedes explorar otros tours o consultar este destino con un asesor."
                    return finish(msg, 'evidence_inactive_tour', pending=True, entity_id=eid_comercial)

            # 2. Consultas de disponibilidad, cupos, agotados o fechas
            import catalog_service
            parsed_query_date = catalog_service.parse_date_from_query(question)
            is_availability_query = bool(re.search(
                r'\b(?:disponib\w*|cupos?|espacios?|vagas?|spots?|availability|available|agotad\w*|ocupad\w*|sold\s*out|full|fechas?\s+disponibles?|hay\s+lugar|queda\s+lugar|hay\s+salidas?|hay\s+fechas?)\b',
                q
            )) or bool(re.search(r'\b(?:febrero|february|fevereiro)\b', q)) or (parsed_query_date is not None)

            if is_availability_query:
                # 2.1 Camino Inca en Febrero (Cierre por mantenimiento oficial de ruta)
                is_inca_trail = (eid_comercial == 'camino-inka') or bool(re.search(r'camino\s+in[ck]a|in[ck]a\s+trail|trilha\s+inca', q))
                is_february = bool(re.search(r'\b(?:febrero|february|fevereiro)\b', q))
                if is_inca_trail and is_february:
                    if en:
                        msg = (
                            "⛔ *Important Notice — Inca Trail in February:*\n\n"
                            "The **Inca Trail (4D/3N)** is closed throughout the entire month of **February** by official regulations of the Ministry of Culture and SERNANP for environmental maintenance and trail conservation.\n\n"
                            "💡 *Recommended alternatives during this time:*\n"
                            "• 🌄 **Inka Jungle (4D/3N):** Adventure trekking route to Machu Picchu (open in February).\n"
                            "• 🚂 **Machu Picchu by Train:** Regular daily departures all year round.\n\n"
                            "👉 Write: *advisor* to check available dates or plan your itinerary."
                        )
                    elif pt:
                        msg = (
                            "⛔ *Aviso Importante — Trilha Inca em Fevereiro:*\n\n"
                            "A **Trilha Inca (4D/3N)** permanece fechada durante todo o mês de **fevereiro** por determinação oficial do Ministério de Cultura e SERNANP para manutenção ambiental e conservação da rota.\n\n"
                            "💡 *Alternativas recomendadas para essa época:*\n"
                            "• 🌄 **Inka Jungle (4D/3N):** Trilha de aventura e trekking aberta até Machu Picchu.\n"
                            "• 🚂 **Machu Picchu de trem:** Saídas diárias regulares o ano todo.\n\n"
                            "👉 Escreva: *assessor* para verificar datas alternativas ou planejar seu roteiro."
                        )
                    else:
                        msg = (
                            "⛔ *Aviso Importante — Camino Inca en Febrero:*\n\n"
                            "El **Camino Inca (4D/3N)** permanece cerrado durante todo el mes de **febrero** por disposición oficial del Ministerio de Cultura y SERNANP para trabajos de mantenimiento ambiental y conservación de la ruta.\n\n"
                            "💡 *Alternativas recomendadas para esa temporada:*\n"
                            "• 🌄 **Inka Jungle (4D/3N):** Ruta de aventura y senderismo abierta hacia Machu Picchu.\n"
                            "• 🚂 **Machu Picchu en tren:** Salidas diarias regulares durante todo el año.\n\n"
                            "👉 Escribe: *asesor* para evaluar fechas alternativas o coordinar tu itinerario."
                        )
                    return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id='camino-inka')

                # 2.2 Disponibilidad de un tour específico según catálogo
                if eid_comercial and eid_comercial in active_tours:
                    tour_obj = active_tours[eid_comercial]
                    t_name = tour_obj.get('name', eid_comercial)

                    # Evaluar si la consulta menciona una fecha específica (o hereda fecha reciente)
                    parsed_date = parsed_query_date
                    if not parsed_date and prior:
                        for h in reversed(prior):
                            if h.get('role') == 'human':
                                parsed_date = catalog_service.parse_date_from_query(h.get('content', ''))
                                if parsed_date:
                                    break

                    if parsed_date:
                        date_info = catalog_service.get_tour_availability_on_date(eid_comercial, parsed_date)
                        date_status = date_info.get('status', 'available')
                        date_disp = catalog_service.format_date_localized(parsed_date, lang)
                        # La nota del bloqueo es interna (panel: "Motivo o nota interna"):
                        # se reserva para el ticket del asesor y nunca se muestra al turista.
                        note_suffix = ""

                        if date_status == 'sold_out':
                            if en:
                                msg = (
                                    f"🔴 *Availability — {t_name}:*\n\n"
                                    f"For the requested date (*{date_disp}*), spots for *{t_name}* are **currently sold out**{note_suffix}.\n\n"
                                    f"Our agency team can check if any spots open up or recommend the nearest available departure date.\n\n"
                                    f"👉 Write: *advisor* to check alternative dates or join the waitlist."
                                )
                            elif pt:
                                msg = (
                                    f"🔴 *Disponibilidade — {t_name}:*\n\n"
                                    f"Para a data consultada (*{date_disp}*), as vagas para *{t_name}* estão **atualmente esgotadas**{note_suffix}.\n\n"
                                    f"Nossa equipe na agência pode verificar se surgem vagas de última hora ou sugerir a data disponível mais próxima.\n\n"
                                    f"👉 Escreva: *assessor* para consultar datas alternativas ou lista de espera."
                                )
                            else:
                                msg = (
                                    f"🔴 *Disponibilidad — {t_name}:*\n\n"
                                    f"Para la fecha consultada (*{date_disp}*), los cupos para *{t_name}* se encuentran **actualmente agotados**{note_suffix}.\n\n"
                                    f"Nuestro equipo en la agencia puede verificar si se liberan espacios de última hora o recomendarte la fecha más cercana disponible.\n\n"
                                    f"👉 Escribe: *asesor* para consultar fechas alternativas o lista de espera."
                                )
                            return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id=eid_comercial)

                        if date_status == 'limited':
                            if en:
                                msg = (
                                    f"🟡 *Availability — {t_name}:*\n\n"
                                    f"For *{date_disp}*, *{t_name}* has **limited spots remaining** due to high demand{note_suffix}.\n\n"
                                    f"We strongly recommend securing your seats promptly before availability closes.\n\n"
                                    f"👉 Write: *advisor* with your group size to book your spots right away."
                                )
                            elif pt:
                                msg = (
                                    f"🟡 *Disponibilidade — {t_name}:*\n\n"
                                    f"Para *{date_disp}*, o passeio *{t_name}* conta com **últimas vagas disponíveis** e alta procura{note_suffix}.\n\n"
                                    f"Recomendamos garantir seus lugares o quanto antes para não ficar sem vaga.\n\n"
                                    f"👉 Escreva: *assessor* com o número de pessoas para reservar de imediato."
                                )
                            else:
                                msg = (
                                    f"🟡 *Disponibilidad — {t_name}:*\n\n"
                                    f"Para el *{date_disp}*, el tour *{t_name}* cuenta con **cupos limitados** (alta demanda){note_suffix}.\n\n"
                                    f"Te recomendamos asegurar tus espacios con anticipación antes de que se agote la fecha.\n\n"
                                    f"👉 Escribe: *asesor* indicando el número de personas para reservar de inmediato."
                                )
                            return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id=eid_comercial)

                        # Tour disponible para la fecha consultada
                        if en:
                            msg = (
                                f"🟢 *Availability — {t_name}:*\n\n"
                                f"We have **departures and spots available** for *{date_disp}*.\n\n"
                                f"👉 Write: *advisor* with your group size to coordinate your booking and departure details 😊"
                            )
                        elif pt:
                            msg = (
                                f"🟢 *Disponibilidade — {t_name}:*\n\n"
                                f"Temos **saídas e vagas disponíveis** para *{date_disp}*.\n\n"
                                f"👉 Escreva: *assessor* com o número de pessoas para coordenar sua reserva e detalhes de saída 😊"
                            )
                        else:
                            msg = (
                                f"🟢 *Disponibilidad — {t_name}:*\n\n"
                                f"Contamos con **salidas y cupos disponibles** para el *{date_disp}*.\n\n"
                                f"👉 Escribe: *asesor* indicando tu número de personas para coordinar tu reserva y enviarte los detalles de salida 😊"
                            )
                        return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id=eid_comercial)

                    t_avail = catalog_service.get_tour_availability(eid_comercial)

                    # Si está marcado como agotado en catálogo
                    if t_avail == 'sold_out':
                        if en:
                            msg = (
                                f"🔴 *Availability — {t_name}:*\n\n"
                                f"Spots for *{t_name}* are **temporarily sold out** for upcoming dates or the current season.\n\n"
                                f"Our agency team can check for last-minute openings or recommend similar alternatives.\n\n"
                                f"👉 Write: *advisor* to check upcoming dates or options."
                            )
                        elif pt:
                            msg = (
                                f"🔴 *Disponibilidade — {t_name}:*\n\n"
                                f"As vagas para *{t_name}* estão **temporariamente esgotadas** para as próximas datas ou temporada atual.\n\n"
                                f"Nossa equipe na agência pode verificar vagas de última hora ou recomendar alternativas semelhantes.\n\n"
                                f"👉 Escreva: *assessor* para consultar próximas datas ou opções."
                            )
                        else:
                            msg = (
                                f"🔴 *Disponibilidad — {t_name}:*\n\n"
                                f"Los cupos para *{t_name}* se encuentran **temporalmente agotados** (sin cupos disponibles) para las fechas próximas o temporada actual.\n\n"
                                f"Nuestro equipo en la agencia puede verificar si se liberan espacios de última hora o recomendarte la mejor alternativa disponible.\n\n"
                                f"👉 Escribe: *asesor* para consultar próximas fechas o tours similares."
                            )
                        return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id=eid_comercial)

                    # Si está marcado con cupos limitados en catálogo
                    if t_avail == 'limited':
                        if en:
                            msg = (
                                f"🟡 *Availability — {t_name}:*\n\n"
                                f"This tour has **limited spots** and high demand for upcoming departures.\n\n"
                                f"Seat availability is confirmed in real time based on daily operational capacity.\n\n"
                                f"👉 Write: *advisor* with your tentative date and group size to secure your spot."
                            )
                        elif pt:
                            msg = (
                                f"🟡 *Disponibilidade — {t_name}:*\n\n"
                                f"Este passeio conta com **vagas limitadas** e alta procura para as próximas saídas.\n\n"
                                f"A disponibilidade é confirmada em tempo real conforme as vagas operacionais do dia.\n\n"
                                f"👉 Escreva: *assessor* informando sua data prevista e número de pessoas para garantir sua vaga."
                            )
                        else:
                            msg = (
                                f"🟡 *Disponibilidad — {t_name}:*\n\n"
                                f"El tour *{t_name}* cuenta con **cupos limitados** y alta demanda para las próximas salidas.\n\n"
                                f"La disponibilidad de espacios se confirma en tiempo real según los cupos de operación del día.\n\n"
                                f"👉 Escribe: *asesor* indicando tu fecha tentativa y número de personas para reservar tu lugar a tiempo."
                            )
                        return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id=eid_comercial)

                    # Tours de cupos estrictos por el Estado (Camino Inca / Machu Picchu)
                    if eid_comercial == 'camino-inka':
                        if en:
                            msg = (
                                "📅 *Availability — Inca Trail (4D/3N):*\n\n"
                                "Inca Trail permits are strictly regulated by the Peruvian Government (SERNANP / Ministry of Culture), limited to **500 spots per day** (including guides and porters).\n\n"
                                "Spots sell out months in advance. We recommend checking availability for your tentative travel date right away.\n\n"
                                "👉 Write: *advisor* with your planned month and date to check official availability in real time."
                            )
                        elif pt:
                            msg = (
                                "📅 *Disponibilidade — Trilha Inca (4D/3N):*\n\n"
                                "As autorizações da Trilha Inca são rigorosamente controladas pelo Governo do Peru (SERNANP / Ministério da Cultura), limitadas a **500 vagas por dia** (incluindo guias e carregadores).\n\n"
                                "As vagas costumam esgotar com meses de antecedência. Recomendamos consultar com antecedência para sua data prevista.\n\n"
                                "👉 Escreva: *assessor* com seu mês e data pretendidos para verificar a disponibilidade oficial em tempo real."
                            )
                        else:
                            msg = (
                                "📅 *Disponibilidad — Camino Inca (4D/3N):*\n\n"
                                "Los permisos de Camino Inca son regulados estrictamente por el Estado peruano (SERNANP / Ministerio de Cultura), con un límite de **500 cupos diarios** (incluyendo guías y porteadores).\n\n"
                                "Los espacios suelen agotarse con semanas o meses de anticipación. Te recomendamos verificar disponibilidad con tu fecha tentativa a la brevedad.\n\n"
                                "👉 Escribe: *asesor* indicando tu mes o fecha estimada para consultar la disponibilidad oficial en tiempo real."
                            )
                        return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id='camino-inka')

                    if eid_comercial == 'machu-picchu-tren':
                        if en:
                            msg = (
                                "📅 *Availability — Machu Picchu by Train:*\n\n"
                                "Machu Picchu visits have daily shift capacity for citadel entrance circuits (Ministry of Culture) and train tickets (PeruRail / Inca Rail).\n\n"
                                "Departures run daily, but entrances sell out quickly during high season. Early booking is strongly advised.\n\n"
                                "👉 Write: *advisor* with your tentative date to secure tickets and train schedules."
                            )
                        elif pt:
                            msg = (
                                "📅 *Disponibilidade — Machu Picchu de Trem:*\n\n"
                                "As visitas a Machu Picchu possuem limites diários por turno para ingressos da cidadela (Ministério da Cultura) e bilhetes de trem (PeruRail / Inca Rail).\n\n"
                                "Há saídas diárias, mas as entradas esgotam rapidamente na alta temporada. Recomendamos reservar com antecedência.\n\n"
                                "👉 Escreva: *assessor* com sua data prevista para garantir ingressos e horários de trem."
                            )
                        else:
                            msg = (
                                "📅 *Disponibilidad — Machu Picchu en Tren:*\n\n"
                                "Las visitas a Machu Picchu cuentan con cupos por turno para el ingreso a la ciudadela (Ministerio de Cultura) y boletos de tren (PeruRail / Inca Rail).\n\n"
                                "Operamos salidas diarias durante todo el año, pero los boletos de ingreso se agotan con anticipación en temporada alta.\n\n"
                                "👉 Escribe: *asesor* con tu fecha tentativa para asegurar los turnos de ingreso y horarios de tren ideales."
                            )
                        return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id='machu-picchu-tren')

                    # Tours de operación diaria regular
                    if en:
                        msg = (
                            f"📅 *Availability — {t_name}:*\n\n"
                            f"We have **daily departures** all year round for this tour. Group spots are confirmed with 24 to 48 hours in advance to guarantee vehicle seats and professional guide.\n\n"
                            f"👉 Write: *advisor* with your travel date and group size to confirm your spots right away 😊"
                        )
                    elif pt:
                        msg = (
                            f"📅 *Disponibilidade — {t_name}:*\n\n"
                            f"Temos **saídas diárias** durante todo o ano para este passeio. As vagas de grupo são confirmadas com 24 a 48 horas de antecedência para garantir transporte e guia credenciado.\n\n"
                            f"👉 Escreva: *assessor* com sua data e número de pessoas para confirmar suas vagas na hora 😊"
                        )
                    else:
                        msg = (
                            f"📅 *Disponibilidad — {t_name}:*\n\n"
                            f"Contamos con **salidas diarias garantizadas** durante todo el año para este tour. Los cupos de grupo se coordinan con 24 a 48 horas de anticipación para asegurar transporte y guía oficial.\n\n"
                            f"👉 Escribe: *asesor* indicando tu fecha de viaje y número de personas para asegurar tus lugares al instante 😊"
                        )
                    return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id=eid_comercial)

                # 2.3 Consulta general de disponibilidad (sin tour específico identificado)
                if en:
                    msg = (
                        "📅 *Availability and Spots — Texeira Travel:*\n\n"
                        "Our tour departures operate as follows:\n"
                        "• 🚐 *Daily Tours (City Tour, Sacred Valley, Maras Moray, Rainbow Mountain, Humantay Lake):* Daily departures; bookings recommended 24 to 48 hours in advance.\n"
                        "• 🎟️ *Machu Picchu & Inca Trail:* High demand with strict Peruvian Government ticket quotas (Inca Trail closed in February for maintenance). Early booking required.\n\n"
                        "👉 Write: *advisor* with your planned date and destination to check immediate availability."
                    )
                elif pt:
                    msg = (
                        "📅 *Disponibilidade e Vagas — Texeira Travel:*\n\n"
                        "Nossos passeios operam da seguinte forma:\n"
                        "• 🚐 *Passeios Diários (City Tour, Vale Sagrado, Maras Moray, Montanha 7 Cores, Laguna Humantay):* Saídas diárias; recomendamos reservar com 24 a 48 horas de antecedência.\n"
                        "• 🎟️ *Machu Picchu e Trilha Inca:* Alta procura com limites diários do Governo do Peru (Trilha Inca fechada em fevereiro para manutenção). Reserva antecipada obrigatória.\n\n"
                        "👉 Escreva: *assessor* com sua data prevista e passeio de interesse para verificar a disponibilidade imediata."
                    )
                else:
                    msg = (
                        "📅 *Disponibilidad y Cupos — Texeira Travel:*\n\n"
                        "Nuestras salidas operan de la siguiente manera:\n"
                        "• 🚐 *Tours Diarios (City Tour, Valle Sagrado, Maras Moray, Montaña 7 Colores, Laguna Humantay):* Salidas diarias durante todo el año; recomendamos reservar con 24 a 48 horas de anticipación.\n"
                        "• 🎟️ *Machu Picchu y Camino Inca:* Cupos limitados por el Estado peruano (Camino Inca cerrado en febrero por mantenimiento). Requieren reserva con anticipación.\n\n"
                        "👉 Escribe: *asesor* indicando tu fecha tentativa y el tour que deseas para confirmarte disponibilidad inmediata."
                    )
                return finish(msg, 'evidence_availability', pending=True, sources=['CATALOGO_OFICIAL'], entity_id=None)

            # 3. Horario publicado comercial residual si no era consulta de disponibilidad
            if eid_comercial and eid_comercial in active_tours:
                tour_obj_com = active_tours.get(eid_comercial, {})
                name_com = tour_obj_com.get('name', eid_comercial)
                schedule_com = str(tour_obj_com.get('schedule') or '').strip()
                overrides_com = tour_obj_com.get('overridden_fields', [])
                if not schedule_com and 'schedule' not in overrides_com:
                    facts_com = get_facts(eid_comercial)
                    for f in facts_com:
                        if f.field == 'schedule' and f.value:
                            schedule_com = str(f.value).strip()
                            break
                if schedule_com:
                    if en:
                        msg = (f'⏰ *{name_com}*\n• Published schedule: {schedule_com}\n\nFor price and available dates, our team confirms them directly with you.\n\nWrite 👉 *advisor* and we\'ll assist you right away 😊')
                    else:
                        msg = (f'⏰ *{name_com}*\n• Horario publicado: {schedule_com}\n\nEl precio y las fechas disponibles te las confirmamos al instante en la agencia.\n\nEscribe 👉 *asesor* y te atendemos ahora 😊')
                    return finish(msg, 'evidence_schedule', pending=True, sources=['F1','F2'], entity_id=eid_comercial)

            if en:
                msg = 'Payments, bookings and availability are confirmed directly with our team at the agency.\n\nWrite 👉 *advisor* and we\'ll assist you right away 😊'
            elif pt:
                msg = 'Pagamentos, reservas e disponibilidade são coordenados diretamente com nossa equipe na agência. 📅\n\nEscreva 👉 *assessor* e te atendemos agora 😊'
            else:
                msg = 'Pagos, reservas y disponibilidad los coordinamos directamente en la agencia. 📅\n\nEscribe 👉 *asesor* y te atendemos ahora 😊'
            return finish(msg,'evidence_unknown',True,entity_id=None)
        if re.search(r'7d/6n|paquete.*7|7.day package',q):
            if en:
                msg = "The 7-day package is not documented in our current catalog.\n\nWrite 👉 *advisor* and we'll check what options are available for you 😊"
            else:
                msg = "El paquete de 7 días no está en nuestro catálogo actual. 📋\n\nEscribe 👉 *asesor* y revisamos qué opciones tenemos para ti 😊"
            return finish(msg,'evidence_unknown',True,entity_id=None)
        if re.search(r'contact|telefono|whatsapp|correo|email|direccion|ubicacion|oficina|office|donde\s+(?:queda|estan?|se\s+encuentran)|where\s+are\s+you',q):
            a=catalog['agency']
            if en:
                msg = f"📞 *Texeira Travel — Contact:*\n{phone}\n✉️ {', '.join(a['emails'])}\n📍 {a['address']}"
            else:
                msg = f"📞 *Texeira Travel — Contacto:*\n{phone}\n✉️ {', '.join(a['emails'])}\n📍 {a['address']}"
            return finish(msg,'evidence_contact',sources=['F1','F2','F3'])

        eid=entity(q)
        if not eid:
            for h in reversed(prior):
                if h.get('role') == 'human':
                    eid = entity(support.normalize(h['content']))
                    if eid: break

        # ---- MULTIMEDIA: FOTOS Y FOLLETOS PDF ----
        from src.visual.visual_engine import is_photo_requested, is_brochure_requested, get_tour_image_data, get_tour_brochure_data

        if is_photo_requested(question):
            if eid and (is_deactivated_tour(eid) or eid not in active_tours):
                tour_info = None
                try:
                    import catalog_service
                    tour_info = catalog_service.get_tour_by_id(eid)
                except Exception:
                    pass
                tour_name = tour_info.get('name', eid) if tour_info else eid
                msg = f"*{tour_name}* is not currently in our active catalog. You can explore other tours or consult this destination with an advisor." if en else f"*{tour_name}* no figura actualmente en nuestro catálogo activo. Puedes explorar otros tours o consultar este destino con un asesor."
                if pt:
                    msg = f"*{tour_name}* não está no catálogo ativo no momento. Você pode explorar outros passeios ou consultar um assessor."
                return finish(msg, 'evidence_inactive_tour', pending=True, sources=[], entity_id=eid)

            img_data = get_tour_image_data(question, user_msg=question, entity_id=eid or "")
            tour_obj = active_tours.get(eid) if eid else None
            tour_name = tour_obj['name'] if tour_obj else None
            if img_data:
                img_url, img_caption = img_data
                msg = f"Here is the official photo of *{tour_name or 'our tours with Texeira Travel'}*. 📸✨" if en else f"Te compartimos la fotografía oficial de *{tour_name or 'nuestros destinos con Texeira Travel'}*. 📸✨"
                if pt:
                    msg = f"Esta é a foto oficial de *{tour_name or 'nossos passeios com Texeira Travel'}*. 📸"
                return finish(msg, 'evidence_photo', sources=['ASSET_OFICIAL'], entity_id=eid)
            else:
                msg = f"Currently we don't have online photos for *{tour_name or 'this tour'}*, but our advisor will share our complete gallery with you." if en else f"Actualmente no disponemos de fotos en línea para *{tour_name or 'este tour'}*, pero nuestro asesor te compartirá nuestra galería completa."
                if pt:
                    msg = f"No momento não temos fotos online de *{tour_name or 'este passeio'}*. Você pode consultar a galeria com um assessor."
                return finish(msg, 'evidence_photo_unavailable', sources=['ASSET_OFICIAL'], entity_id=eid)

        if is_brochure_requested(question):
            if eid and (is_deactivated_tour(eid) or eid not in active_tours):
                tour_info = None
                try:
                    import catalog_service
                    tour_info = catalog_service.get_tour_by_id(eid)
                except Exception:
                    pass
                tour_name = tour_info.get('name', eid) if tour_info else eid
                msg = f"*{tour_name}* is not currently in our active catalog. You can explore other tours or consult this destination with an advisor." if en else f"*{tour_name}* no figura actualmente en nuestro catálogo activo. Puedes explorar otros tours o consultar este destino con un asesor."
                return finish(msg, 'evidence_inactive_tour', pending=True, sources=[], entity_id=eid)

            doc_data = get_tour_brochure_data(question, user_msg=question, entity_id=eid or "")
            tour_obj = active_tours.get(eid) if eid else None
            tour_name = tour_obj['name'] if tour_obj else None
            if doc_data:
                doc_url, doc_filename, doc_caption = doc_data
                msg = f"Sure! Here is the official PDF brochure for {tour_name or 'the tour'}. 📄✨" if en else f"¡Por supuesto! Te adjunto el folleto oficial en PDF de {tour_name or 'este tour'}. 📄✨"
                return finish(msg, 'evidence_brochure', sources=['ASSET_OFICIAL'], entity_id=eid)
            else:
                if eid and tour_name:
                    msg = f"Currently {tour_name} does not have an online PDF brochure, but our advisor will share the full itinerary with you." if en else f"Actualmente {tour_name} no cuenta con folleto en PDF en línea, pero nuestro asesor te facilitará el itinerario completo."
                else:
                    msg = "Which of our tours would you like to receive the PDF brochure or itinerary for?" if en else "¿De cuál de nuestros tours te gustaría recibir el folleto o itinerario en PDF?"
                return finish(msg, 'evidence_brochure', sources=['CATALOGO_OFICIAL'], entity_id=eid)

        # Consultas directas sobre un tour desactivado: no ofrecer como activo
        if eid and (is_deactivated_tour(eid) or eid not in active_tours):
            tour_info = None
            try:
                import catalog_service
                tour_info = catalog_service.get_tour_by_id(eid)
            except Exception:
                pass
            tour_name = tour_info.get('name', eid) if tour_info else eid
            if en:
                msg = f"*{tour_name}* is not currently in our active catalog (not available). You can explore other tours or consult this destination with an advisor."
            else:
                msg = f"*{tour_name}* no figura actualmente en nuestro catálogo activo (no se encuentra disponible). Puedes explorar otros tours o consultar este destino con un asesor."
            if pt:
                msg = f"*{tour_name}* não está no catálogo ativo no momento. Você pode explorar outros passeios ou consultar um assessor."
            return finish(msg, 'evidence_inactive_tour', pending=True, sources=[], entity_id=eid)

        # Si la consulta es una comparación entre tours o una pregunta interpretativa abierta,
        # no debe ser absorbida por reglas deterministas de un solo tour/campo para permitir el uso del RAG.
        is_comparison = is_tour_comparison(q)
        is_open_interpretive = is_open_tour_advice(q)
        if is_comparison or is_open_interpretive:
            eid = None
            fld = None
        else:
            fld = field(q)
        if eid == 'machu-picchu-tren' and re.search(r'dormir|pernoct|alojamiento|overnight|sleep|accommodation', q):
            detail = ('overnight accommodation is not documented for this train tour; hotel pickup does not mean a hotel stay is included' if en else 'el alojamiento o pernocte no está documentado para este tour en tren; el recojo del hotel no significa que incluya hospedaje')
            return unknown(detail, entity_id=eid)

        # Tour directo o ficha técnica (ej. "camino inka", "· Camino Inca Clásico 4D/3N", "información de camino inka")
        # Si la entidad se heredó del historial (no en q), solo activar ficha si pide explícitamente información general
        direct_eid = entity(q)
        overview_names = set(aliases.get(direct_eid, []))
        if direct_eid in active_tours:
            obj = active_tours[direct_eid]
            overview_names.update([obj.get('name', ''), *obj.get('aliases', [])])
        stripped_q = q.strip(' ?¿!.•*')
        query_words = re.findall(r'\b\w+\b', stripped_q)
        bare_name = any(stripped_q == support.normalize(name) for name in overview_names if name)
        if not bare_name and direct_eid:
            # Retain the existing uniquely identified one-edit tour-name UX;
            # extra question words are never accepted as a bare name.
            for name in overview_names:
                name_words = re.findall(r'\b\w+\b', support.normalize(name))
                if len(query_words) == len(name_words) >= 2 and sum(
                    _single_typo_cost(a, b) for a, b in zip(query_words, name_words)
                ) == 1:
                    bare_name = True
                    break
        wants_overview = bare_name or bool(re.search(
            r'\b(?:informaci[oó]n|information|info|detalles|ficha|overview|details|'
            r'saber\s+(?:de|del|sobre))\b', q, re.I))
        if len(support.requested_catalog_fields(q)) > 1:
            # A single-field answer would silently discard part of the query.
            fld = None
            wants_overview = False
        if eid and fld is None and wants_overview and lang in {'es', 'en'}:
            tour_obj = active_tours.get(eid, {})
            name = tour_obj.get('name', eid)
            official_price = str(tour_obj.get("official_price") or "").strip()
            currency = str(tour_obj.get("currency") or "USD")
            schedule = str(tour_obj.get("schedule") or "").strip()
            duration = str(tour_obj.get("duration") or "").strip()
            includes = str(tour_obj.get("includes") or "").strip()
            excludes = str(tour_obj.get("excludes") or "").strip()

            overrides_tour = tour_obj.get('overridden_fields', [])
            if not official_price or not schedule or not duration:
                facts = get_facts(eid)
                for f in facts:
                    if not official_price and f.field == 'official_price' and f.value:
                        official_price = str(f.value).strip()
                    if not schedule and f.field == 'schedule' and f.value and 'schedule' not in overrides_tour:
                        schedule = str(f.value).strip()
                    if not duration and f.field == 'duration' and f.value and 'duration' not in overrides_tour:
                        duration = str(f.value).strip()

            if not duration or not schedule:
                for cat in CAT_SPECS_DICT.values():
                    for t_eid, _, t_dur in cat.get('tours', []):
                        if t_eid == eid and t_dur:
                            if '|' in t_dur:
                                d_part, s_part = [p.strip() for p in t_dur.split('|', 1)]
                                if not duration and 'duration' not in overrides_tour:
                                    duration = d_part
                                if not schedule and 'schedule' not in overrides_tour:
                                    schedule = s_part
                            else:
                                if not duration and 'duration' not in overrides_tour:
                                    duration = t_dur

            if official_price or schedule or duration or includes:
                tour_emojis = {
                    'camino-inka': '🥾', 'salkantay-trek': '🥾', 'inka-jungle': '🥾', 'choquequirao': '🏕️',
                    'machu-picchu-tren': '🏔️', 'machu-picchu-car': '🏔️',
                    'city-tour-cusco': '🏛️', 'valle-sagrado': '🌾', 'montana-7-colores': '🌈',
                    'laguna-humantay': '💎', 'maras-moray': '🧂', 'maras-moray-cuatrimoto': '🏎️',
                    'waqra-pukara': '🏰', 'valle-sur': '🌄', 'puente-qeswachaca': '🌉',
                    'tour-mistico': '🔮', 'islas-titicaca': '⛵', 'canon-colca': '🦅', 'ruta-del-sol': '☀️'
                }
                icon = tour_emojis.get(eid, '📍')
                display_name = name
                if en:
                    from app import _get_tour_display_name
                    display_name = _get_tour_display_name(eid, is_en=True) or name
                lines = [f"{icon} *{display_name}*"]
                if duration:
                    lines.append(f"• Duración: {duration}" if not en else f"• Duration: {english_duration(duration)}")
                if schedule:
                    lines.append(f"• Horario: {schedule}" if not en else f"• Schedule: {schedule}")
                if official_price:
                    price_display = official_price if any(c in official_price for c in ['USD', 'PEN', '$', 'S/']) else f"{official_price} {currency}"
                    lines.append(f"• Tarifa oficial: *{price_display}* por persona" if not en else f"• Official rate: *{price_display}* per person")

                try:
                    from catalog_service import get_tour_rates
                    rates_ov = get_tour_rates(eid, active_only=True)
                    if rates_ov:
                        r_str = ", ".join(f"*{r['rate_name']}* ({r['price']} {r['currency']})" for r in rates_ov)
                        lines.append(f"• Tarifas especiales disponibles: {r_str}" if not en else f"• Special rates available: {r_str}")
                except Exception:
                    pass

                avail_status = tour_obj.get('availability', 'available')
                if avail_status == 'sold_out':
                    lines.append("• Estado: 🔴 Agotado / Sin cupos disponibles (consulta con asesor por posibles liberaciones)" if not en else "• Status: 🔴 Sold out / No spots available (contact advisor for possible releases)")
                elif avail_status == 'limited':
                    lines.append("• Disponibilidad: 🟡 Cupos limitados (se recomienda reservar con anticipación)" if not en else "• Availability: 🟡 Limited spots (advance booking recommended)")
                if 'camino-in' in eid:
                    lines.append("• Cupos: Regulados por el SERNANP (500 personas/día). Cierre anual en febrero." if not en else "• Quota: Regulated by SERNANP (500 people/day). Annual closure in February.")

                actions_hint = (
                    "\n_Puedes consultar qué incluye, ver fotos o solicitar reserva con las opciones de abajo o escribiendo tu consulta._"
                    if not en else
                    "\n_You can check what's included, view photos, or request a reservation using the options below or typing your question._"
                )
                return finish("\n".join(lines) + actions_hint, 'evidence_tour_overview', sources=['CATALOGO_OFICIAL'], entity_id=eid)

        if eid and fld and lang in {'es','en'}:
            tour_obj = active_tours.get(eid, {})
            name = tour_obj.get('name', eid)
            facts = get_facts(eid)
            # Las ediciones explícitas del panel son la fuente vigente para
            # estos campos; no mezclar inclusiones antiguas con las actuales.
            dynamic_value = str(tour_obj.get(fld) or '').strip()
            overrides = tour_obj.get('overridden_fields', [])
            if fld in overrides and not dynamic_value and fld in {'schedule', 'duration', 'includes', 'excludes'}:
                return unknown(fld, entity_id=eid)
            if dynamic_value and fld in overrides and fld in {'schedule', 'duration', 'includes', 'excludes'}:
                label = ({'schedule': 'Horario', 'duration': 'Duración', 'includes': 'Incluye', 'excludes': 'No incluye'}
                         if not en else {'schedule': 'Schedule', 'duration': 'Duration', 'includes': 'Includes', 'excludes': 'Does not include'})[fld]
                if fld == 'duration' and en:
                    dynamic_value = english_duration(dynamic_value)
                if fld in {'includes', 'excludes'} and any(sep in dynamic_value for sep in [',', ';', '\n']):
                    items = [it.strip().lstrip('•-* ') for it in re.split(r'[,;\n]+', dynamic_value) if it.strip()]
                    formatted_val = ":\n" + "\n".join(f"• {it}" for it in items)
                else:
                    formatted_val = f": {dynamic_value}"
                text = f"*{name}*\n{label}{formatted_val}"
                if fld in {'includes', 'excludes'}:
                    other = 'excludes' if fld == 'includes' else 'includes'
                    other_value = str(tour_obj.get(other) or '').strip()
                    if other_value:
                        other_label = ('No incluye' if other == 'excludes' else 'Incluye') if not en else ('Does not include' if other == 'excludes' else 'Includes')
                        if any(sep in other_value for sep in [',', ';', '\n']):
                            o_items = [it.strip().lstrip('•-* ') for it in re.split(r'[,;\n]+', other_value) if it.strip()]
                            formatted_other = ":\n" + "\n".join(f"• {it}" for it in o_items)
                        else:
                            formatted_other = f": {other_value}"
                        text += f"\n\n{other_label}{formatted_other}"
                return finish(text, f'evidence_{fld}', sources=['CATALOGO_OFICIAL'], entity_id=eid)
            relevant=detect_conflicts(eid, fld)
            if relevant:
                if en:
                    msg = f"ℹ️ We have different details for *{name}* in our records.\n\nWrite 👉 *advisor* to get the latest confirmed info 😊"
                else:
                    msg = f"ℹ️ Tenemos datos que necesitan verificación para *{name}*.\n\nEscribe 👉 *asesor* y te confirmamos el dato actualizado 😊"
                return finish(msg,'evidence_conflict',True,[f.source_id for f in facts],True,entity_id=eid)
            if fld=='price':
                official_price = str(tour_obj.get("official_price") or "").strip()
                currency = str(tour_obj.get("currency") or "USD")
                if not official_price:
                    for f in facts:
                        if f.field == 'official_price' and f.value:
                            official_price = str(f.value).strip()
                            break
                if official_price:
                    price_display = official_price if any(c in official_price for c in ['USD', 'PEN', '$', 'S/']) else f"{official_price} {currency}"
                    special_hint = ""
                    try:
                        from catalog_service import get_tour_rates
                        rates_pr = get_tour_rates(eid, active_only=True)
                        if rates_pr:
                            names_str = ", ".join(f"*{r['rate_name']}* ({r['price']} {r['currency']})" for r in rates_pr)
                            special_hint = f"\n💡 Tarifas especiales disponibles: {names_str}." if not en else f"\n💡 Special rates available: {names_str}."
                    except Exception:
                        pass
                    if en:
                        msg = f"💰 *{name}*\nOfficial rate: *{price_display}* per person{special_hint}\n\nWrite 👉 *advisor* to book or ask about dates 😊"
                    else:
                        msg = f"💰 *{name}*\nTarifa oficial: *{price_display}* por persona{special_hint}\n\nEscribe 👉 *asesor* para reservar o consultar fechas 😊"
                    return finish(msg, 'evidence_confirmed_price', sources=['CATALOGO_OFICIAL'], entity_id=eid)

                if en:
                    msg = f"💬 The price for *{name}* is confirmed directly with our team.\n\nWrite 👉 *advisor* and we'll tell you right away 😊"
                else:
                    msg = f"💬 El precio de *{name}* lo confirmamos contigo al instante.\n\nEscribe 👉 *asesor* y te respondemos ahora 😊"
                return finish(msg,'evidence_unknown',True,entity_id=eid)
            if fld=='product':
                if en:
                    msg = f"✅ *{name}* is a confirmed tour with Texeira Travel.\n\nWant photos, prices or the itinerary? Just ask!\nOr write 👉 *advisor* to book 😊"
                else:
                    msg = f"✅ *{name}* es un tour confirmado con Texeira Travel.\n\n¿Quieres fotos, precio o itinerario? ¡Pregúntame!\nO escribe 👉 *asesor* para reservar 😊"
                return finish(msg,'evidence_product',sources=[f.source_id for f in facts if f.field=='confirmed_product'],entity_id=eid)
            selected=[f for f in facts if f.field==fld and f.value is not False]
            targets={'caballo|horse':'caballo','seguro|insurance':'seguro','entrada|ticket|boleto':'entrada|ingreso|boleto','oxigen|oxygen':'oxigeno','bus':'bus','desayuno|breakfast':'desayuno','almuerzo|lunch':'almuerzo'}
            if fld in {'includes','excludes'}:
                for pattern,item in targets.items():
                    if re.search(pattern,q):
                        selected=[f for f in facts if f.field in {'includes','excludes'} and f.item and re.search(item,f.item)]
                        if not selected:
                            subj = f'whether the requested service is included in {name}' if en else f'si el servicio solicitado esta incluido en {name}'
                            return unknown(subj, entity_id=eid)
                        break
            if not selected:
                dyn_val = str(tour_obj.get(fld) or "").strip()
                if dyn_val:
                    emojis = {'includes': '✅', 'excludes': '🚫', 'stops': '📍', 'schedule': '🕐', 'duration': '⏱️'}
                    labels_es = {'includes':'Incluye','excludes':'No incluye','stops':'Visita','schedule':'Horario','duration':'Duración'}
                    labels_en = {'includes':'Includes','excludes':'Does not include','stops':'Visits','schedule':'Schedule','duration':'Duration'}
                    emoji = emojis.get(fld, 'ℹ️')
                    label = (labels_en if en else labels_es).get(fld, fld.capitalize())
                    if fld in {'includes', 'excludes'} and any(sep in dyn_val for sep in [',', ';', '\n']):
                        items = [it.strip().lstrip('•-* ') for it in re.split(r'[,;\n]+', dyn_val) if it.strip()]
                        formatted_dyn = ":\n" + "\n".join(f"• {it}" for it in items)
                        body_str = f"{label}{formatted_dyn}"
                    else:
                        body_str = f"{label}: {dyn_val}"
                    if en:
                        msg = f"{emoji} *{name}*\n{body_str}\n\nWrite 👉 *advisor* for more details or to book 😊"
                    else:
                        msg = f"{emoji} *{name}*\n{body_str}\n\nEscribe 👉 *asesor* para más detalles o reservar 😊"
                    return finish(msg, f'evidence_{fld}', sources=['CATALOGO_OFICIAL'], entity_id=eid)
                if en:
                    msg = f"💬 That detail for *{name}* is confirmed directly with our team.\n\nWrite 👉 *advisor* and we'll help you 😊"
                else:
                    msg = f"💬 Ese detalle de *{name}* lo confirmamos contigo directamente.\n\nEscribe 👉 *asesor* y te ayudamos 😊"
                return finish(msg,'evidence_unknown',True,entity_id=eid)
            lines=[]
            labels={'includes':('Includes' if en else 'Incluye'),'excludes':('Does not include' if en else 'No incluye'),'stops':('Visits' if en else 'Visita'),'schedule':('Published schedule' if en else 'Horario publicado'),'duration':('Published duration' if en else 'Duracion publicada')}
            # Agrupar equivalencias solo en la presentación de este producto.
            # Mantener todas las fuentes y no inferir ida/vuelta de un ticket aislado.
            if en:
                mp_labels={
                    'traslado_cusco_ollanta_cusco':'Transfer Cusco–Ollanta–Cusco',
                    'tren_ida_vuelta':'Round-trip train',
                    'tickets_tren':'Train tickets',
                    'bus_subida_bajada':'Bus up and down',
                    'ingresos_machu_picchu':'Machu Picchu entrance ticket',
                    'entradas_ciudadela':'Machu Picchu entrance ticket',
                    'guia_profesional':'Professional guide',
                    'recojo_hotel':'Hotel pickup',
                }
            else:
                mp_labels={
                    'traslado_cusco_ollanta_cusco':'Traslado Cusco–Ollanta–Cusco',
                    'tren_ida_vuelta':'Tren de ida y vuelta',
                    'tickets_tren':'Tickets de tren',
                    'bus_subida_bajada':'Bus de subida y bajada',
                    'ingresos_machu_picchu':'Entrada a Machu Picchu',
                    'entradas_ciudadela':'Entrada a Machu Picchu',
                    'guia_profesional':'Guía profesional',
                    'recojo_hotel':'Recojo del hotel',
                }
            selected_items={(f.field,f.item) for f in selected}
            for f in selected:
                val=f.item.replace('_',' ') if f.item else str(f.value)
                if eid=='machu-picchu-tren' and f.field in {'includes','excludes'}:
                    if f.item=='tickets_tren' and (f.field,'tren_ida_vuelta') in selected_items:
                        continue
                    val=mp_labels.get(f.item,val)
                elif f.field=='duration' and en:
                    val=english_duration(val)
                elif en and f.item:
                    val=EN_ITEMS.get(f.item,val)
                label=labels.get(f.field,'Published' if en else 'Publicado')
                line=f'{label}: {val}'
                if line not in lines:lines.append(line)
            tour_title = ('Machu Picchu by Train' if eid=='machu-picchu-tren' else name) if en else name
            t_obj_sub = active_tours.get(eid, {})
            avail_sub = t_obj_sub.get('availability', 'available')
            if avail_sub == 'sold_out':
                lines.append('Estado: 🔴 Agotado / Sin cupos disponibles' if not en else 'Status: 🔴 Sold out / No spots available')
            elif avail_sub == 'limited':
                lines.append('Disponibilidad: 🟡 Cupos limitados' if not en else 'Availability: 🟡 Limited spots')
            emojis = {'includes': '✅', 'excludes': '🚫', 'stops': '📍', 'schedule': '🕐', 'duration': '⏱️'}
            emoji = emojis.get(fld, 'ℹ️')
            header = f"{emoji} *{tour_title}*"
            body = '\n'.join(f'• {l}' for l in lines)
            if en:
                footer = '\n\nWrite 👉 *advisor* for bookings or more info 😊'
            else:
                footer = '\n\nEscribe 👉 *asesor* para reservar o más información 😊'
            return finish(f"{header}\n{body}{footer}",'evidence_'+fld,sources=[f.source_id for f in selected],entity_id=eid)
        # Para otras consultas se conserva el RAG y su proveedor, sin la segunda capa de evidencia.
        with ns.get('suspend_recording', nullcontext)():
            result=original(question,user_id)
        # La ausencia explícita de evidencia no equivale a resolución autónoma.
        answer_norm = support.normalize(result.get('response', ''))
        if re.search(r'cannot confirm|can.t confirm|does not contain.*information|no incluye el nombre|no especifica|no (?:puedo|podemos) confirmar|no (?:esta|estan) documentad|nao (?:posso|podemos) confirmar|nao (?:esta|estao) documentad|nao ha (?:dados|informacoes)', answer_norm):
            result['needs_agency_confirmation'] = True
            result['needs_confirmation'] = True
            result['resolved_autonomously'] = False
        record(user_id, question, result['response'])
        result.setdefault('language', lang)
        result['is_escalation']=False
        if result.get('is_rate_limit') or result.get('is_fallback'):result['resolved_autonomously']=False
        return result
    ns['rag_chain']=chain

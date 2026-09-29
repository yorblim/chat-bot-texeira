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

CAT_SPECS_DICT = {
    'treks': {
        'key': 'treks',
        'title_es': '🏔️ *Machu Picchu y Treks*',
        'title_en': '🏔️ *Machu Picchu & Treks*',
        'btn_id': 'btn_cat:treks',
        'btn_title_es': '🏔️ Machu Picchu',
        'btn_title_en': '🏔️ Machu Picchu',
        'tours': [
            ('machu-picchu-tren', 'Machu Picchu en Tren', '1 día | 04:00-20:30'),
            ('camino-inka', 'Camino Inca Clásico', '4 días / 3 noches'),
            ('machu-picchu-car', 'Machu Picchu by Car', '2 días / 1 noche'),
            ('salkantay-trek', 'Salkantay Trek', '4 días / 3 noches'),
            ('inka-jungle', 'Inka Jungle to Machu Picchu', '4 días / 3 noches'),
            ('choquequirao', 'Choquequirao Trek', '4 días / 3 noches'),
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
            ('montana-7-colores', 'Montaña de 7 Colores', 'Full Day | 04:00-18:30'),
            ('laguna-humantay', 'Laguna Humantay', 'Full Day | 04:30-18:00'),
            ('city-tour-cusco', 'City Tour Cusco', 'Medio día | 13:00-18:30'),
            ('valle-sagrado', 'Valle Sagrado', 'Full Day | 07:00-18:30'),
            ('maras-moray', 'Maras - Moray', 'Medio día | 08:00-14:30'),
            ('waqra-pukara', 'Waqra Pukara', 'Full Day | 04:00-19:00'),
            ('valle-sur', 'Valle Sur', 'Medio día | 08:30-14:00'),
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
            ('ruta-del-sol', 'Ruta del Sol Cusco-Puno', 'Día completo | 06:40-17:30'),
            ('islas-titicaca', 'Islas del Lago Titicaca', 'Full Day'),
            ('canon-colca', 'Cañón del Colca / Baños Termales de Chacapi', '2 días / 1 noche'),
        ]
    }
}
CAT_SPECS = list(CAT_SPECS_DICT.values())


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
                    dur = t_data.get('duration', b_dur) or b_dur
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
                res[dt['entity_id']] = {
                    'entity_id': dt['entity_id'],
                    'name': dt['name'],
                    'confirmed_product': True,
                    'official_price': dt.get('official_price', ''),
                    'currency': dt.get('currency', 'USD'),
                    'schedule': dt.get('schedule', ''),
                    'duration': dt.get('duration', ''),
                    'includes': dt.get('includes', ''),
                    'excludes': dt.get('excludes', ''),
                    'photo_filename': dt.get('photo_filename', ''),
                    'brochure_filename': dt.get('brochure_filename', ''),
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
        if re.search(r'cuatrimotos?|\batv\b|quad bike',q) and re.search(r'maras|moray|tour cuatrimoto',q):
            return 'maras-moray-cuatrimoto'
        try:
            from catalog_service import get_active_entity_keywords
            active_kw = get_active_entity_keywords()
            hits = []
            for eid, kws in active_kw.items():
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
        return max(hits)[1] if hits else None
    def field(q):
        for key,pattern in [
            ('excludes',r'no incluye|no esta incluido|exclu|not include'),
            ('includes',r'inclu|include'),
            ('price',r'precio|cuesta|cuanto cuesta|costo|costos|tarifa|tarifas|rate|rates|soles|\bpen\b|price|prices|cost|costs|how much'),
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
    def record(user_id, question, response):
        if 'add_history_turn' in ns:
            ns['add_history_turn'](user_id, question, response)
        else:
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', response)

    def chain(question,user_id='default'):
        q=support.normalize(question); lang=ns['detect_language'](question); en=lang=='en'
        prior=list(ns['get_history'](user_id))
        phone=' / '.join(catalog['agency']['phones'])
        active_tours, is_read_error, is_empty = get_current_tours_status()

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

        def finish(text,route, pending=False, sources=(), conflict=False, predefined=True, entity_id=None):
            record(user_id, question, text)
            return dict(response=text,context_used=bool(sources),is_predefined=predefined,is_fallback=False,
                resolved_autonomously=not pending,is_escalation=False,needs_agency_confirmation=pending,
                needs_confirmation=pending,conflict_detected=conflict,evidence_status='conflict' if conflict else ('unknown' if pending else 'documented'),
                sources_used=sorted(set(sources)),route=route,response_route=route,entity_id=entity_id)
        def unknown(subject, entity_id=None):
            if en:
                msg = f"That information is confirmed directly at the agency.\n\nWrite 👉 *advisor* and we'll help you right away 😊"
                return finish(msg,'evidence_unknown',True,entity_id=entity_id)
            msg = f"Ese dato lo confirmamos directamente en la agencia. 💬\n\nEscribe 👉 *asesor* y te ayudamos ahora mismo 😊"
            return finish(msg,'evidence_unknown',True,entity_id=entity_id)

        # 1. Fallo técnico al consultar la base de datos: no afirmar que tours fueron desactivados
        if is_read_error:
            msg = (
                "Tuvimos un inconveniente técnico temporal al consultar el catálogo. Puedes comunicarte directamente con un asesor o intentar nuevamente en unos instantes."
                if not en else
                "We encountered a temporary technical issue accessing the catalog. You can contact an advisor directly or try again in a moment."
            )
            return finish(msg, 'evidence_catalog_error', pending=True)

        # 2. Catálogo vacío confirmado (lectura exitosa pero 0 tours activos)
        if is_empty:
            msg = (
                "Actualmente no disponemos de tours activos en nuestro catálogo. Puedes consultar opciones personalizadas con un asesor."
                if not en else
                "Currently there are no active tours available in our catalog. You can check custom options with an advisor."
            )
            return finish(msg, 'evidence_catalog_empty', pending=True)

        # 3. Detección de referencias ambiguas ("el otro", "del otro", "the other", etc.)
        is_ambiguous_ref = bool(re.search(
            r'\b((?:d?el|de la)\s+otr[oa]s?|el demas|los demas|otro tour|otra opcion|the other( one)?|the second( one)?)\b',
            q
        ))
        if is_ambiguous_ref and not support.detect_entity_from_question(q):
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
                return finish(msg, 'evidence_ambiguous', pending=True, sources=[], entity_id=f"{recent_eids[0]},{recent_eids[1]}")

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
            'show me all options', 'list of tours'
        }
        # ---- CATÁLOGO NAVEGABLE POR CATEGORÍAS (DINÁMICO) ----
        CAT_SPECS = get_dynamic_cat_specs(active_tours)

        # 1. Petición de categoría específica (ej. "categoria treks", "category treks", "categoria cusco", etc.)
        is_cat_treks = bool(re.search(r'\b(categor[iy]a?\s+treks?|categor[iy]a?\s+machu|categor[iy]a?\s+1|treks?\s+y\s+machu|treks?\s+and\s+machu)\b', q))
        is_cat_cusco = bool(re.search(r'\b(categor[iy]a?\s+cusco|categor[iy]a?\s+monta[nñ]as|categor[iy]a?\s+mountains|categor[iy]a?\s+2|clasicos\s+cusco|cusco\s+classics)\b', q))
        is_cat_reg = bool(re.search(r'\b(categor[iy]a?\s+reg\w*|categor[iy]a?\s+rutas|categor[iy]a?\s+routes|categor[iy]a?\s+3|rutas\s+regionales|regional\s+routes)\b', q))
        selected_cat_key = None
        if is_cat_treks: selected_cat_key = 'treks'
        elif is_cat_cusco: selected_cat_key = 'cusco'
        elif is_cat_reg: selected_cat_key = 'reg'

        if selected_cat_key:
            cat_data = CAT_SPECS.get(selected_cat_key, {})
            active_in_cat = [
                (eid, default_label, default_dur)
                for eid, default_label, default_dur in cat_data.get('tours', [])
                if eid in active_tours and is_product_confirmed(eid)
            ]
            if not active_in_cat:
                cat_name = cat_data.get('title_es', selected_cat_key) if not en else cat_data.get('title_en', selected_cat_key)
                msg = (f"Actualmente no hay tours disponibles en la categoría {cat_name}. 📋\n\nPuedes explorar otras categorías o comunicarte con un asesor 😊"
                       if not en else
                       f"Currently there are no tours available in the category {cat_name}. 📋\n\nYou can explore other categories or contact an advisor 😊")
                return finish(msg, 'evidence_category_empty', sources=['CATALOGO_OFICIAL'], entity_id=f"cat_{selected_cat_key}")

            cat_title = cat_data.get('title_es', '') if not en else cat_data.get('title_en', '')
            lines = [f"{cat_title} disponibles:\n" if not en else f"{cat_title} available:\n"]
            for eid, default_label, default_dur in active_in_cat:
                t_obj = active_tours[eid]
                if en:
                    from app import _get_tour_display_name
                    tour_name = _get_tour_display_name(eid, is_en=True) or default_label
                else:
                    tour_name = t_obj.get('name', default_label)
                dur = english_duration(t_obj.get('duration') or default_dur) if en else (t_obj.get('duration') or default_dur)
                lines.append(f"• *{tour_name}* ({dur})")

            footer = ("\n_Escribe directamente el nombre de cualquier tour para ver detalles completos, o selecciona una opción abajo:_\nEscribe 👉 *asesor* si necesitas ayuda personalizada 😊"
                      if not en else
                      "\n_Type the name of any tour for full details, or select an option below:_\nWrite 👉 *advisor* for personalized help 😊")
            lines.append(footer)
            return finish("\n".join(lines), 'evidence_category_tours', sources=['CATALOGO_OFICIAL'], entity_id=f"cat_{selected_cat_key}")

        # 2. Petición de catálogo general (Ver Tours / Categorías)
        is_listing_request = (
            q.strip(' ?¿!.') in listing_keywords or
            bool(re.search(r'\b(muestr\w*|meustr\w*|mostr\w*|ver|view|show|dime|tell\s+me|cuales|which|what|tienen?|do\s+you\s+have|hay)\b.*?\b(tours?|opciones?|options?|paquetes?|packages?|destinos?|destinations?|viajes?|trips?|rutas?|routes?|circuitos?|paseos?|categorias?|categories)\b', q) and
                  not re.search(r'\b(precio|precios|cuesta|cuanto|costo|costos|tarifa|tarifas|price|prices|cost|costs|rate|rates|soles|dolares|\busd\b|\bpen\b|horario|hora|duracion|duration|schedule|incluye|includes?|itinerario|itinerary|fotos?|photos?|imagen|image|imagenes|images|brochure|folleto|cancel|reembols|refund|yape|paypal|pagar|pay|pago|payment|adelant|deposit|descuento|discount|reserva|book|booking|cupos?|manana|tomorrow|7d|7\s*d[ií]as?|7.day)\b|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}', q) and
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

        rate_cat = detect_rate_category(q)
        if re.search(r'\b(segur\w*|safe\w*|wheelchair|silla de ruedas|embaraz\w*|pregnan\w*)\b', q):
            return unknown('condiciones de seguridad o accesibilidad', entity_id=entity(q))
        rate_question = (field(q) == 'price' or
                         re.search(r'\b(tarifa\w*|descuent\w*|promo\w*|discount\w*|rate\w*)\b', q) or
                         re.fullmatch(r'(y |and )?(para |for )?(los |las )?(estudiantes?|students?|ninos?|children|kids)\??', q))
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

        # Operaciones comerciales y disponibilidad para fechas puntuales
        if re.search(r'cancel|reembols|refund|yape|paypal|\bpagar\b|\bpago\b|adelant|deposit|\bpay\b|payment|descuento|discount|reserva|booking|\bbook\b|cupos?|spots?|availability|available|disponib|manana|tomorrow|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}',q):
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

                tour_obj_com = active_tours.get(eid_comercial, {})
                name_com = tour_obj_com.get('name', eid_comercial)
                schedule_com = str(tour_obj_com.get('schedule') or '').strip()
                if not schedule_com:
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
            else:
                msg = 'Pagos, reservas y disponibilidad los coordinamos directamente en la agencia. 📅\n\nEscribe 👉 *asesor* y te atendemos ahora 😊'
            return finish(msg,'evidence_unknown',True,entity_id=None)
        if re.search(r'7d/6n|paquete.*7|7.day package',q):
            if en:
                msg = "The 7-day package is not documented in our current catalog.\n\nWrite 👉 *advisor* and we'll check what options are available for you 😊"
            else:
                msg = "El paquete de 7 días no está en nuestro catálogo actual. 📋\n\nEscribe 👉 *asesor* y revisamos qué opciones tenemos para ti 😊"
            return finish(msg,'evidence_unknown',True,entity_id=None)
        if re.search(r'contact|telefono|whatsapp|correo|email|direccion|ubicacion',q):
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
                return finish(msg, 'evidence_inactive_tour', pending=True, sources=[], entity_id=eid)

            img_data = get_tour_image_data(question, user_msg=question, entity_id=eid or "")
            tour_obj = active_tours.get(eid) if eid else None
            tour_name = tour_obj['name'] if tour_obj else None
            if img_data:
                img_url, img_caption = img_data
                msg = f"Here is the official photo of *{tour_name or 'our tours with Texeira Travel'}*. 📸✨" if en else f"Te compartimos la fotografía oficial de *{tour_name or 'nuestros destinos con Texeira Travel'}*. 📸✨"
                return finish(msg, 'evidence_photo', sources=['ASSET_OFICIAL'], entity_id=eid)
            else:
                msg = f"Currently we don't have online photos for *{tour_name or 'this tour'}*, but our advisor will share our complete gallery with you." if en else f"Actualmente no disponemos de fotos en línea para *{tour_name or 'este tour'}*, pero nuestro asesor te compartirá nuestra galería completa."
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
                msg = f"*{tour_name}* is not currently in our active catalog. You can explore other tours or consult this destination with an advisor."
            else:
                msg = f"*{tour_name}* no figura actualmente en nuestro catálogo activo. Puedes explorar otros tours o consultar este destino con un asesor."
            return finish(msg, 'evidence_inactive_tour', pending=True, sources=[], entity_id=eid)

        fld=field(q)
        if eid == 'machu-picchu-tren' and re.search(r'dormir|pernoct|alojamiento|overnight|sleep|accommodation', q):
            detail = ('overnight accommodation is not documented for this train tour; hotel pickup does not mean a hotel stay is included' if en else 'el alojamiento o pernocte no está documentado para este tour en tren; el recojo del hotel no significa que incluya hospedaje')
            return unknown(detail, entity_id=eid)

        # Tour directo o ficha técnica (ej. "camino inka", "· Camino Inca Clásico 4D/3N")
        if eid and fld is None and lang in {'es', 'en'}:
            tour_obj = active_tours.get(eid, {})
            name = tour_obj.get('name', eid)
            official_price = str(tour_obj.get("official_price") or "").strip()
            currency = str(tour_obj.get("currency") or "USD")
            schedule = str(tour_obj.get("schedule") or "").strip()
            duration = str(tour_obj.get("duration") or "").strip()
            includes = str(tour_obj.get("includes") or "").strip()
            excludes = str(tour_obj.get("excludes") or "").strip()

            if not official_price or not schedule or not duration:
                facts = get_facts(eid)
                for f in facts:
                    if not official_price and f.field == 'official_price' and f.value:
                        official_price = str(f.value).strip()
                    if not schedule and f.field == 'schedule' and f.value:
                        schedule = str(f.value).strip()
                    if not duration and f.field == 'duration' and f.value:
                        duration = str(f.value).strip()

            if not duration or not schedule:
                for cat in CAT_SPECS_DICT.values():
                    for t_eid, _, t_dur in cat.get('tours', []):
                        if t_eid == eid and t_dur:
                            if '|' in t_dur:
                                d_part, s_part = [p.strip() for p in t_dur.split('|', 1)]
                                if not duration:
                                    duration = d_part
                                if not schedule:
                                    schedule = s_part
                            else:
                                if not duration:
                                    duration = t_dur
                            break

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
        if re.search(r'cannot confirm|can.t confirm|does not contain.*information|no incluye el nombre|no especifica|no (?:puedo|podemos) confirmar|no (?:esta|estan) documentad', answer_norm):
            result['needs_agency_confirmation'] = True
            result['needs_confirmation'] = True
            result['resolved_autonomously'] = False
        record(user_id, question, result['response'])
        result['is_escalation']=False
        if result.get('is_rate_limit') or result.get('is_fallback'):result['resolved_autonomously']=False
        return result
    ns['rag_chain']=chain

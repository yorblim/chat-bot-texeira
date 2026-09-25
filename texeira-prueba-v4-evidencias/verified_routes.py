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
    # Traducir el texto, sin sustituir la cantidad ni inferir noches.
    return (value.replace('días','days').replace('dias','days').replace('horas','hours')
            .replace('itinerario publicado','published itinerary')
            .replace('confirmar variante y noches','confirm variant and nights'))

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

_SOCIAL_RESPONSES = {
    'hola': '¡Hola! 👋 Bienvenido a *Texeira Travel*. ¿En qué te puedo ayudar hoy?',
    'buenos dias': '¡Buenos días! ☀️ Bienvenido a *Texeira Travel*. ¿En qué te puedo ayudar?',
    'buenas tardes': '¡Buenas tardes! 🌤️ Bienvenido a *Texeira Travel*. ¿En qué te puedo ayudar?',
    'buenas noches': '¡Buenas noches! 🌙 Bienvenido a *Texeira Travel*. ¿En qué te puedo ayudar?',
    'hello': 'Hello! 👋 Welcome to *Texeira Travel*. How can I help you today?',
    'hi': 'Hi! 👋 Welcome to *Texeira Travel*. How can I help you?',
    'buenas': '¡Buenas! 👋 Bienvenido a *Texeira Travel*. ¿En qué te puedo ayudar?',
    'gracias': '¡Con gusto! 😊 Si necesitas algo más, aquí estamos.',
    'thanks': "You're welcome! 😊 Feel free to ask anything else.",
    'adios': '¡Hasta pronto! 🙌 Que disfrutes tu visita a Cusco.',
    'bye': 'Goodbye! 🙌 Enjoy your trip to Cusco!',
    'saludo': '¡Hola! 👋 Bienvenido a *Texeira Travel*. ¿En qué te puedo ayudar?',
}

_HELP_RESPONSE = '¡Claro! 😊 Puedo ayudarte con *tours, horarios y servicios* de Texeira Travel.\n¿Qué destino te interesa? O escribe 👉 *asesor*'

def install(ns, support, original):
    catalog = support.CATALOG

    def get_current_tours():
        try:
            from catalog_service import get_all_tours
            dynamic_active = get_all_tours(active_only=True)
            dynamic_all = get_all_tours(active_only=False)
            if dynamic_all:
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
                    }
                return res
        except Exception:
            pass
        return {t['entity_id']: dict(t) for t in catalog['tours']}

    def is_deactivated_tour(eid: str) -> bool:
        if not eid:
            return False
        try:
            from catalog_service import get_tour_by_id
            t = get_tour_by_id(eid)
            if t is not None:
                return not bool(t.get("is_active", 1))
        except Exception:
            pass
        return False

    tours = get_current_tours()
    aliases = {eid:[support.normalize(t['name'])] for eid,t in tours.items()}
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
            hits = [(len(k), eid) for eid, kws in active_kw.items() for k in kws if k in q]
            if hits:
                return max(hits)[1]
        except Exception:
            pass
        hits=[(len(a),eid) for eid,aa in aliases.items() for a in aa if a in q]
        return max(hits)[1] if hits else None
    def field(q):
        for key,pattern in [
            ('excludes',r'no incluye|no esta incluido|exclu|not include'),
            ('includes',r'inclu|include'),
            ('price',r'precio|cuesta|cuanto cuesta|costo|costos|tarifa|tarifas|soles|\bpen\b|price|prices|cost|costs|how much'),
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
        active_tours = get_current_tours()

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

        # Catálogo de tours solicitados (antes de evaluar fechas o disponibilidad comercial)
        listing_keywords = {
            'tour', 'tours', 'opcion', 'opciones', 'paquetes', 'catalogo',
            'que tours tienen', 'que tours ofrecen', 'que tours hay', 'lista de tours',
            'cuales tours tienen', 'cuales son los tours', 'todos los tours',
            'que opciones tienen', 'que opciones hay', 'todas las opciones',
            'what tours do you offer', 'what tours do you have', 'all tours',
            'show me all options', 'list of tours'
        }
        is_listing_request = (
            q.strip(' ?¿!.') in listing_keywords or
            # Peticiones tipo "me muestras todas las opciones", "muéstrame los tours", "qué opciones tienes", "ver tours", etc.
            bool(re.search(r'\b(muestr\w*|meustr\w*|mostr\w*|ver|dime|cuales|que|tienen?|hay)\b.*?\b(tours?|opciones?|paquetes?|destinos?|viajes?|rutas?|circuitos?|paseos?)\b', q) and
                 not re.search(r'\b(precio|precios|cuesta|cuanto|costo|costos|tarifa|tarifas|soles|dolares|\busd\b|\bpen\b|horario|hora|duracion|incluye|itinerario|fotos?|imagen|imagenes|brochure|folleto|cancel|reembols|yape|paypal|pagar|pago|adelant|deposit|descuento|reserva|booking|cupos?|manana|tomorrow|7d|7\s*d[ií]as?|7.day)\b|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}', q) and
                 support.detect_entity_from_question(q) is None) or
            # Preguntas sobre si es el único o si hay más opciones, u otros lugares/destinos
            bool(re.search(r'\b(es el unic\w|es la unic\w|es lo unic\w|hay mas|tienen mas|otros? tours?|otras? opciones?|otros? lugares?|otros? destinos?|otros? paquetes?|que m[aá]s tienen|que mas tienen|mas opciones|m[aá]s opciones|other tours?|other options?|more tours?|more options?|anything else)\b', q) and
                 not re.search(r'\b(cancel|reembols|yape|paypal|pagar|pago|manana|tomorrow)\b', q) and
                 (support.detect_entity_from_question(q) is None or
                  bool(re.search(r'\b(aparte\s+de|adem[aá]s\s+de|fuera\s+de|other\s+than|besides|apart\s+from)\b', q)))) or
            # Consultas con la palabra "disponibles" generales
            (bool(re.search(r'\b(tours?|viajes?|opciones?|paquetes?|cuales?|muestr\w*|ver|dime)\b.*?\bdisponibles?\b', q) or
                  re.search(r'\bdisponibles?\b.*?\b(tours?|viajes?|opciones?|paquetes?)\b', q)) and
             not re.search(r'\b(manana|tomorrow|hoy|today|enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre|noviembre|diciembre)\b|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}', q) and
             support.detect_entity_from_question(q) is None) or
            bool(re.search(r'^\s*(tours?|viajes?|opciones?|destinos?)\s*$', q))
        )
        if is_listing_request:
            is_asking_unique = bool(re.search(r'\b(es el unic\w|es la unic\w|es lo unic\w|hay mas|tienen mas|otros? tours?|otras? opciones?|otros? lugares?|otros? destinos?|que m[aá]s tienen|mas opciones|m[aá]s opciones|other tours?|more tours?|more options?|anything else)\b', q))
            if en:
                if is_asking_unique:
                    title = "Not at all! We have many more confirmed tour options at *Texeira Travel*: 🗺️\n\n"
                else:
                    title = "🗺️ *Our confirmed tours with Texeira Travel:*\n\n"
                
                cat_specs = [
                    ("🏔️ *Machu Picchu & Treks:*", [
                        ('machu-picchu-tren', 'Machu Picchu by Train'),
                        ('machu-picchu-car', 'Machu Picchu by Car'),
                        ('camino-inka', 'Inca Trail'),
                        ('salkantay-trek', 'Salkantay Trek'),
                        ('inka-jungle', 'Inka Jungle to Machu Picchu'),
                        ('choquequirao', 'Choquequirao Trek')
                    ]),
                    ("🌄 *Mountains & Day Tours (Cusco):*", [
                        ('montana-7-colores', 'Rainbow Mountain (7 Colors)'),
                        ('laguna-humantay', 'Humantay Lake'),
                        ('city-tour-cusco', 'City Tour Cusco'),
                        ('valle-sagrado', 'Sacred Valley'),
                        ('maras-moray', 'Maras - Moray'),
                        ('waqra-pukara', 'Waqra Pukara'),
                        ('valle-sur', 'South Valley'),
                        ('maras-moray-cuatrimoto', 'Quad Bike ATV Maras-Moray'),
                        ('puente-qeswachaca', "Q'eswachaca Bridge"),
                        ('tour-mistico', 'Mystic Tour')
                    ]),
                    ("🚌 *Regional Routes:*", [
                        ('ruta-del-sol', 'Route of the Sun (Cusco - Puno)'),
                        ('islas-titicaca', 'Lake Titicaca Islands'),
                        ('canon-colca', 'Colca Canyon')
                    ])
                ]
                footer = "\n\nWhich one would you like to explore? Ask me for photos, prices or itinerary 😊\nOr write 👉 *advisor* to book directly."
            else:
                if is_asking_unique:
                    title = "¡Para nada! No es el único. En *Texeira Travel* tenemos todas estas opciones disponibles: 🗺️\n\n"
                else:
                    title = "🗺️ *Nuestros tours confirmados con Texeira Travel:*\n\n"

                cat_specs = [
                    ("🏔️ *Machu Picchu y Treks:*", [
                        ('machu-picchu-tren', 'Machu Picchu en Tren'),
                        ('machu-picchu-car', 'Machu Picchu by Car'),
                        ('camino-inka', 'Camino Inka'),
                        ('salkantay-trek', 'Salkantay Trek'),
                        ('inka-jungle', 'Inka Jungle to Machu Picchu'),
                        ('choquequirao', 'Choquequirao Trek')
                    ]),
                    ("🌄 *Montañas y Clásicos (Cusco):*", [
                        ('montana-7-colores', 'Montaña de 7 Colores'),
                        ('laguna-humantay', 'Laguna Humantay'),
                        ('city-tour-cusco', 'City Tour Cusco'),
                        ('valle-sagrado', 'Valle Sagrado'),
                        ('maras-moray', 'Maras - Moray'),
                        ('waqra-pukara', 'Waqra Pukara'),
                        ('valle-sur', 'Valle Sur'),
                        ('maras-moray-cuatrimoto', 'Tour Cuatrimoto / Maras-Moray'),
                        ('puente-qeswachaca', "Puente de Q’eswachaca"),
                        ('tour-mistico', 'Tour Místico')
                    ]),
                    ("🚌 *Rutas Regionales:*", [
                        ('ruta-del-sol', 'Ruta del Sol Cusco-Puno'),
                        ('islas-titicaca', 'Islas del Lago Titicaca'),
                        ('canon-colca', 'Cañón del Colca / Baños Termales de Chacapi')
                    ])
                ]
                footer = "\n\n¿Cuál de ellos te gustaría conocer? Pregúntame por fotos, precios o detalles 😊\nO escribe 👉 *asesor* para reservar."

            seen = set()
            blocks = []
            for cat_title, items in cat_specs:
                grp = []
                for eid, default_label in items:
                    if eid in active_tours and is_product_confirmed(eid):
                        label = default_label if en else active_tours[eid]['name']
                        grp.append(f"• {label}")
                        seen.add(eid)
                if grp:
                    blocks.append(f"{cat_title}\n" + "\n".join(grp))

            extras = []
            for eid, t in active_tours.items():
                if eid not in seen and is_product_confirmed(eid):
                    extras.append(f"• {t['name']}")
            if extras:
                extra_title = "✨ *More Experiences:*" if en else "✨ *Otras Opciones:*"
                blocks.append(f"{extra_title}\n" + "\n".join(extras))

            full_body = "\n\n".join(blocks)
            return finish(title + full_body + footer, 'evidence_listing', sources=['F1','F2','F3'])

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
                        msg = f"Currently, *{name_deact}* is not available in our active catalog.\n\nWrite 👉 *advisor* to check alternative options 😊"
                    else:
                        msg = f"Actualmente *{name_deact}* no se encuentra disponible en nuestro catálogo activo. 📋\n\nEscribe 👉 *asesor* si deseas consultar opciones alternativas 😊"
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
                msg = f"Currently, *{tour_name}* is not available in our active catalog, so photos are not available online.\n\nWrite 👉 *advisor* for assistance 😊" if en else f"Actualmente *{tour_name}* no se encuentra disponible en nuestro catálogo activo. 📋\n\nEscribe 👉 *asesor* y te brindamos más opciones 😊"
                return finish(msg, 'evidence_inactive_tour', pending=True, sources=[], entity_id=eid)

            img_data = get_tour_image_data(question, user_msg=question, entity_id=eid or "")
            tour_obj = active_tours.get(eid) if eid else None
            tour_name = tour_obj['name'] if tour_obj else None
            if img_data:
                img_url, img_caption = img_data
                msg = f"Sure! Here is a photo of {tour_name or 'our tours with Texeira Travel'}. 📸✨" if en else f"¡Por supuesto! Aquí tienes una imagen de {tour_name or 'nuestros destinos con Texeira Travel'}. 📸✨"
                return finish(msg, 'evidence_photo', sources=['ASSET_OFICIAL'], entity_id=eid)
            else:
                msg = f"Currently we don't have online photos for {tour_name or 'this tour'}, but our advisor can share our gallery with you." if en else f"Actualmente no disponemos de fotos en línea para {tour_name or 'este tour'}, pero nuestro asesor te compartirá nuestra galería completa."
                return finish(msg, 'evidence_photo', sources=['ASSET_OFICIAL'], entity_id=eid)

        if is_brochure_requested(question):
            if eid and (is_deactivated_tour(eid) or eid not in active_tours):
                tour_info = None
                try:
                    import catalog_service
                    tour_info = catalog_service.get_tour_by_id(eid)
                except Exception:
                    pass
                tour_name = tour_info.get('name', eid) if tour_info else eid
                msg = f"Currently, *{tour_name}* is not available in our active catalog, so no brochure is available.\n\nWrite 👉 *advisor* for assistance 😊" if en else f"Actualmente *{tour_name}* no se encuentra disponible en nuestro catálogo activo. 📋\n\nEscribe 👉 *asesor* y te brindamos más opciones 😊"
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
                msg = f"Currently, *{tour_name}* is not available in our active catalog.\n\nWrite 👉 *advisor* if you would like to inquire about special dates or alternative tours 😊"
            else:
                msg = f"Actualmente *{tour_name}* no se encuentra disponible en nuestro catálogo activo. 📋\n\nEscribe 👉 *asesor* si deseas consultar fechas especiales o tours alternativos 😊"
            return finish(msg, 'evidence_inactive_tour', pending=True, sources=[], entity_id=eid)

        fld=field(q)
        if eid == 'machu-picchu-tren' and re.search(r'dormir|pernoct|alojamiento|overnight|sleep|accommodation', q):
            detail = ('overnight accommodation is not documented for this train tour; hotel pickup does not mean a hotel stay is included' if en else 'el alojamiento o pernocte no está documentado para este tour en tren; el recojo del hotel no significa que incluya hospedaje')
            return unknown(detail, entity_id=eid)
        if eid and fld and lang in {'es','en'}:
            tour_obj = active_tours.get(eid, {})
            name = tour_obj.get('name', eid)
            facts = get_facts(eid)
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
                    if en:
                        msg = f"💰 *{name}*\nOfficial rate: *{price_display}* per person\n\nWrite 👉 *advisor* to book or ask about dates 😊"
                    else:
                        msg = f"💰 *{name}*\nTarifa oficial: *{price_display}* por persona\n\nEscribe 👉 *asesor* para reservar o consultar fechas 😊"
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
                    if en:
                        msg = f"{emoji} *{name}*\n{label}: {dyn_val}\n\nWrite 👉 *advisor* for more details or to book 😊"
                    else:
                        msg = f"{emoji} *{name}*\n{label}: {dyn_val}\n\nEscribe 👉 *asesor* para más detalles o reservar 😊"
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

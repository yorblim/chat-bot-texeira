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
    'hola': '¡Hola! Bienvenido a Texeira Travel. ¿En qué puedo ayudarte?',
    'buenos dias': '¡Buenos días! Bienvenido a Texeira Travel. ¿En qué puedo ayudarte?',
    'buenas tardes': '¡Buenas tardes! Bienvenido a Texeira Travel. ¿En qué puedo ayudarte?',
    'buenas noches': '¡Buenas noches! Bienvenido a Texeira Travel. ¿En qué puedo ayudarte?',
    'hello': 'Hello! Welcome to Texeira Travel. How can I help you?',
    'hi': 'Hi! Welcome to Texeira Travel. How can I help you?',
    'buenas': '¡Buenas! Bienvenido a Texeira Travel. ¿En qué puedo ayudarte?',
    'gracias': '¡De nada! Si tienes más preguntas, con gusto puedo ayudarte.',
    'thanks': "You're welcome! Feel free to ask anything else.",
    'adios': '¡Hasta luego! Que tengas un excelente viaje en Cusco.',
    'bye': 'Goodbye! Have a wonderful trip in Cusco.',
    'saludo': '¡Hola! Bienvenido a Texeira Travel. ¿En qué puedo ayudarte?',
}

_HELP_RESPONSE = '¡Claro! Puedo ayudarte con tours, recorridos, horarios e información sobre nuestros servicios documentados. ¿Qué necesitas saber?'

def install(ns, support, original):
    catalog = support.CATALOG

    def get_current_tours():
        res = {t['entity_id']: dict(t) for t in catalog['tours']}
        try:
            from catalog_service import get_all_tours
            dynamic = get_all_tours(active_only=True)
            for dt in dynamic:
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
        except Exception:
            pass
        return res

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
                return finish('This information requires confirmation with the agency: '+subject+'. '+phone,'evidence_unknown',True,entity_id=entity_id)
            return finish('Este dato requiere confirmacion con la agencia: '+subject+'. '+phone,'evidence_unknown',True,entity_id=entity_id)

        # Catálogo de tours solicitados (antes de evaluar fechas o disponibilidad comercial)
        if (q.strip(' ?¿!.') in {'tour','tours','que tours tienen','que tours ofrecen','lista de tours','what tours do you offer','what tours do you have'} or
            re.search(r'\b(tours?|viajes?|opciones?|paquetes?|cuales?|muestres?|muestrame|mostrar|ver|que|dime)\b.*?\bdisponibles?\b', q) or
            re.search(r'\bdisponibles?\b.*?\b(tours?|viajes?|opciones?|paquetes?)\b', q) or
            re.search(r'\b(muestres?|muestrame|mostrar|ver|dime)\s+(los\s+)?disponibles?\b', q) or
            re.search(r'^\s*(tours?|viajes?)\s*$', q)):
            title = 'Documented tours (availability to be confirmed):\n' if en else 'Tours documentados por Texeira Travel:\n'
            return finish(title+'\n'.join('- '+t['name'] for t in active_tours.values() if is_product_confirmed(t['entity_id'])),'evidence_listing',sources=['F1','F2','F3'])

        # Operaciones comerciales y disponibilidad para fechas puntuales
        if re.search(r'cancel|reembols|refund|yape|paypal|\bpagar\b|\bpago\b|adelant|deposit|\bpay\b|payment|descuento|discount|reserva|booking|\bbook\b|cupos?|spots?|availability|available|disponib|manana|tomorrow|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}',q):
            subj = 'payments, cancellations, bookings or availability for the requested date' if en else 'pagos, cancelaciones, reservas o disponibilidad para la fecha solicitada'
            return unknown(subj)
        if re.search(r'7d/6n|paquete.*7|7.day package',q):
            subj = 'seven-day package not documented in the received sources' if en else 'paquete de siete dias no documentado en las fuentes recibidas'
            return unknown(subj)
        if re.search(r'contact|telefono|whatsapp|correo|email|direccion|ubicacion',q):
            a=catalog['agency'];return finish(phone+'\n'+', '.join(a['emails'])+'\n'+a['address'],'evidence_contact',sources=['F1','F2','F3'])

        eid=entity(q)
        if not eid:
            for h in reversed(prior):
                if h.get('role') == 'human':
                    eid = entity(support.normalize(h['content']))
                    if eid: break

        # ---- MULTIMEDIA: FOTOS Y FOLLETOS PDF ----
        from src.visual.visual_engine import is_photo_requested, is_brochure_requested, get_tour_image_data, get_tour_brochure_data

        if is_photo_requested(question):
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
                msg = f'The sources disagree; please confirm the current information with the agency. {name}. {phone}' if en else f'Las fuentes difieren; confirma el dato vigente con la agencia. {name}. {phone}'
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
                        msg = f"The official published rate for {name} is {price_display}."
                    else:
                        msg = f"La tarifa oficial vigente de {name} es de {price_display}."
                    return finish(msg, 'evidence_confirmed_price', sources=['CATALOGO_OFICIAL'], entity_id=eid)

                subj = f'official price or currency conversion for {name}' if en else f'precio oficial o conversion a soles de {name}'
                return unknown(subj, entity_id=eid)
            if fld=='product':
                msg = f'Documented in the materials received from the agency: {name}' if en else f'Documentado en los materiales recibidos de la agencia: {name}'
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
                    labels={'includes':('Includes' if en else 'Incluye'),'excludes':('Does not include' if en else 'No incluye'),'stops':('Visits' if en else 'Visita'),'schedule':('Published schedule' if en else 'Horario publicado'),'duration':('Published duration' if en else 'Duracion publicada')}
                    label = labels.get(fld, 'Published' if en else 'Publicado')
                    return finish(f"{name}\n{label}: {dyn_val}", f'evidence_{fld}', sources=['CATALOGO_OFICIAL'], entity_id=eid)
                subj = f'undocumented detail for {name}' if en else f'detalle no documentado para {name}'
                return unknown(subj, entity_id=eid)
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
            return finish(tour_title+'\n'+'\n'.join(lines),'evidence_'+fld,sources=[f.source_id for f in selected],entity_id=eid)
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

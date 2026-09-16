"""Una sola decision de evidencia y un solo par de mensajes por turno."""
import re
from src.evidence import get_facts, detect_conflicts, is_product_confirmed

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
    'bye': 'adios',
    'que tal': 'saludo',
    'como estas': 'saludo',
}

_SOCIAL_RESPONSES = {
    'hola': 'Hola! Bienvenido a Texeira Travel. En que puedo ayudarte?',
    'buenos dias': 'Buenos dias! Bienvenido a Texeira Travel. En que puedo ayudarte?',
    'buenas tardes': 'Buenas tardes! Bienvenido a Texeira Travel. En que puedo ayudarte?',
    'buenas noches': 'Buenas noches! Bienvenido a Texeira Travel. En que puedo ayudarte?',
    'hello': 'Hello! Welcome to Texeira Travel. How can I help you?',
    'hi': 'Hi! Welcome to Texeira Travel. How can I help you?',
    'buenas': 'Buenas! Bienvenido a Texeira Travel. En que puedo ayudarte?',
    'gracias': 'De nada! Si tienes mas preguntas, escribeme.',
    'thanks': "You're welcome! Feel free to ask anything else.",
    'adios': 'Hasta luego! Que tengas un excelente viaje.',
    'saludo': 'Hola! Bienvenido a Texeira Travel. En que puedo ayudarte?',
}

_HELP_RESPONSE = 'Claro! Puedo ayudarte con tours, recorridos, horarios e informacion sobre nuestros servicios. Que necesitas?'

def install(ns, support, original):
    catalog = support.CATALOG
    tours = {t['entity_id']:t for t in catalog['tours']}
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
        hits=[(len(a),eid) for eid,aa in aliases.items() for a in aa if a in q]
        return max(hits)[1] if hits else None
    def field(q):
        for key,pattern in [('excludes',r'no incluye|no esta incluido|exclu|not include'),('includes',r'inclu|include'),('schedule',r'horario|hora|schedule|what time|departure'),('duration',r'dura|how long'),('stops',r'lugares|recorrido|ruta|paradas|itinerary|route|places'),('price',r'precio|cuesta|soles|\bpen\b|price|cost|how much'),('product',r'tienen|ofrecen|documentado|oferta|do you have|do you offer')]:
            if re.search(pattern,q): return key
        return None
    support.detect_entity_from_question=lambda q:entity(support.normalize(q))
    support.detect_field_from_question=lambda q:field(support.normalize(q))
    ns['_evaluate_evidence_layer']=lambda *args:None
    ns['check_tour_intent']=lambda *args,**kwargs:None
    def chain(question,user_id='default'):
        q=support.normalize(question); lang=ns['detect_language'](question); en=lang=='en'
        prior=list(ns['get_history'](user_id))
        phone=' / '.join(catalog['agency']['phones'])

        # --- SOCIAL / CONVERSACIONAL: respuesta corta, sin NOTICES, sin LLM ---
        social_key = _SOCIAL_INTENTS.get(q.strip(' ?¿!.'))
        if social_key:
            text = _SOCIAL_RESPONSES[social_key]
            ns['conversation_history'][user_id]=list(prior)
            ns['add_to_history'](user_id,'human',question)
            ns['add_to_history'](user_id,'ai',text)
            return dict(response=text,context_used=False,is_predefined=True,is_fallback=False,
                resolved_autonomously=True,is_escalation=False,needs_agency_confirmation=False,
                needs_confirmation=False,conflict_detected=False,evidence_status='social',
                sources_used=[],route='social',response_route='social')

        # --- AYUDA: respuesta corta, sin NOTICES, sin LLM ---
        if q.strip(' ?¿!.') in {'ayuda','help','me ayudas','ayudame','puedes ayudarme','que puedes hacer','que haces'}:
            text = _HELP_RESPONSE
            ns['conversation_history'][user_id]=list(prior)
            ns['add_to_history'](user_id,'human',question)
            ns['add_to_history'](user_id,'ai',text)
            return dict(response=text,context_used=False,is_predefined=True,is_fallback=False,
                resolved_autonomously=True,is_escalation=False,needs_agency_confirmation=False,
                needs_confirmation=False,conflict_detected=False,evidence_status='social',
                sources_used=[],route='help',response_route='help')

        def finish(text,route, pending=False, sources=(), conflict=False, predefined=True):
            ns['conversation_history'][user_id]=list(prior)
            ns['add_to_history'](user_id,'human',question);ns['add_to_history'](user_id,'ai',text)
            return dict(response=text,context_used=bool(sources),is_predefined=predefined,is_fallback=False,
                resolved_autonomously=not pending,is_escalation=False,needs_agency_confirmation=pending,
                needs_confirmation=pending,conflict_detected=conflict,evidence_status='conflict' if conflict else ('unknown' if pending else 'documented'),
                sources_used=sorted(set(sources)),route=route,response_route=route)
        def unknown(subject):
            return finish('Este dato requiere confirmacion con la agencia: '+subject+'. '+phone,'evidence_unknown',True)
        # Primero operaciones comerciales
        if re.search(r'cancel|reembols|refund|yape|paypal|\bpagar\b|\bpago\b|adelant|deposit|\bpay\b|payment|descuento|discount|reserva|booking|\bbook\b|cupos?|spots?|availability|available|disponib|manana|tomorrow|\d{1,2}\s+de\s+\w+|\d{4}-\d{2}-\d{2}',q):
            return unknown('pagos, cancelaciones, reservas o disponibilidad para la fecha solicitada')
        if re.search(r'7d/6n|paquete.*7|7.day package',q): return unknown('paquete de siete dias no documentado en las fuentes recibidas')
        if re.search(r'contact|telefono|whatsapp|correo|email|direccion|ubicacion',q):
            a=catalog['agency'];return finish(phone+'\n'+', '.join(a['emails'])+'\n'+a['address'],'evidence_contact',sources=['F1','F2','F3'])
        if q.strip(' ?¿!.') in {'tour','tours','que tours tienen','que tours ofrecen','lista de tours','what tours do you offer','what tours do you have'}:
            return finish('Tours documentados (cupos por confirmar):\n'+'\n'.join('- '+t['name'] for t in tours.values() if is_product_confirmed(t['entity_id'])),'evidence_listing',sources=['F1','F2','F3'])
        eid=entity(q); fld=field(q)
        if not eid and fld:
            for h in reversed(prior):
                if h['role']=='human':
                    eid=entity(support.normalize(h['content']))
                    if eid:break
        if eid and fld and lang in {'es','en'}:
            name=tours[eid]['name']; facts=get_facts(eid)
            relevant=detect_conflicts(eid, fld)
            if relevant:
                return finish('Las fuentes difieren; confirma el dato vigente con la agencia. '+name+'. '+phone,'evidence_conflict',True,[f.source_id for f in facts],True)
            if fld=='price':return unknown('precio oficial o conversion a soles de '+name)
            if fld=='product':return finish('Documentado en los materiales recibidos de la agencia: '+name,'evidence_product',sources=[f.source_id for f in facts if f.field=='confirmed_product'])
            selected=[f for f in facts if f.field==fld and f.value is not False]
            targets={'caballo|horse':'caballo','seguro|insurance':'seguro','entrada|ticket|boleto':'entrada|ingreso|boleto','oxigen|oxygen':'oxigeno','bus':'bus','desayuno|breakfast':'desayuno','almuerzo|lunch':'almuerzo'}
            if fld in {'includes','excludes'}:
                for pattern,item in targets.items():
                    if re.search(pattern,q):
                        selected=[f for f in facts if f.field in {'includes','excludes'} and f.item and re.search(item,f.item)]
                        if not selected:return unknown('si el servicio solicitado esta incluido en '+name)
                        break
            if not selected:return unknown('detalle no documentado para '+name)
            lines=[]
            labels={'includes':('Incluye'),'excludes':('No incluye'),'stops':('Visita'),'schedule':('Horario publicado'),'duration':('Duracion publicada')}
            # Agrupar equivalencias solo en la presentación de este producto.
            # Mantener todas las fuentes y no inferir ida/vuelta de un ticket aislado.
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
                if eid=='machu-picchu-tren' and lang=='es' and f.field in {'includes','excludes'}:
                    if f.item=='tickets_tren' and (f.field,'tren_ida_vuelta') in selected_items:
                        continue
                    val=mp_labels.get(f.item,val)
                label=labels.get(f.field,'Publicado')
                line=f'{label}: {val}'
                if line not in lines:lines.append(line)
            return finish(name+'\n'+'\n'.join(lines),'evidence_'+fld,sources=[f.source_id for f in selected])
        # Para otras consultas se conserva el RAG y su proveedor, sin la segunda capa de evidencia.
        result=original(question,user_id)
        ns['conversation_history'][user_id]=list(prior)
        ns['add_to_history'](user_id,'human',question);ns['add_to_history'](user_id,'ai',result['response'])
        result['is_escalation']=False
        if result.get('is_rate_limit') or result.get('is_fallback'):result['resolved_autonomously']=False
        return result
    ns['rag_chain']=chain

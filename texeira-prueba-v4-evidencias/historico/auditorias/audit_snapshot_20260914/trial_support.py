"""trial_support.py v4-evidencias: Integracion del motor de evidencia con rutas deterministas."""
import json
import unicodedata
import re
import time
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / 'data/tours_catalog.json').read_text(encoding='utf-8'))
INDEX = ROOT / 'chroma_v4_evidencias_db'

NAMES = [
    'City Tour Cusco', 'Valle Sagrado completo', 'Machu Picchu en tren',
    'Maras - Moray', 'Valle Sur', 'Laguna Humantay', 'Montaña de 7 Colores',
    'Waqra Pukara', 'Machu Picchu by Car', 'Camino Inka',
    'Salkantay Trek', 'Inka Jungle', 'Choquequirao', 'Tour Místico',
    'Islas del Lago Titicaca', 'Cañón del Colca', 'Ruta del Sol',
    'Tour Cuatrimoto Maras-Moray'
]

ENTITY_IDS = [
    'city-tour-cusco', 'valle-sagrado', 'machu-picchu-tren',
    'maras-moray', 'valle-sur', 'laguna-humantay', 'montana-7-colores',
    'waqra-pukara', 'machu-picchu-car', 'camino-inka',
    'salkantay-trek', 'inka-jungle', 'choquequirao', 'tour-mistico',
    'islas-titicaca', 'canon-colca', 'ruta-del-sol',
    'maras-moray-cuatrimoto'
]

NOTICES = {
    'es': 'Información de los materiales de Texeira. Tarifas, cupos y vigencia por confirmar con la agencia.',
    'en': 'Information from Texeira materials. Confirm prices, availability and current conditions with the agency.',
    'pt': 'Informações dos materiais da Texeira. Confirme preços, disponibilidade e condições atuais com a agência.',
    'fr': 'Informations des documents Texeira. Confirmez les prix, disponibilités et conditions actuelles auprès de l’agence.'
}

import sys
sys.path.insert(0, str(ROOT))
try:
    from src.evidence import (
        get_facts, detect_conflicts, is_product_confirmed,
        get_confirmed_products, build_context_for_entity,
        build_context_for_question, get_listing, get_includes,
        get_route, stats
    )
    EVIDENCE_AVAILABLE = True
except ImportError:
    EVIDENCE_AVAILABLE = False


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')


def detect_entity_from_question(question: str) -> str:
    q = normalize(question)
    entity_keywords = {
        'city-tour-cusco': ['city tour', 'citytour', 'city-tour', 'tour cusco', 'tour de cusco'],
        'valle-sagrado': ['valle sagrado', 'sacred valley'],
        'machu-picchu-tren': ['machu picchu en tren', 'machupicchu tren', 'machu picchu'],
        'machu-picchu-car': ['machu picchu by car', 'machu picchu en auto', 'machu picchu en carro'],
        'valle-sur': ['valle sur', 'south valley'],
        'montana-7-colores': ['montana de 7 colores', '7 colores', 'rainbow mountain', 'vinicunca', 'valle rojo'],
        'laguna-humantay': ['humantay', 'laguna humantay'],
        'waqra-pukara': ['waqra pukara', 'huaccra pukara'],
        'maras-moray': ['maras moray', 'maras-moray', 'moray maras'],
        'maras-moray-cuatrimoto': ['cuatrimoto', 'cuatrimotos', 'atv maras'],
        'camino-inka': ['camino inka', 'camino inca', 'inka trail'],
        'salkantay-trek': ['salkantay', 'salkantay trek'],
        'inka-jungle': ['inka jungle', 'inca jungle'],
        'choquequirao': ['choquequirao'],
        'tour-mistico': ['tour mistico', 'mistico', 'mystic'],
        'islas-titicaca': ['titicaca', 'islas del titicaca', 'uros', 'taquile'],
        'canon-colca': ['canon del colca', 'colca', 'baños termales'],
        'ruta-del-sol': ['ruta del sol', 'cusco puno', 'cusco a puno'],
    }
    for entity_id, keywords in entity_keywords.items():
        for kw in keywords:
            if kw in q:
                return entity_id
    return None


def detect_field_from_question(question: str) -> str:
    q = normalize(question)
    field_keywords = {
        'schedule': ['horario', 'hora', 'a que hora', 'que hora', 'schedule', 'hour', 'time', 'cuando sale', 'cuando parte'],
        'includes': ['incluye', 'incluid', 'que incluye', 'que lleva', 'include', 'includes', 'what include'],
        'excludes': ['no incluye', 'excluye', 'exclu', 'does not include'],
        'stops': ['lugares', 'paradas', 'recorrido', 'ruta', 'stops', 'places', 'route', 'itinerary'],
        'official_price': ['precio', 'cuesta', 'cuanto cuesta', 'price', 'cost', 'how much'],
        'duration': ['duracion', 'cuanto dura', 'duration', 'how long'],
        'confirmed_product': ['tienen', 'ofrecen', 'existe', 'disponible', 'do you have', 'do you offer'],
    }
    for field, keywords in field_keywords.items():
        for kw in keywords:
            if kw in q:
                return field
    return None


def install(ns):
    async def preload_retriever():
        from asyncio import to_thread
        started = time.perf_counter()
        engine = await to_thread(retriever)
        if engine is None:
            raise RuntimeError('Falta el indice v4: no se puede iniciar la prueba.')
        ns['app'].state.retriever_preload_seconds = time.perf_counter() - started
        print(f"[TRIAL v4] Buscador precargado en {ns['app'].state.retriever_preload_seconds:.2f}s.", flush=True)
    ns['app'].add_event_handler('startup', preload_retriever)

    def language(text):
        words = set(re.findall(r'\b\w+\b', normalize(text)))
        markers = {
            'es': set('que cual cuanto cuesta incluye incluidas entradas puedo cancelar manana gracias hola precio precios'.split()),
            'en': set('what which how does the include includes included tickets can cancel tomorrow thanks price'.split()),
            'pt': set('quais quanto custa preco passeios voce quero ola obrigado'.split()),
            'fr': set('quels quelle combien bonjour prix je avec merci'.split()),
        }
        scores = {lang: len(words & values) for lang, values in markers.items()}
        best = max(scores, key=scores.get)
        if scores[best]:
            return best
        if words <= {'tour', 'tours', 'machu', 'picchu', 'humantay', 'salkantay', 'valle', 'sagrado'}:
            return 'es'
        try:
            return ns['LANG_MAP'].get(ns['detect'](text), 'es')
        except Exception:
            return 'es'

    ns['detect_language'] = language

    original_ui = ns['get_chat_html']
    def trial_ui(*args, **kwargs):
        return original_ui(*args, **kwargs).replace('Texeira Travel Tour', 'Texeira — PRUEBA REFERENCIAL v4')
    ns['get_chat_html'] = trial_ui

    keep = {'hola', 'buenos días', 'buenas', 'hello', 'hi', 'adiós', 'chau', 'hasta luego', 'bye', 'gracias', 'muchas gracias', 'thanks', 'ayuda', 'help', 'me ayudas'}
    ns['PREDEFINED_RESPONSES'] = {k: v for k, v in ns['PREDEFINED_RESPONSES'].items() if k in keep}
    ns['get_retriever'] = retriever
    ns['CHROMA_HYBRID_DIR'] = str(INDEX)
    ns['_tour_images_map'] = {}

    ns['SYSTEM_PROMPT'] = '''Eres Texeira Bot, asistente virtual de Texeira Travel. Responde en el idioma del usuario.
Usa solo los datos del contexto proporcionado por el motor de evidencia. El historial sirve para identificar el tour, no como fuente de precios.
Los rangos son estimaciones de mercado, nunca tarifas oficiales.
Si el contexto indica un CONFLICTO de horarios o datos, NO elijas uno. Indica que el dato debe confirmarse con la agencia.
Si un campo es "unknown" o "por confirmar", NO inventes datos. Indica que falta informacion.
La ausencia de un dato NO significa que este excluido. Solo lo que se confirma explicitamente como excluido lo esta.
Los productos "confirmed_product=true" significan que Texeira los documenta, NO que todos sus datos esten confirmados.
No inventes politicas, seguros, descuentos, disponibilidad, importes PEN ni conversiones.
No confirmes reservas ni prometas que un asesor contactara al usuario.
IMPORTANTE: Cuando el usuario pregunte por condiciones comerciales no confirmadas (pagos, adelantos, disponibilidad, precio exacto en soles), indica que faltan datos y remite al contacto publicado de la agencia.
Contexto: {context}
Pregunta: {question}'''

    def listing(message, lang='es'):
        general = {'tour', 'tours', 'precio', 'precios', 'que tours tienen', 'que tours ofrecen',
                    'lista de tours', 'what tours do you offer', 'quais passeios', 'quels circuits'}
        if normalize(message).strip(' ?¿!.') not in general:
            return None
        if EVIDENCE_AVAILABLE:
            return NOTICES.get(lang, NOTICES['es']) + '\n\n' + get_listing()
        lines = []
        for t, name in zip(CATALOG['tours'], NAMES[:len(CATALOG['tours'])]):
            lines.append(f"- {name}")
        return NOTICES.get(lang, NOTICES['es']) + '\n\n' + '\n'.join(lines)

    ns['check_tour_intent'] = listing
    original = ns['rag_chain']

    def chain(question, user_id='default'):
        lang = ns['detect_language'](question)
        q = normalize(question)

        if lang == 'es' and re.search(r'\b(cancel\w*|reembolso\w*)\b', q):
            text = ('No hay una politica de cancelacion o reembolso confirmada en los datos disponibles. '
                    'Consulta con la agencia: ' + CATALOG['agency']['phones'][0] + '.')
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', text)
            return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                    'resolved_autonomously': False, 'is_escalation': False, 'needs_agency_confirmation': True,
                    'response_route': 'evidence_unknown_policy',
                    'evidence_status': 'unknown',
                    'needs_confirmation': True,
                    'conflict_detected': False,
                    'sources_used': [],
                    'route': 'unconfirmed_policy'}

        unconfirmed_keywords = ['paquete 7d', 'paquete de 7', '7d/6n', '7 dias 6 noches']
        if any(x in q for x in unconfirmed_keywords):
            text = ('El Paquete Cusco 7D/6N no esta documentado en ninguna fuente de la agencia. '
                    'Consulta directamente: ' + CATALOG['agency']['phones'][0] + '.')
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', text)
            return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                    'resolved_autonomously': False, 'is_escalation': False, 'needs_agency_confirmation': True,
                    'response_route': 'evidence_unconfirmed_product',
                    'evidence_status': 'unknown',
                    'needs_confirmation': True,
                    'conflict_detected': False,
                    'sources_used': [],
                    'route': 'unconfirmed_product'}

        if EVIDENCE_AVAILABLE:
            entity_id = detect_entity_from_question(question)
            field = detect_field_from_question(question)

            if entity_id and not is_product_confirmed(entity_id):
                text = (f'El producto "{entity_id}" no esta confirmado como tour de Texeira Travel. '
                        'Consulta con la agencia: ' + CATALOG['agency']['phones'][0] + '.')
                ns['add_to_history'](user_id, 'human', question)
                ns['add_to_history'](user_id, 'ai', text)
                return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                        'resolved_autonomously': False, 'is_escalation': False, 'needs_agency_confirmation': True,
                        'response_route': 'evidence_unconfirmed_product',
                        'evidence_status': 'unknown',
                        'needs_confirmation': True,
                        'conflict_detected': False,
                        'sources_used': [],
                        'route': 'unconfirmed_product'}

            if entity_id:
                conflicts = detect_conflicts(entity_id, field)
                conflict_fields = set(c['field'] for c in conflicts)
                if field and field in conflict_fields:
                    conflict = [c for c in conflicts if c['field'] == field][0]
                    src_a = conflict['source_a']
                    src_b = conflict['source_b']
                    sources_used = list(set([src_a.get('source_id',''), src_b.get('source_id','')]))
                    text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                            f'Los materiales de la agencia muestran información diferente sobre {field}. '
                            'Es necesario confirmar el dato vigente con la agencia.\n'
                            f'Contacto: ' + CATALOG['agency']['phones'][0])
                    ns['add_to_history'](user_id, 'human', question)
                    ns['add_to_history'](user_id, 'ai', text)
                    return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                            'resolved_autonomously': False, 'is_escalation': False,
                            'needs_agency_confirmation': True,
                            'response_route': 'evidence_conflict',
                            'evidence_status': 'conflict',
                            'needs_confirmation': True,
                            'conflict_detected': True,
                            'sources_used': sources_used,
                            'route': 'conflict_detected'}

                if field == 'includes' and not conflicts:
                    # Check if question asks about an excluded item
                    q_words = normalize(question).split()
                    excludes = get_facts(entity_id, 'excludes')
                    for ex in excludes:
                        ex_item = str(ex.item).lower().replace('_', ' ')
                        if any(w in ex_item for w in q_words if len(w) > 3):
                            entity_name = next((t['name'] for t in CATALOG['tours'] if t['entity_id'] == entity_id), entity_id)
                            text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                                    f'{entity_name} no incluye {ex.item.replace("_", " ")}. '
                                    f'Esto está confirmado como excluido por la fuente {ex.source_id}.')
                            ns['add_to_history'](user_id, 'human', question)
                            ns['add_to_history'](user_id, 'ai', text)
                            return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                                    'response_route': 'evidence_exclusion',
                                    'evidence_status': 'confirmed',
                                    'needs_confirmation': False,
                                    'conflict_detected': False,
                                    'sources_used': [ex.source_id],
                                    'route': 'evidence_exclusion'}
                    text = NOTICES.get(lang, NOTICES['es']) + '\n\n' + get_includes(entity_id)
                    ns['add_to_history'](user_id, 'human', question)
                    ns['add_to_history'](user_id, 'ai', text)
                    return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                            'response_route': 'evidence_includes',
                            'evidence_status': 'confirmed',
                            'needs_confirmation': False,
                            'conflict_detected': False,
                            'sources_used': [],
                            'route': 'evidence_includes'}

                if field == 'stops' and not conflicts:
                    text = NOTICES.get(lang, NOTICES['es']) + '\n\n' + get_route(entity_id)
                    ns['add_to_history'](user_id, 'human', question)
                    ns['add_to_history'](user_id, 'ai', text)
                    return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                            'response_route': 'evidence_route',
                            'evidence_status': 'confirmed',
                            'needs_confirmation': False,
                            'conflict_detected': False,
                            'sources_used': [],
                            'route': 'evidence_route'}

                if field == 'official_price':
                    tour = next((t for t in CATALOG['tours'] if t['entity_id'] == entity_id), None)
                    text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                            'No hay precio oficial confirmado para este tour. '
                            'La tarifa debe confirmarse con la agencia.\n'
                            f'Contacto: ' + CATALOG['agency']['phones'][0])
                    ns['add_to_history'](user_id, 'human', question)
                    ns['add_to_history'](user_id, 'ai', text)
                    return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                            'resolved_autonomously': False, 'needs_agency_confirmation': True,
                            'response_route': 'evidence_unknown_price',
                            'evidence_status': 'unknown',
                            'needs_confirmation': True,
                            'conflict_detected': False,
                            'sources_used': [],
                            'route': 'evidence_price'}

                if field == 'confirmed_product':
                    tour = next((t for t in CATALOG['tours'] if t['entity_id'] == entity_id), None)
                    if tour and tour.get('confirmed_product'):
                        name = tour['name']
                        text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                                f'Sí, Texeira Travel documenta el tour "{name}". '
                                'Para detalles específicos, consulta con la agencia.\n'
                                f'Contacto: ' + CATALOG['agency']['phones'][0])
                    else:
                        text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                                'No se encontró evidencia de que este tour sea ofrecido por Texeira Travel. '
                                'Consulta con la agencia: ' + CATALOG['agency']['phones'][0])
                    ns['add_to_history'](user_id, 'human', question)
                    ns['add_to_history'](user_id, 'ai', text)
                    return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                            'response_route': 'evidence_product_check',
                            'evidence_status': 'confirmed' if (tour and tour.get('confirmed_product')) else 'unknown',
                            'needs_confirmation': False,
                            'conflict_detected': False,
                            'sources_used': [],
                            'route': 'evidence_product_check'}

        payment_keywords = ['yape', 'adelanto', 'pago', 'pagar', 'forma de pago', 'depósito', 'deposito',
                            'tarjeta', 'credito', 'debito', 'efectivo', 'plin']
        if any(x in q for x in payment_keywords):
            text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                    'No hay información confirmada sobre métodos de pago. '
                    'Consulta directamente con la agencia.\n'
                    f'Contacto: ' + CATALOG['agency']['phones'][0])
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', text)
            return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                    'resolved_autonomously': False, 'needs_agency_confirmation': True,
                    'response_route': 'evidence_unknown_payment',
                    'evidence_status': 'unknown',
                    'needs_confirmation': True,
                    'conflict_detected': False,
                    'sources_used': [],
                    'route': 'unconfirmed_policy'}

        availability_keywords = ['cupo', 'cupos', 'disponibilidad', 'reserva', 'reservar', 'confirmar reserva',
                                 'available', 'booking', 'spots']
        if any(x in q for x in availability_keywords):
            text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                    'No hay acceso a disponibilidad en tiempo real. '
                    'Consulta directamente con la agencia.\n'
                    f'Contacto: ' + CATALOG['agency']['phones'][0])
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', text)
            return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                    'resolved_autonomously': False, 'needs_agency_confirmation': True,
                    'response_route': 'evidence_unknown_availability',
                    'evidence_status': 'unknown',
                    'needs_confirmation': True,
                    'conflict_detected': False,
                    'sources_used': [],
                    'route': 'availability_check'}

        discount_keywords = ['descuento', 'discount', 'dto', 'oferta especial', 'promocion']
        if any(x in q for x in discount_keywords):
            text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                    'No hay información confirmada sobre descuentos. '
                    'Consulta directamente con la agencia.\n'
                    f'Contacto: ' + CATALOG['agency']['phones'][0])
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', text)
            return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                    'resolved_autonomously': False, 'needs_agency_confirmation': True,
                    'response_route': 'evidence_unknown_discount',
                    'evidence_status': 'unknown',
                    'needs_confirmation': True,
                    'conflict_detected': False,
                    'sources_used': [],
                    'route': 'discount_check'}

        contact_keywords = ['contacto', 'telefono', 'whatsapp', 'direccion', 'ubicacion', 'donde estan',
                            'correo', 'email', 'mail']
        if any(x in q for x in contact_keywords):
            a = CATALOG['agency']
            phones = ' / '.join(a['phones'])
            emails = ', '.join(a['emails'])
            text = (NOTICES.get(lang, NOTICES['es']) + '\n'
                    f'Teléfonos: {phones}\n'
                    f'Correos: {emails}\n'
                    f'Dirección: {a["address"]}')
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', text)
            return {'response': text, 'context_used': True, 'is_predefined': False, 'is_fallback': False,
                    'response_route': 'evidence_contact',
                    'evidence_status': 'confirmed',
                    'needs_confirmation': False,
                    'conflict_detected': False,
                    'sources_used': ['F1', 'F2'],
                    'route': 'contact_info'}

        tren_keywords = ['tren', 'perurail', 'inca rail', 'vistadome', 'expedition', 'voyager']
        if any(x in q for x in tren_keywords):
            text = (NOTICES.get(lang, NOTICES['es']) + '\n\n'
                    'Texeira documenta opciones de tren: PeruRail Expedition, PeruRail Vistadome, '
                    'Inca Rail Voyager, Inca Rail 360. '
                    'La clase de tren incluida en cada tour debe confirmarse con la agencia.\n'
                    f'Contacto: ' + CATALOG['agency']['phones'][0])
            ns['add_to_history'](user_id, 'human', question)
            ns['add_to_history'](user_id, 'ai', text)
            return {'response': text, 'context_used': True, 'is_predefined': True, 'is_fallback': False,
                    'route': 'train_info'}

        result = original(question, user_id)
        notice = NOTICES.get(lang, NOTICES['es'])
        if not result['response'].startswith(notice):
            result['response'] = notice + '\n\n' + result['response']
        ns['add_to_history'](user_id, 'human', question)
        ns['add_to_history'](user_id, 'ai', result['response'])
        return result

    from verified_routes import install as install_verified
    import sys
    install_verified(ns, sys.modules[__name__], original)


@lru_cache(maxsize=1)
def retriever():
    if not (INDEX / 'READY.json').exists():
        return None
    import hashlib
    marker = json.loads((INDEX / 'READY.json').read_text(encoding='utf-8'))
    if marker.get('inputs') != input_hashes():
        raise RuntimeError('Las fuentes o documentos cambiaron: crear otro índice versionado.')
    from src.retriever import build_hybrid_retriever
    return build_hybrid_retriever(documents=documents(), persist_directory=str(INDEX))

def input_hashes():
    import hashlib
    names=['tours_catalog.json','evidence_facts.json','conflicts.json','source_registry.json']
    values={name:hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest() for name in names}
    values['documents']=hashlib.sha256(json.dumps(documents(),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return values


def documents():
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)

    if EVIDENCE_AVAILABLE:
        return _build_evidence_documents(splitter)
    return _build_fallback_documents(splitter)


def _build_evidence_documents(splitter):
    rows = []
    for tour in CATALOG['tours']:
        entity_id = tour['entity_id']
        context = build_context_for_entity(entity_id)
        if not context:
            continue
        for i, chunk in enumerate(splitter.split_text(NOTICES['es'] + '\n' + tour['name'] + '\n' + context)):
            conflict_status = 'has_conflict' if detect_conflicts(entity_id) else 'no_conflict'
            rows.append({
                'page_content': chunk,
                'metadata': {
                    'tour_id': entity_id,
                    'tour_name': tour['name'],
                    'chunk_index': i,
                    'source': 'evidence-v4-2026-09-11',
                    'category': 'evidence_based',
                    'evidence_status': conflict_status,
                    'needs_confirmation': tour.get('schedule_status') == 'conflict'
                }
            })

    a = CATALOG['agency']
    phones_str = ' / '.join(a['phones'])
    emails_str = ', '.join(a['emails'])
    rows.append({
        'page_content': NOTICES['es'] + '\nContacto Texeira Travel: ' + phones_str + ' | ' + emails_str + ' | ' + a['address'],
        'metadata': {
            'tour_id': 'agency',
            'tour_name': 'Agencia: datos publicados y confirmados',
            'chunk_index': 0,
            'source': 'evidence-v4-2026-09-11',
            'category': 'agency_contact'
        }
    })
    return rows


def _build_fallback_documents(splitter):
    rows = []
    for tour in CATALOG['tours']:
        name = tour['name']
        eid = tour['entity_id']
        parts = [name, f'Producto confirmado: {tour.get("confirmed_product", False)}']
        if tour.get('schedule_status') == 'conflict':
            parts.append('Horario: conflicto entre fuentes, confirmar con agencia.')
        elif tour.get('schedule_status') == 'confirmed':
            parts.append('Horario: confirmado por la agencia.')
        for i, chunk in enumerate(splitter.split_text(NOTICES['es'] + '\n' + '\n'.join(parts))):
            rows.append({
                'page_content': chunk,
                'metadata': {
                    'tour_id': eid,
                    'tour_name': name,
                    'chunk_index': i,
                    'source': 'evidence-v4-2026-09-11',
                    'category': 'evidence_based'
                }
            })
    return rows

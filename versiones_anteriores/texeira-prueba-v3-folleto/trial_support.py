"""Adaptación aislada del catálogo referencial. No utiliza el catálogo anterior."""
import json
import unicodedata
import re
import time
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / 'data/provisional.json').read_text(encoding='utf-8'))
INDEX = ROOT / 'chroma_v3_folleto_db'
NAMES = ['City Tour Cusco', 'Valle Sagrado completo', 'Machu Picchu en tren', 'Maras - Moray', 'Valle Sur', 'Laguna Humantay', 'Montaña de 7 Colores']
NOTICES = {
 'es': 'PROTOTIPO: precios referenciales por persona; cotización final con la agencia. Las condiciones simuladas no son compromisos de Texeira.',
 'en': 'PROTOTYPE: indicative prices per person; final quote from the agency. Simulated services are not commitments by Texeira.',
 'pt': 'PROTÓTIPO: preços referenciais por pessoa; cotação final com a agência. Serviços simulados não são compromissos da Texeira.',
 'fr': 'PROTOTYPE : prix indicatifs par personne ; devis final auprès de l’agence. Les services simulés ne sont pas des engagements de Texeira.'
}

def normalize(text):
 return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')

def fact_sheet(t, name):
 range_usd = t.get('range_usd')
 if range_usd:
  lo, hi = range_usd
  price_line = f'Rango estimado: USD {lo}–{hi} por adulto, servicio compartido. NO tarifa oficial.'
 else:
  price_line = 'Precio no confirmado en folleto. Consultar a la agencia.'
 return '\n'.join([
  name, price_line,
  'Duración de referencia: ' + t['duration_reference'],
  'Publicado por la agencia: ' + ('; '.join(t['agency_published']) or 'Oferta de este paquete no confirmada.'),
  'ESCENARIO SIMULADO, incluye: ' + '; '.join(t['simulation_includes']) if t['simulation_includes'] else 'Servicios: ver folleto de la agencia.',
  'ESCENARIO SIMULADO, excluye: ' + '; '.join(t['simulation_excludes']) if t['simulation_excludes'] else 'Exclusiones: no especificadas en folleto.',
  'Vigencia de los datos de agencia: ' + t.get('agency_validity', 'Condiciones pendientes de confirmar.'),
  'Políticas de reserva, cancelación, pagos, descuentos y seguro: consultar con la agencia; sin confirmar.',
  'Fuentes de precios: ' + ' '.join(CATALOG['sources'][s] for s in t['market_sources']) if t['market_sources'] else 'Sin fuentes de precios.',
 ])

def documents():
 from langchain.text_splitter import RecursiveCharacterTextSplitter
 splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
 rows = []
 for t, name in zip(CATALOG['tours'], NAMES):
  range_usd = t.get('range_usd')
  price_metadata = {}
  if range_usd:
   price_metadata = {'price_kind': 'reference_range', 'range_min_usd': range_usd[0], 'range_max_usd': range_usd[1]}
  else:
   price_metadata = {'price_kind': 'unconfirmed', 'range_min_usd': 0, 'range_max_usd': 0}
  for i, chunk in enumerate(splitter.split_text(fact_sheet(t, name))):
   rows.append({'page_content': NOTICES['es'] + '\n' + chunk, 'metadata': {'tour_id': t['id'], 'tour_name': name, 'chunk_index': i, 'source': 'brochure-v3-2026-09-11', 'category': 'brochure_confirmed', **price_metadata}})
 agency = CATALOG['agency']
 emails = agency.get('emails', [])
 email_line = '\nCorreos: ' + ', '.join(emails) if emails else ''
 addr_source = agency.get('address_source', 'fuente no especificada')
 rows.append({'page_content': NOTICES['es'] + '\nContacto publicado (folleto): ' + agency['published_phone'] + ' / ' + agency['published_secondary_phone'] + email_line + '\nDirección publicada: ' + agency['published_address'] + ' (fuente: ' + addr_source + ')' + '\nCorreo, pagos, adelantos, descuentos, cancelación y disponibilidad: sin confirmar. No se pueden confirmar reservas. No existe asignación automática de asesor.', 'metadata': {'tour_id': 'agency', 'tour_name': 'Agencia: datos publicados y pendientes', 'chunk_index': 0, 'source': 'brochure-v3-2026-09-11'}})
 return rows

@lru_cache(maxsize=1)
def retriever():
 if not (INDEX / 'READY.json').exists():
  return None
 import hashlib
 marker = json.loads((INDEX/'READY.json').read_text(encoding='utf-8'))
 if marker['catalog_sha256'] != hashlib.sha256((ROOT/'data/provisional.json').read_bytes()).hexdigest():
  raise RuntimeError('El catálogo cambió: crear otro índice de prueba antes de continuar.')
 from src.retriever import build_hybrid_retriever
 return build_hybrid_retriever(documents=documents(), persist_directory=str(INDEX))

def install(ns):
 async def preload_retriever():
  from asyncio import to_thread
  started = time.perf_counter()
  engine = await to_thread(retriever)
  if engine is None:
   raise RuntimeError('Falta el índice provisional: no se puede iniciar la prueba.')
  ns['app'].state.retriever_preload_seconds = time.perf_counter() - started
  print(f"[TRIAL] Buscador precargado en {ns['app'].state.retriever_preload_seconds:.2f}s; sin llamada al LLM.", flush=True)
 ns['app'].add_event_handler('startup', preload_retriever)
 def language(text):
  words = set(re.findall(r'\b\w+\b', normalize(text)))
  markers = {
   'es': set('que cual cuanto cuesta incluye incluidas entradas puedo cancelar manana gracias hola precio precios'.split()),
   'en': set('what which how does the include includes included tickets can cancel tomorrow hello thanks price'.split()),
   'pt': set('quais quanto custa preco passeios voce quero ola obrigado'.split()),
   'fr': set('quels quelle combien bonjour prix je avec merci'.split()),
  }
  scores = {lang: len(words & values) for lang, values in markers.items()}
  best = max(scores, key=scores.get)
  if scores[best]: return best
  # Nombres de destinos y palabras compartidas no determinan el idioma.
  if words <= {'tour','tours','machu','picchu','humantay','salkantay','valle','sagrado'}: return 'es'
  try: return ns['LANG_MAP'].get(ns['detect'](text), 'es')
  except Exception: return 'es'
 ns['detect_language'] = language
 original_ui = ns['get_chat_html']
 def trial_ui(*args, **kwargs):
  return original_ui(*args, **kwargs).replace('Texeira Travel Tour', 'Texeira — PRUEBA REFERENCIAL')
 ns['get_chat_html'] = trial_ui
 # Mantener únicamente saludos y cortesías sin hechos comerciales del prototipo anterior.
 keep = {'hola','buenos días','buenas','hello','hi','adiós','chau','hasta luego','bye','gracias','muchas gracias','thanks'}
 ns['PREDEFINED_RESPONSES'] = {k:v for k,v in ns['PREDEFINED_RESPONSES'].items() if k in keep}
 ns['get_retriever'] = retriever
 ns['CHROMA_HYBRID_DIR'] = str(INDEX)
 ns['_tour_images_map'] = {}
 ns['SYSTEM_PROMPT'] = '''Eres el asistente de un PROTOTIPO de Texeira. Responde en el idioma del usuario. Usa solo los datos del contexto; el historial sirve para identificar el tour, no como fuente de precios.
Los rangos son estimaciones de mercado, nunca tarifas oficiales. Diferencia información publicada de condiciones SIMULADAS. Menciona esa distinción cuando describas inclusiones. Si faltan datos, dilo y remite al contacto publicado. No inventes políticas, seguros, descuentos, disponibilidad, importes PEN ni conversiones. No confirmes reservas ni prometas que un asesor contactará al usuario. El paquete 7D/6N es hipotético, no una oferta confirmada.
IMPORTANTE: Cuando el usuario pregunte por condiciones comerciales no confirmadas (pagos, adelantos, disponibilidad, precio exacto en soles), indica que faltan datos y remite al contacto publicado de la agencia (teléfonos y dirección del contexto). NO menciones "prohibición de conversiones" ni reglas internas; di que no hay tipo de cambio ni cotización confirmada. NO ofrezcas fuentes de precios de mercado (M1-M9) como contacto; usa solo el contacto publicado del objeto agency.
Contexto: {context}
Pregunta: {question}'''

 def listing(message, lang='es'):
  general = {'tour','tours','precio','precios','que tours tienen','que tours ofrecen','lista de tours','what tours do you offer','quais passeios','quels circuits'}
  if normalize(message).strip(' ?¿!.') not in general:
   return None
  lines = []
  for t, name in zip(CATALOG['tours'], NAMES):
   range_usd = t.get('range_usd')
   if range_usd:
    lines.append(f"- {name}: USD {range_usd[0]}–{range_usd[1]}")
   else:
    lines.append(f"- {name}: Precio por confirmar")
  return NOTICES.get(lang, NOTICES['es']) + '\n\n' + '\n'.join(lines)
 ns['check_tour_intent'] = listing
 original = ns['rag_chain']

 def chain(question, user_id='default'):
  lang = ns['detect_language'](question)
  q = normalize(question)
  if lang == 'es' and re.search(r'\b(cancel\w*|reembolso\w*)\b', q):
   text = ('PROTOTIPO: no hay una política de cancelación o reembolso confirmada en los datos disponibles. '
           'No puedo confirmar que sea gratis. Consulta con la agencia: ' + CATALOG['agency']['published_phone'] + '.')
   ns['add_to_history'](user_id,'human',question)
   ns['add_to_history'](user_id,'ai',text)
   return {'response':text, 'context_used':True, 'is_predefined':True, 'is_fallback':False,
           'resolved_autonomously':False, 'is_escalation':False, 'needs_agency_confirmation':True,
           'route':'unconfirmed_policy'}
  unconfirmed_keywords = ['salkantay','7 dias','7 days','7d/6n','paquete completo','paquete de 7']
  if any(x in q for x in unconfirmed_keywords):
   text = ('PROTOTIPO: el Salkantay Trek y el Paquete Cusco 7D/6N NO están confirmados en el folleto de Texeira Travel. '
           'No puedo ofrecer precios ni detalles. Consulta directamente con la agencia: ' + CATALOG['agency']['published_phone'] + '.')
   ns['add_to_history'](user_id,'human',question)
   ns['add_to_history'](user_id,'ai',text)
   return {'response':text, 'context_used':True, 'is_predefined':True, 'is_fallback':False,
           'resolved_autonomously':False, 'is_escalation':False, 'needs_agency_confirmation':True,
           'route':'unconfirmed_product'}
  aliases = [['city tour','city-tour'],['valle sagrado','sacred valley'],['machu picchu','machupicchu'],['humantay'],['colores','rainbow','vinicunca']]
  matched = [i for i,a in enumerate(aliases) if any(x in q for x in a)]
  detail = any(x in q for x in ['precio','cuesta','incluy','inclu','cost','price','dur','hora'])
  if not matched and detail:
   for h in reversed(ns['get_history'](user_id)):
    if h['role'] == 'human':
     matched = [i for i,a in enumerate(aliases) if any(x in normalize(h['content']) for x in a)]
     if matched: break
  if lang == 'es' and len(matched)==1 and detail:
   i = matched[0]
   t = CATALOG['tours'][i]
   parts = []
   if any(x in q for x in ['precio','cuesta','cost','price']):
    parts.append(f"Rango estimado: USD {t['range_usd'][0]}–{t['range_usd'][1]} por adulto, servicio compartido; no es una tarifa oficial.")
   if any(x in q for x in ['incluy','inclu']):
    parts.append('ESCENARIO SIMULADO, incluye: ' + '; '.join(t['simulation_includes']) + '.')
    parts.append('Excluye: ' + '; '.join(t['simulation_excludes']) + '.')
   if any(x in q for x in ['dur','hora']):
    parts.append('Duración de referencia: ' + t['duration_reference'])
   text = NOTICES['es'] + '\n\n' + NAMES[i] + '\n' + '\n'.join(parts)
   needs_agency_conf = False
   if any(x in q for x in ['soles','pen','tipo de cambio','conversión','conversion']):
    needs_agency_conf = True
   if any(x in q for x in ['cupo','cupos','disponibilidad','reserva','reservar','confirmar reserva']):
    needs_agency_conf = True
   if any(x in q for x in ['yape','adelanto','pago','pagar','forma de pago','depósito','deposito']):
    needs_agency_conf = True
   ns['add_to_history'](user_id,'human',question)
   ns['add_to_history'](user_id,'ai',text)
   return {'response': text, 'context_used': True, 'is_predefined': True, 'is_fallback': False,
           'resolved_autonomously': not needs_agency_conf,
           'needs_agency_confirmation': needs_agency_conf,
           'route': 'provisional_catalog'}
  if q.strip(' ?¿!.') in {'contacto','telefono','whatsapp','direccion','ubicacion'}:
   a = CATALOG['agency']
   text = NOTICES.get(lang,NOTICES['es']) + '\n' + a['published_phone'] + ' / ' + a['published_secondary_phone'] + '\n' + a['published_address']
   ns['add_to_history'](user_id,'human',question)
   ns['add_to_history'](user_id,'ai',text)
   return {'response':text,'context_used':True,'is_predefined':True,'is_fallback':False}
  result = original(question,user_id)
  notice = NOTICES.get(lang,NOTICES['es'])
  if not result['response'].startswith(notice): result['response'] = notice + '\n\n' + result['response']
  ns['add_to_history'](user_id, 'human', question)
  ns['add_to_history'](user_id, 'ai', result['response'])
  return result
 ns['rag_chain'] = chain

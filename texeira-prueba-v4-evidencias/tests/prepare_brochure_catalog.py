import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""Transcripción explícita de las imágenes aportadas; no consulta servicios externos."""
import json
from pathlib import Path
root = Path(__file__).parent
old = json.loads((root/'data/provisional.json').read_text(encoding='utf-8'))
specs = [
 ('city-tour-cusco','City Tour Cusco',['city tour','city-tour'], 'de 10am 14pm y de 13:30pm 18:30pm', 'Dos turnos impresos con notación ambigua: «10am 14pm» y «13:30pm 18:30pm». Confirmar horas exactas; no normalizadas.', ['Templo de Koricancha','Sacsayhuamán','Qenqo','Puca pucara','Tambomachay'], ['Bus turístico','Guía profesional'], 'B2'),
 ('valle-sagrado','Valle Sagrado',['valle sagrado','sacred valley'], 'de 7:30 am a 18:30 pm','07:30–18:30 según folleto; confirmar para la fecha solicitada.', ['Chinchero','Moray','Maras salineras','Ollantaytambo','Pisac','Urubamba'], ['Almuerzo buffet en Urubamba','Bus turístico','Guía profesional'], 'B2'),
 ('machu-picchu-clasico','Machu Picchu',['machu picchu','machupicchu'], None,'Horario y duración no indicados en el folleto.', [], ['Traslado Cusco–Ollanta–Cusco','Tren ida y vuelta','Bus de subida y bajada','Ingresos a Machu Picchu','Guía profesional'], 'B1'),
 ('maras-moray','Maras–Moray',['maras','moray'], 'de 8:40 am a 14:00 pm','08:40–14:00 según folleto; confirmar para la fecha solicitada.', ['Awana de Chinchero','Moray','Salineras'], ['Bus turístico o cuatrimotos (alternativas; modalidad por confirmar)','Guía profesional'], 'B1'),
 ('valle-sur','Valle Sur',['valle sur','south valley'], 'de 8:40 am a 14:00 pm','08:40–14:00 según folleto; confirmar para la fecha solicitada.', ['Tipon','Pikillaqta','Templo de Andahuaylillas'], ['Bus turístico','Guía profesional'], 'B1'),
 ('montana-7-colores','Montaña de 7 Colores',['7 colores','colores','rainbow','vinicunca'], 'de 4:30 am a 5:00 pm','04:30–17:00 según folleto; confirmar para la fecha solicitada.', [], ['Transporte turístico','Guía profesional','Desayuno','Almuerzo'], 'B1'),
 ('laguna-humantay','Laguna Humantay',['humantay'], 'de 4:30 am a 5:00 pm','04:30–17:00 según folleto; confirmar para la fecha solicitada.', [], ['Transporte turístico','Guía profesional','Desayuno','Almuerzo'], 'B1'),
]
tours = []
for ident,name,aliases,raw,schedule,route,services,source in specs:
    previous = next((t for t in old['tours'] if t['id']==ident), None)
    # La referencia anterior de Machu Picchu excluía bus: no trasladar su rango
    # al producto del folleto, que lo incluye.
    reference = previous if ident != 'machu-picchu-clasico' else None
    tours.append(dict(id=ident,name=name,aliases=aliases,schedule_raw=raw,
        duration_reference=schedule,route=route,agency_includes=services,
        agency_source=source,exclusions=None,
        range_usd=reference['range_usd'] if reference else None,
        market_sources=reference['market_sources'] if reference else [],
        price_note='Referencia histórica de mercado del prototipo, no cotización del servicio del folleto; modalidades pueden diferir.' if reference else 'Sin precio confirmado ni referencia comparable incorporada.',
        unknowns='El folleto no detalla exclusiones, cupos, pagos ni cancelaciones. Un servicio no mencionado queda sin confirmar, no excluido.'))
agency = dict(old['agency'])
agency.update(name='TEXEIRA TRAVEL — TRAVEL AGENCY E.I.R.L.', emails=['texeiratraveltour@hotmail.com','eugeniotejeira@hotmail.com'],
    email='texeiratraveltour@hotmail.com', contact_source='B2', address_source='F1 (Facebook anterior; no figura en estas imágenes)',
    contact_status='Teléfonos y correos impresos; operatividad no comprobada.')
catalog = dict(version='brochure-v3-2026-09-11', status='agency_brochure_user_confirmed',
    publication_date=None, supplied_date='2026-09-11', agency=agency, policies=old['policies'],
    sources={**old['sources'],'B1':'data/agency_sources/brochure_page_1.jpeg','B2':'data/agency_sources/brochure_page_2.jpeg'},
    tours=tours, currency='USD',price_pen=None,exchange_rate=None,
    unconfirmed_in_brochure=['Salkantay','Paquete Cusco 7D/6N'],
    note='El usuario confirma que la agencia trabaja con este folleto. No contiene tarifas ni fecha de vigencia. Rangos heredados no son precios oficiales.')
target=root/'data/agency_brochure_v3.json'
if target.exists(): raise SystemExit('No se sobrescribe el catálogo versionado.')
target.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Transcripción y conciliación del folleto de Texeira','',catalog['note'],'',
 'Fuentes: B1 y B2 son copias de las fotografías suministradas. La fecha de publicación del folleto no es visible.','',
 '## Contactos', agency['name'],agency['published_phone']+' / '+agency['published_secondary_phone'],*agency['emails'],
 'Dirección: se conserva la fuente de Facebook anterior; no aparece en el folleto.','']
for t in tours:
    lines += ['## '+t['name'],'Fuente: '+t['agency_source'],'Horario literal: '+str(t['schedule_raw']),t['duration_reference'],
        'Recorrido: '+('; '.join(t['route']) or 'No detallado.'),'Servicios publicados: '+'; '.join(t['agency_includes']),t['unknowns'],'']
lines += ['## Cambios y dudas',
 '- Machu Picchu: el bus de subida y bajada pasa a servicio publicado. Se retira el rango activo USD 300–400 porque procedía de una modalidad sin ese bus; queda conservado en provisional.json.',
 '- Humantay: la entrada ya no se afirma incluida. Caballos, seguros y otras exclusiones previas dejan de afirmarse: no están detallados aquí.',
 '- City Tour: Koricancha figura en el recorrido; no se afirma opcional ni entrada incluida. Confirmar notación de los dos turnos.',
 '- Valle Sagrado: horario del folleto 07:30–18:30; reemplaza el 07:00 de la fuente anterior para esta versión.',
 '- Maras–Moray: bus O cuatrimotos; confirmar modalidad, no prometer ambos.',
 '- Salkantay y paquete 7D/6N: no figuran aquí; se retiran del listado activo, no se afirma que la agencia no los venda.',
 '- Confirmar tarifas/vigencia, entradas de cada tour, exclusiones y políticas. No hay precios publicados en estas páginas.']
(root/'TRANSCRIPCION_FOLLETO_V3.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Catálogo versionado y transcripción creados:',len(tours),'tours.')

"""Correcciones verificadas contra documentos del usuario, 2026-09-12."""
import json, hashlib
from pathlib import Path
root=Path(__file__).parent
def read(name): return json.loads((root/'data'/name).read_text(encoding='utf-8'))
def save(name,obj): (root/'data'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
data=read('evidence_facts.json'); facts=data['facts']; cat=read('tours_catalog.json')
facts[:]=[f for f in facts if f['fact_id']!='address-f1-note']
facts[:]=[f for f in facts if f['fact_id']!='mm-inc-cuatrimotos-f1']
for f in facts:
    if f['field']=='duration' and f['entity_id'] in {'salkantay-trek','inka-jungle','choquequirao'}:
        f['value']='4 días (itinerario publicado; confirmar variante y noches)'
    if f['fact_id']=='email2-f1': f['value']='eugeniotejeira@hotmail.com'
    if f['fact_id']=='mp-product-f2':
        f.update(source_id='F1',source_page='B1',note='Machu Picchu en tren está en el folleto; F2 p3 corresponde a City Tour.')
    if f['fact_id']=='mm-product-f2': f.update(source_id='F1',source_page='B1',note='Maras–Moray documentado en el folleto; F2 p3 es City Tour.')
    if f['fact_id']=='mm-inc-bus-f1':
        f.update(item='bus_turistico_o_cuatrimotos_(modalidad_por_confirmar)',note='Alternativas, no dos servicios simultáneos.')
    if f['source_id']=='F3': f['note']='Verificado en PDF original por extracción y render el 2026-09-12; documento sin fecha de vigencia.'
    if f['fact_id']=='ct-schedule-f1':
        f['note']='Notación original ambigua: de 10am 14pm y de 13:30pm 18:30pm. Normalización orientativa, no horario vigente confirmado.'
def add(e,field,value,page,item=None,source='F2'):
    if any(f['entity_id']==e and f['field']==field and f.get('item')==item and f['value']==value and f['source_id']==source for f in facts): return
    facts.append(dict(fact_id=f'audit-{e}-{field}-{item or "value"}-{source}',entity_id=e,field=field,item=item,value=value,source_id=source,source_page=page,evidence_status='confirmed'))
pages={'camino-inka':14,'salkantay-trek':16,'inka-jungle':17,'choquequirao':18,'tour-mistico':19,'islas-titicaca':20,'canon-colca':21,'ruta-del-sol':22}
for e,p in pages.items(): add(e,'confirmed_product',True,p)
for e,p in [('salkantay-trek',16),('inka-jungle',17),('choquequirao',18)]: add(e,'duration','4 días (itinerario publicado; confirmar variante y noches)',p)
add('puente-qeswachaca','confirmed_product',True,8)
if not any(t['entity_id']=='puente-qeswachaca' for t in cat['tours']):
    cat['tours'].append(dict(entity_id='puente-qeswachaca',name="Puente de Q’eswachaca",confirmed_product=True,product_sources=['F2'],schedule_status='unknown',includes_status='unknown',excludes_status='unknown',route_status='unknown'))
cat['agency']['emails']=['texeiratraveltour@hotmail.com','eugeniotejeira@hotmail.com']
cat['last_updated']='2026-09-12'
for t in cat['tours']:
    entity_facts=[f for f in facts if f['entity_id']==t['entity_id']]
    for field,status in [('stops','route_status'),('includes','includes_status'),('excludes','excludes_status')]:
        if not any(f['field']==field for f in entity_facts): t[status]='unknown'
    if t['entity_id']=='salkantay-trek': t['duration']='4 días; noches no confirmadas'
    if t['entity_id']=='laguna-humantay': t['includes_note']='Desayuno documentado en F1; F3 p5 no publica inclusiones.'
    t['product_sources']=sorted({f['source_id'] for f in entity_facts if f['field']=='confirmed_product' and f['value'] is True})
reg=read('source_registry.json')
for s in reg['sources']:
    if s['source_id']=='F3':
        s['pages']=8; s['transcription_method']='Extracción local y revisión de páginas renderizadas, 2026-09-12'
        s['notes']='PDF original del usuario, ocho páginas. Sin fecha de vigencia, tarifas ni políticas publicadas.'
    s['publication_date']=None
save('evidence_facts.json',data);save('tours_catalog.json',cat);save('source_registry.json',reg)
print('Fuentes conciliadas:',len(facts),'hechos;',len(cat['tours']),'productos.')

"""Local visual review with synthetic fixtures; never connects to production."""
import sys
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from admin_theme import decorate
from handoff_support import PANEL
from operational_metrics import PAGE
from catalog_ui import get_catalog_html
import admin_dashboard
admin_dashboard._load_evaluation_results = lambda: None
rows = [dict(id=f'DEMO-{i}', channel='whatsapp', user_id=f'Cliente de ejemplo {i}',
    status=status, created_at='2026-09-27T15:30:00Z', question='Quisiera confirmar disponibilidad de Machu Picchu.',
    context='[]', advisor='', note='') for i, status in enumerate(['pending','pending','in_progress','closed'])]
tours = [dict(entity_id=str(i), name=name, official_price='', currency='PEN', schedule='Por confirmar',
    duration='', photo_filename='', brochure_filename='', is_canonical=True) for i,name in enumerate(['Machu Picchu en Tren','City Tour Cusco','Valle Sagrado','Laguna Humantay'])]
metrics = dict(total_interactions=10, avg_latency_ms=1200, resolution_rate_pct=60, escalation_rate_pct=20)
interaction = dict(id=1,timestamp='2026-09-27T15:30',user_id='DEMO',channel='test',detected_language='es',user_message='¿Qué tours tienen?',bot_response='Respuesta de ejemplo, sin datos reales.',resolved_autonomously=True,escalated_to_human=False,latency_ms=1200)
operational = dict(observed_since='2026-09-27T15:30:00Z',received=10,api_accepted=9,send_failed=1,processing_failed=0,processing=0,provider_rate_limits=0,api_acceptance_pct=90,generation_ms=1200,api_acceptance_ms=1800,human_requests={'pending':2,'closed':1})
pages = {'/handoffs': decorate(PANEL.replace('__CSRF__','demo'), 'handoffs'), '/catalogo':get_catalog_html('demo'),
    '/dashboard':admin_dashboard.get_dashboard_html(metrics,[interaction]),'/operational-metrics':decorate(PAGE,'metrics')}
qa = '''<script>setTimeout(async()=>{try{
const check=(ok,msg)=>{if(!ok)throw Error(msg)};
const visible=()=>[...document.querySelectorAll('.ticket')].filter(x=>!x.hidden);
check(visible().length===2,'pending filter');
const ticket=visible()[0];ticket.open=true;
ticket.querySelector('textarea').value='Borrador de prueba';
document.querySelector('[data-state=closed]').click();check(visible().length===1,'closed filter');
document.querySelector('[data-state=pending]').click();check(ticket.querySelector('textarea').value==='Borrador de prueba','draft preserved');
const search=document.getElementById('ticketSearch');search.value='DEMO-1';search.dispatchEvent(new Event('input'));check(visible().length===1,'search');search.value='';search.dispatchEvent(new Event('input'));
ticket.querySelector('input[type=text]').value='Asesor de ejemplo';
window.fetch=async()=>({ok:false,json:async()=>({error:'Fallo simulado; borrador conservado'})});
const send=ticket.querySelector('.btn-close');await send.onclick();check(!send.disabled,'retry enabled');check(ticket.querySelector('textarea').value==='Borrador de prueba','error preserved draft');
document.body.insertAdjacentHTML('afterbegin','<p id="qa-result">PASS: filtros, búsqueda, borrador y reintento</p>');
}catch(e){document.body.insertAdjacentHTML('afterbegin','<p id="qa-result">FAIL: '+e.message+'</p>')}},800)</script>'''
pages['/handoffs?qa=1'] = pages['/handoffs'].replace('</html>', qa+'</html>')
open_script = '<script>setTimeout(()=>{const t=document.querySelector(".ticket");if(t)t.open=true;},500)</script>'
pages['/handoffs?open=1'] = pages['/handoffs'].replace('</html>', open_script + '</html>')
catalog_open = '<script>setTimeout(()=>{if(window.openModal)openModal("tourModal");},500)</script>'
pages['/catalogo?open=1'] = pages['/catalogo'].replace('</html>', catalog_open + '</html>')
dashboard_open = '<script>setTimeout(()=>{const d=document.querySelector("details");if(d)d.open=true;},500)</script>'
pages['/dashboard?open=1'] = pages['/dashboard'].replace('</html>', dashboard_open + '</html>')
metrics_open = '<script>setTimeout(()=>{const m=document.querySelector(".admin-method");if(m)m.open=true;},500)</script>'
pages['/operational-metrics?open=1'] = pages['/operational-metrics'].replace('</html>', metrics_open + '</html>')
data = {'/handoffs/data':rows,'/api/catalog/tours':tours,'/operational-metrics/data':operational}
class Preview(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in data:
            content=json.dumps(data[self.path]).encode(); media='application/json'
        elif self.path in pages:
            content=pages[self.path].encode(); media='text/html; charset=utf-8'
        else:
            self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',media);self.end_headers();self.wfile.write(content)
    def do_POST(self):
        self.send_error(405,'Preview only: no changes or messages sent')
print('Synthetic preview: http://127.0.0.1:8035/handoffs',flush=True)
HTTPServer(('127.0.0.1',8035),Preview).serve_forever()

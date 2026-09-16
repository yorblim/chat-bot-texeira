"""Solicitudes humanas persistentes; panel exclusivo del servidor local."""
import json
import re
import secrets
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'human_requests.db'


@contextmanager
def connection():
    conn = sqlite3.connect(str(DB), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, channel TEXT NOT NULL,
        question TEXT NOT NULL, context TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        advisor TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '')''')
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_open_request ON requests(channel,user_id) WHERE status != 'closed'")
    conn.commit()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def create_request(user_id, channel, question, context):
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT * FROM requests WHERE user_id=? AND channel=? AND status!='closed'", (user_id, channel)).fetchone()
        if row:
            return dict(row), False
        ticket = secrets.token_hex(6)
        conn.execute('INSERT INTO requests(id,user_id,channel,question,context,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                     (ticket,user_id,channel,question,json.dumps(context[-6:],ensure_ascii=False),'pending',now,now))
        return dict(conn.execute('SELECT * FROM requests WHERE id=?',(ticket,)).fetchone()), True


def update_request(ticket, status, advisor, note):
    if status not in {'in_progress','closed'} or not advisor.strip():
        raise ValueError('Indica el asesor y un estado válido.')
    if status == 'closed' and not note.strip():
        raise ValueError('Describe el resultado de la atención antes de cerrar.')
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM requests WHERE id=?',(ticket,)).fetchone()
        if not row: raise ValueError('Solicitud inexistente.')
        if row['status']=='closed': raise ValueError('La solicitud ya está cerrada.')
        if row['status']=='pending' and status=='closed': raise ValueError('Primero toma la solicitud en atención.')
        conn.execute('UPDATE requests SET status=?,advisor=?,note=?,updated_at=? WHERE id=?',
                     (status,advisor.strip(),note.strip(),datetime.now(timezone.utc).isoformat(),ticket))


def requested(text):
    normalized=''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))
    return normalized.strip(' .!¿?') in {
        'asesor','hablar con un asesor','quiero hablar con un asesor',
        'necesito un asesor','quiero hablar con una persona','solicitar asesor',
        'human agent','speak to an agent','i want to speak to an agent',
    }


def apply_request(ns, result, user_id, channel, question):
    if not result.get('handoff_requested'): return result
    result=dict(result)
    try:
        history=ns['get_history'](user_id)
        row, created=create_request(user_id,channel,question,history[:-2])
        result['response']=(f"Tu solicitud {row['id']} está registrada y pendiente de atención humana. "
                            'Aún no ha sido atendida. Puedes seguir haciendo consultas al bot.')
        result.update(handoff_id=row['id'],handoff_status=row['status'],handoff_registered=True)
        if row['status']=='in_progress':
            result['response']=f"Tu solicitud {row['id']} ya está en atención. Aún no está cerrada."
    except sqlite3.Error:
        result['response']='No pude registrar la solicitud. Intenta nuevamente o usa los contactos de la agencia.'
        result.update(handoff_registered=False,handoff_status='registration_failed')
    result['resolved_autonomously']=False
    # Mantener exactamente la respuesta final en el historial.
    history=ns['conversation_history'].get(user_id,[])
    if history and history[-1].get('role')=='ai': history[-1]['content']=result['response']
    return result


def install(ns):
    original=ns['rag_chain']
    def chain(question,user_id='default'):
        if not requested(question):
            result=original(question,user_id)
            if result.get('needs_agency_confirmation'):
                result=dict(result)
                lang = ns.get('detect_language', lambda q: 'es')(question)
                if lang == 'en':
                    result['response']+='\nTo register a request for human assistance, type: speak to an agent.'
                else:
                    result['response']+='\nPara registrar una solicitud de atención humana, escribe: asesor.'
                history=ns['conversation_history'].get(user_id,[])
                if history and history[-1].get('role')=='ai': history[-1]['content']=result['response']
            return result
        text='Registrando solicitud de atención humana.'
        ns['add_to_history'](user_id,'human',question)
        ns['add_to_history'](user_id,'ai',text)
        return dict(response=text,is_fallback=False,is_predefined=True,is_escalation=False,
                    resolved_autonomously=False,needs_agency_confirmation=True,
                    handoff_requested=True,response_route='human_request',route='human_request')
    ns['rag_chain']=chain
    csrf=secrets.token_urlsafe(24)
    app=ns['app']

    def local(request):
        return request.client is not None and request.client.host in {'127.0.0.1','::1','testclient'}

    @app.get('/handoffs',response_class=HTMLResponse)
    async def panel(request:Request):
        if not local(request): return HTMLResponse('Acceso local requerido',status_code=403)
        return HTMLResponse(PANEL.replace('__CSRF__',csrf))

    @app.get('/handoffs/data')
    async def data(request:Request):
        if not local(request): return JSONResponse({'error':'Acceso local requerido'},status_code=403)
        with connection() as conn:
            rows=[dict(r) for r in conn.execute('SELECT * FROM requests ORDER BY created_at DESC LIMIT 200')]
        return JSONResponse(rows)

    @app.post('/handoffs/{ticket}')
    async def update(ticket:str,request:Request):
        if not local(request) or request.headers.get('X-Handoff-CSRF')!=csrf:
            return JSONResponse({'error':'Solicitud no autorizada'},status_code=403)
        try:
            body=await request.json()
            update_request(ticket,str(body.get('status','')),str(body.get('advisor',''))[:100],str(body.get('note',''))[:2000])
            return JSONResponse({'ok':True})
        except (ValueError,TypeError,AttributeError) as exc:
            return JSONResponse({'error':str(exc)},status_code=400)


PANEL='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Solicitudes para asesores — Texeira</title>
<style>body{font:16px system-ui;max-width:1000px;margin:32px auto;padding:20px;background:#f4f7f8;color:#18333b}article{background:white;padding:20px;margin:16px 0;border:1px solid #cbdadd;border-radius:12px}button,input,textarea{font:inherit;padding:10px;margin:5px}button{cursor:pointer}pre{white-space:pre-wrap}label{display:block}textarea{width:90%}</style>
<h1>Solicitudes para asesores</h1><p>Registrar una solicitud no significa que el cliente ya fue atendido. Cierra cada caso solo después de la atención y anota el resultado.</p>
<p>Los avisos automáticos al WhatsApp del asesor todavía no están configurados.</p>
<a href="/operational-metrics">Ver métricas operativas</a> <button id="refresh">Actualizar</button><p id="feedback" role="status"></p><main id="list"></main>
<script>
const stateNames={pending:'Pendiente',in_progress:'En atención',closed:'Cerrada'};
const elem=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
async function load(){const r=await fetch('/handoffs/data');if(!r.ok)throw Error('No se pudieron cargar las solicitudes');const rows=await r.json();const list=document.getElementById('list');list.replaceChildren();if(!rows.length)list.append(elem('p','No hay solicitudes registradas.'));
for(const x of rows){const a=elem('article');a.append(elem('h2',`${x.id} · ${stateNames[x.status]}`),elem('p',`${x.channel} · ${x.user_id} · ${new Date(x.created_at).toLocaleString()}`),elem('p',x.question));
const details=elem('details');details.append(elem('summary','Ver contexto'));for(const h of JSON.parse(x.context))details.append(elem('pre',`${h.role}: ${h.content}`));a.append(details);
if(x.status==='closed'){a.append(elem('p',`Asesor: ${x.advisor}`),elem('p',x.note));}
else{const label=elem('label','Asesor responsable');const who=elem('input');who.value=x.advisor;label.append(who);const nlabel=elem('label','Resultado de atención');const note=elem('textarea');note.value=x.note;nlabel.append(note);const b=elem('button',x.status==='pending'?'Tomar solicitud':'Cerrar solicitud');b.onclick=async()=>{b.disabled=true;try{const r=await fetch('/handoffs/'+x.id,{method:'POST',headers:{'Content-Type':'application/json','X-Handoff-CSRF':'__CSRF__'},body:JSON.stringify({status:x.status==='pending'?'in_progress':'closed',advisor:who.value,note:note.value})});const d=await r.json();if(!r.ok)throw Error(d.error);await load()}catch(e){document.getElementById('feedback').textContent=e.message;b.disabled=false}};a.append(label,nlabel,b)}list.append(a)}}
document.getElementById('refresh').onclick=()=>load().catch(e=>document.getElementById('feedback').textContent=e.message);load().catch(e=>document.getElementById('feedback').textContent=e.message);
</script></html>'''

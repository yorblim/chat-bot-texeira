import os
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
from runtime_settings import state_file
from db_adapter import is_postgres, get_db_session
DB = state_file('human_requests.db')


@contextmanager
def connection():
    if is_postgres():
        with get_db_session() as conn:
            yield conn
    else:
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
        inserted = conn.execute("INSERT INTO requests(id,user_id,channel,question,context,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) "
                     "ON CONFLICT (channel,user_id) WHERE status != 'closed' DO NOTHING RETURNING id",
                     (ticket,user_id,channel,question,json.dumps(context[-6:],ensure_ascii=False),'pending',now,now))
        if inserted.fetchone() is not None:
            return dict(conn.execute('SELECT * FROM requests WHERE id=?',(ticket,)).fetchone()), True
        row = conn.execute("SELECT * FROM requests WHERE user_id=? AND channel=? AND status!='closed'", (user_id, channel)).fetchone()
        if row is None:
            raise RuntimeError('La solicitud cambió de estado; vuelve a intentar.')
        return dict(row), False


class AdvisorDeliveryError(RuntimeError):
    """El proveedor no confirmó el envío; no confirmar cambios del ticket."""


def update_request(ticket, status, advisor, note, send_to_customer=False):
    if not isinstance(send_to_customer, bool):
        raise ValueError('La opción de envío debe ser verdadera o falsa.')
    if status not in {'in_progress','closed'} or not advisor.strip():
        raise ValueError('Indica el asesor y un estado válido.')
    if status == 'closed' and not note.strip():
        raise ValueError('Describe el resultado de la atención antes de cerrar.')
    if send_to_customer and not note.strip():
        raise ValueError('Escribe la respuesta que deseas enviar.')
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        lock = ' FOR UPDATE' if is_postgres() else ''
        row=conn.execute('SELECT * FROM requests WHERE id=?' + lock,(ticket,)).fetchone()
        if not row: raise ValueError('Solicitud inexistente.')
        if row['status']=='closed': raise ValueError('La solicitud ya está cerrada.')
        if row['status']=='pending' and status=='closed': raise ValueError('Primero toma la solicitud en atención.')
        if send_to_customer and row['channel'] != 'whatsapp':
            raise ValueError('Esta solicitud no pertenece al canal WhatsApp.')
        changed = conn.execute('UPDATE requests SET status=?,advisor=?,note=?,updated_at=? WHERE id=? AND status=?',
                     (status,advisor.strip(),note.strip(),datetime.now(timezone.utc).isoformat(),ticket,row['status']))
        if changed.rowcount != 1:
            raise ValueError('Otro asesor actualizó la solicitud; recarga antes de continuar.')
        if send_to_customer:
            # Mantener el bloqueo hasta terminar: otra operación no puede cerrar
            # el mismo ticket entre la validación y el intento de envío.
            try:
                from src.services.whatsapp import send_whatsapp_message
                sent = send_whatsapp_message(
                    text=f"Hola, soy {advisor.strip()} de Texeira Travel:\n\n{note.strip()}",
                    to_phone=row['user_id'],
                )
            except Exception:
                raise AdvisorDeliveryError('WhatsApp no confirmó el envío. El ticket no se actualizó. Comprueba la entrega antes de reintentar.') from None
            if not sent:
                raise AdvisorDeliveryError('WhatsApp no confirmó el envío. El ticket no se actualizó. Comprueba la entrega antes de reintentar.')
    return send_to_customer


def requested(text):
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    q = normalized.strip(' .!¿?¡\'"')
    exact_phrases = {
        'asesor', 'asesora', 'asesores',
        'hablar con un asesor', 'hablar con una asesora', 'hablar con un agente',
        'hablar con una persona', 'hablar con un humano', 'hablar con alguien',
        'quiero hablar con un asesor', 'quiero hablar con una asesora',
        'quiero hablar con una persona', 'quiero hablar con un humano', 'quiero hablar con alguien',
        'necesito un asesor', 'necesito una asesora', 'necesito un agente',
        'necesito hablar con un asesor', 'necesito hablar con una persona',
        'solicitar asesor', 'solicitar agente', 'atencion humana', 'ayuda humana',
        'human agent', 'speak to an agent', 'i want to speak to an agent',
        'talk to an agent', 'talk to a human', 'speak to a human', 'speak to a person',
        'human support', 'human help', 'i need human help',
    }
    if q in exact_phrases:
        return True

    patterns = [
        # Hablar / comunicarse con asesor / persona / humano / agente
        r'\b(quiero|quisiera|deseo|necesito|puedo|busco)\s+(hablar|conversar|comunicarme|contactar|contactarme)\s+(con\s+)?(un\s+|una\s+|algun\s+|alguna\s+)?(asesor\w*|persona\w*|humano\w*|agente\w*|operador\w*|alguien)\b',
        # Solicitar que le llamen o contacten directamente
        r'\b(quiero\s+que\s+me\s+llamen|pueden\s+llamarme|me\s+pueden\s+llamar|favor\s+de\s+llamarme|llamenme)\b',
        r'\b(pueden\s+contactarme|me\s+pueden\s+contactar|quiero\s+que\s+me\s+contacten|contactenme)\b',
        # Ayuda / atención humana
        r'\b(ayuda|atencion|soporte|asistencia)\s+humana?\b',
        # En inglés
        r'\b(human\s+support|human\s+help|human\s+assistance)\b',
        r'\b(i\s+want\s+to|i\s+need\s+to|can\s+i|i\s+need)\s+(speak|talk|chat|contact)?\s*(to|with)?\s*(a\s+|an\s+)?(human|person|agent|advisor|representative)\b',
        r'\b(call\s+me|please\s+call\s+me|can\s+you\s+call\s+me)\b',
    ]
    for pat in patterns:
        if re.search(pat, q):
            return True
    return False



def notify_advisor(row, send_fn=None, advisor_phone=None):
    """
    Envía una notificación push vía WhatsApp al número del asesor humano
    cuando se registra una nueva solicitud de derivación (handoff).
    """
    phone = advisor_phone or os.getenv('ADVISOR_WHATSAPP_PHONE', '')
    if not phone:
        print(f"[ADVISOR NOTIFY] Aviso no enviado para ticket {row.get('id')}: ADVISOR_WHATSAPP_PHONE ausente.")
        return False

    ticket_id = row.get('id', 'N/A')
    channel = row.get('channel', 'N/A')
    user_id = row.get('user_id', 'N/A')
    question = row.get('question', '')
    created_at = row.get('created_at', '')

    base_url = os.getenv('APP_BASE_URL', 'http://127.0.0.1:8023').rstrip('/')
    msg = (
        f"🛎️ *NUEVA SOLICITUD DE ATENCIÓN HUMANA — TEXEIRA TRAVEL*\n"
        f"• Ticket: #{ticket_id}\n"
        f"• Canal: {channel}\n"
        f"• Cliente: {user_id}\n"
        f"• Consulta: \"{question}\"\n"
        f"• Fecha/Hora: {created_at}\n"
        f"👉 Gestionar en el panel: {base_url}/handoffs"
    )

    if send_fn:
        try:
            return send_fn(text=msg, to_phone=phone)
        except Exception as e:
            print(f"[ADVISOR NOTIFY ERROR] Error al enviar notificación: {e}")
            return False

    try:
        from app import send_whatsapp_message
        return send_whatsapp_message(text=msg, to_phone=phone)
    except Exception as e:
        print(f"[ADVISOR NOTIFY ERROR] No se pudo invocar send_whatsapp_message: {e}")
        return False


def apply_request(ns, result, user_id, channel, question):
    if not result.get('handoff_requested'): return result
    result=dict(result)
    en=result.get('handoff_language')=='en'
    try:
        history=ns['get_history'](user_id)
        row, created=create_request(user_id,channel,question,history[:-2])
        if created and channel in {'whatsapp', 'messenger'} and ns.get('ADVISOR_NOTIFICATIONS_ENABLED', False):
            send_fn = ns.get('send_whatsapp_message')
            advisor_phone = ns.get('ADVISOR_WHATSAPP_PHONE') or os.getenv('ADVISOR_WHATSAPP_PHONE', '')
            try:
                notify_advisor(row, send_fn=send_fn, advisor_phone=advisor_phone)
            except Exception as e:
                print(f"[ADVISOR NOTIFY] Error silencioso al notificar asesor: {e}")
        result['response']=(f"Tu solicitud {row['id']} está registrada y pendiente de atención humana. "
                            'Aún no ha sido atendida. Puedes seguir haciendo consultas al bot.')
        result.update(handoff_id=row['id'],handoff_status=row['status'],handoff_registered=True)
        if en:
            result['response']=(f"Your request {row['id']} is registered and pending human attention. "
                                'It has not been handled yet. You can continue asking the bot questions.')
        if row['status']=='in_progress':
            result['response']=f"Tu solicitud {row['id']} ya está en atención. Aún no está cerrada."
            if en: result['response']=f"Your request {row['id']} is being handled. It is not closed yet."
    except (sqlite3.Error, Exception):
        result['response']='No pude registrar la solicitud. Intenta nuevamente o usa los contactos de la agencia.'
        result.update(handoff_registered=False,handoff_status='registration_failed')
        if en: result['response']='I could not register the request. Please try again or use the agency contact details.'
    result['resolved_autonomously']=False
    # Mantener exactamente la respuesta final en el historial.
    history=ns['conversation_history'].get(user_id,[])
    if history and history[-1].get('role')=='ai':
        if 'update_last_history_response' in ns:
            ns['update_last_history_response'](user_id, result['response'])
        else:
            history[-1]['content']=result['response']
    return result


def install(ns):
    original=ns['rag_chain']
    def chain(question,user_id='default'):
        if not requested(question):
            result=original(question,user_id)
            if result.get('needs_agency_confirmation'):
                result=dict(result)
                lang = ns.get('detect_language', lambda q: 'es')(question)
                response_text = result.get('response', '')
                if lang == 'en':
                    if 'advisor' not in response_text.lower():
                        result['response'] += '\nWrite \U0001f449 *advisor* to speak with our team at the agency.'
                else:
                    if 'asesor' not in response_text.lower():
                        result['response'] += '\nEscribe \U0001f449 *asesor* para hablar con nuestro equipo en la agencia.'
                history=ns['conversation_history'].get(user_id,[])
                if history and history[-1].get('role')=='ai':
                    if 'update_last_history_response' in ns:
                        ns['update_last_history_response'](user_id, result['response'])
                    else:
                        history[-1]['content']=result['response']
            return result
        text='Registrando solicitud de atención humana.'
        if 'add_history_turn' in ns:
            ns['add_history_turn'](user_id, question, text)
        else:
            ns['add_to_history'](user_id,'human',question)
            ns['add_to_history'](user_id,'ai',text)
        return dict(response=text,is_fallback=False,is_predefined=True,is_escalation=False,
                    resolved_autonomously=False,needs_agency_confirmation=True,
                    handoff_requested=True,handoff_language=ns['detect_language'](question),
                    response_route='human_request',route='human_request')
    ns['rag_chain']=chain
    csrf=secrets.token_urlsafe(24)
    app=ns['app']

    def local(request):
        if os.getenv('ALLOW_CLOUD_RUN') or os.getenv('K_SERVICE'):
            return True
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
            status=str(body.get('status',''))
            advisor=str(body.get('advisor',''))[:100]
            note=str(body.get('note',''))[:2000]
            send_to_customer=body.get('send_to_customer',False)
            msg_sent=update_request(ticket,status,advisor,note,send_to_customer)
            return JSONResponse({'ok':True, 'message_sent': msg_sent})
        except AdvisorDeliveryError as exc:
            return JSONResponse({'ok':False, 'message_sent':False, 'error':str(exc)},status_code=502)
        except (ValueError,TypeError,AttributeError) as exc:
            return JSONResponse({'error':str(exc)},status_code=400)


PANEL='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Consola de Asesores y Handoffs — Texeira Travel</title>
<style>
  :root { --primary: #0284c7; --primary-hover: #0369a1; --success: #16a34a; --bg: #f1f5f9; --card: #ffffff; --text: #0f172a; --muted: #64748b; }
  body { font-family: system-ui, -apple-system, sans-serif; max-width: 960px; margin: 30px auto; padding: 20px; background: var(--bg); color: var(--text); }
  header { margin-bottom: 24px; border-bottom: 1px solid #cbd5e1; padding-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
  h1 { margin: 0; font-size: 24px; color: #0369a1; display: flex; align-items: center; gap: 8px; }
  .nav-links a { color: var(--primary); text-decoration: none; font-weight: 500; margin-right: 16px; }
  .nav-links a:hover { text-decoration: underline; }
  article { background: var(--card); padding: 22px; margin: 16px 0; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 700; text-transform: uppercase; }
  .badge-pending { background: #fef3c7; color: #92400e; }
  .badge-in_progress { background: #dbeafe; color: #1e40af; }
  .badge-closed { background: #dcfce7; color: #166534; }
  .client-meta { color: var(--muted); font-size: 14px; margin-bottom: 10px; }
  .client-query { font-size: 16px; font-weight: 500; background: #f8fafc; padding: 12px; border-left: 4px solid var(--primary); border-radius: 4px; margin: 12px 0; }
  details { margin: 12px 0; background: #fafafa; padding: 8px 12px; border-radius: 8px; border: 1px solid #eee; }
  summary { font-size: 14px; font-weight: 600; cursor: pointer; color: var(--muted); }
  pre { white-space: pre-wrap; font-size: 13px; margin: 8px 0; color: #334155; }
  label { display: block; font-weight: 600; font-size: 14px; margin: 10px 0 4px; color: #334155; }
  input[type="text"], textarea { width: 100%; box-sizing: border-box; font-family: inherit; font-size: 15px; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px; }
  textarea { min-height: 80px; resize: vertical; }
  .checkbox-group { display: flex; align-items: center; gap: 8px; margin: 14px 0; font-size: 14px; font-weight: 500; cursor: pointer; }
  .checkbox-group input { width: 18px; height: 18px; cursor: pointer; }
  .btn-group { display: flex; gap: 10px; margin-top: 14px; }
  button { font-family: inherit; font-weight: 600; font-size: 14px; padding: 10px 18px; border-radius: 8px; border: none; cursor: pointer; transition: background 0.15s ease-in-out; }
  .btn-take { background: #e0f2fe; color: #0369a1; }
  .btn-take:hover { background: #bae6fd; }
  .btn-close { background: var(--success); color: white; }
  .btn-close:hover { background: #15803d; }
  .btn-refresh { background: white; border: 1px solid #cbd5e1; color: var(--text); }
  .btn-refresh:hover { background: #f8fafc; }
  .closed-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 14px; }
  #feedback { margin: 10px 0; font-weight: 600; }
  #feedback.error { color: #dc2626; }
  #feedback.success { color: #16a34a; }
</style>
<header>
  <div>
    <h1>🛎️ Consola de Asesores — Texeira Travel</h1>
    <p style="margin: 4px 0 0; color: var(--muted); font-size: 14px;">Gestión de consultas escaladas y atención humana por WhatsApp</p>
  </div>
  <div class="nav-links">
    <a href="/catalogo">🗺️ Catálogo</a>
    <a href="/dashboard">📊 Dashboard</a>
    <a href="/operational-metrics">📈 Métricas</a>
    <button id="refresh" class="btn-refresh">🔄 Actualizar</button>
  </div>
</header>
<p id="feedback" role="status"></p>
<main id="list"></main>
<script>
const stateNames = { pending: 'Pendiente', in_progress: 'En atención', closed: 'Cerrada' };
const stateBadges = { pending: 'badge-pending', in_progress: 'badge-in_progress', closed: 'badge-closed' };
const elem = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

async function load() {
  const list = document.getElementById('list');
  try {
    const r = await fetch('/handoffs/data');
    if (!r.ok) throw Error('No se pudieron cargar las solicitudes.');
    const rows = await r.json();
    list.replaceChildren();
    if (!rows.length) {
      list.append(elem('p', '', 'No hay solicitudes registradas en este momento.'));
      return;
    }
    for (const x of rows) {
      const a = elem('article');
      
      const head = elem('div', 'card-header');
      head.append(
        elem('h2', '', `Ticket #${x.id}`),
        elem('span', `badge ${stateBadges[x.status] || ''}`, stateNames[x.status] || x.status)
      );
      a.append(head);

      const meta = elem('div', 'client-meta');
      meta.textContent = `Canal: ${x.channel} · Cliente: ${x.user_id} · Fecha: ${new Date(x.created_at).toLocaleString()}`;
      a.append(meta);

      const query = elem('div', 'client-query');
      query.textContent = `Consulta: "${x.question}"`;
      a.append(query);

      if (x.context && x.context !== '[]') {
        const det = elem('details');
        det.append(elem('summary', '', '💬 Ver historial previo de conversación'));
        try {
          const hist = JSON.parse(x.context);
          for (const h of hist) {
            det.append(elem('pre', '', `[${h.role.toUpperCase()}]: ${h.content}`));
          }
        } catch(e) {}
        a.append(det);
      }

      if (x.status === 'closed') {
        const closedBox = elem('div', 'closed-box');
        closedBox.append(
          elem('strong', '', `Atendido por: ${x.advisor || 'Asesor'}`),
          elem('p', '', `Resultado: ${x.note || 'Cerrado'}`)
        );
        a.append(closedBox);
      } else {
        const formDiv = elem('div');
        
        const lWho = elem('label', '', 'Nombre del Asesor');
        const who = elem('input');
        who.type = 'text';
        who.placeholder = 'Ej: Eugenio Maldonado';
        who.value = x.advisor || '';
        formDiv.append(lWho, who);

        const lNote = elem('label', '', 'Respuesta al cliente / Nota de atención');
        const note = elem('textarea');
        note.placeholder = 'Escribe aquí el mensaje para el cliente o el resultado de la atención...';
        note.value = x.note || '';
        formDiv.append(lNote, note);

        const checkLabel = elem('label', 'checkbox-group');
        const sendCheck = elem('input');
        sendCheck.type = 'checkbox';
        sendCheck.checked = true;
        checkLabel.append(sendCheck, ' Enviar esta respuesta directamente al WhatsApp del cliente');
        formDiv.append(checkLabel);

        const btnGroup = elem('div', 'btn-group');
        
        if (x.status === 'pending') {
          const bTake = elem('button', 'btn-take', '✋ Tomar solicitud');
          bTake.onclick = async () => {
            if (!who.value.trim()) { alert('Por favor ingresa tu nombre de asesor.'); who.focus(); return; }
            bTake.disabled = true;
            await sendUpdate(x.id, 'in_progress', who.value, note.value, false);
          };
          btnGroup.append(bTake);
        }

        const bClose = elem('button', 'btn-close', sendCheck.checked ? '🚀 Responder y Cerrar' : '✅ Cerrar Solicitud');
        sendCheck.onchange = () => {
          bClose.textContent = sendCheck.checked ? '🚀 Responder y Cerrar' : '✅ Cerrar Solicitud';
        };

        bClose.onclick = async () => {
          if (!who.value.trim()) { alert('Por favor ingresa tu nombre de asesor.'); who.focus(); return; }
          if (!note.value.trim()) { alert('Escribe la respuesta o nota de atención antes de cerrar.'); note.focus(); return; }
          bClose.disabled = true;
          await sendUpdate(x.id, 'closed', who.value, note.value, sendCheck.checked);
        };
        btnGroup.append(bClose);

        formDiv.append(btnGroup);
        a.append(formDiv);
      }

      list.append(a);
    }
  } catch (err) {
    list.replaceChildren(elem('p', 'error', err.message));
  }
}

async function sendUpdate(ticketId, status, advisor, note, sendToCustomer) {
  const fb = document.getElementById('feedback');
  fb.className = '';
  fb.textContent = 'Procesando...';
  try {
    const r = await fetch(`/handoffs/${ticketId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Handoff-CSRF':'__CSRF__'
      },
      body: JSON.stringify({
        status: status,
        advisor: advisor,
        note: note,
        send_to_customer: sendToCustomer
      })
    });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || 'Error al actualizar');
    fb.className = 'success';
    fb.textContent = d.message_sent ? '¡Respuesta enviada por WhatsApp y ticket actualizado!' : 'Ticket actualizado correctamente.';
    setTimeout(() => { fb.textContent = ''; }, 4000);
    await load();
  } catch (e) {
    fb.className = 'error';
    fb.textContent = e.message;
  }
}

document.getElementById('refresh').onclick = load;
load();
</script></html>'''

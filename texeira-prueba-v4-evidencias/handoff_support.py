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
        # BEGIN IMMEDIATE eliminado: el context manager get_db_session() ya
        # gestiona la transacción. En PostgreSQL, BEGIN IMMEDIATE no existe
        # y provocaba fallo silencioso. FOR UPDATE se usa en update_request.
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


_DELIVERY_ERROR = 'WhatsApp no confirmó el envío. El ticket no se actualizó. Comprueba la entrega antes de reintentar.'


def _deliver(to_phone, text, buttons=None):
    """Envío obligatorio: si WhatsApp no confirma, la transacción se revierte."""
    try:
        from src.services.whatsapp import send_whatsapp_message
        kwargs = {'text': text, 'to_phone': to_phone}
        if buttons:
            kwargs['buttons'] = buttons
        sent = send_whatsapp_message(**kwargs)
    except Exception:
        raise AdvisorDeliveryError(_DELIVERY_ERROR) from None
    if not sent:
        raise AdvisorDeliveryError(_DELIVERY_ERROR)


def _deliver_best_effort(to_phone, text, buttons=None):
    """Envío de cortesía (aviso de toma / agradecimiento): nunca bloquea el ticket."""
    try:
        from src.services.whatsapp import send_whatsapp_message
        kwargs = {'text': text, 'to_phone': to_phone}
        if buttons:
            kwargs['buttons'] = buttons
        return bool(send_whatsapp_message(**kwargs))
    except Exception as exc:
        print(f'[HANDOFF] Mensaje de cortesía no enviado a {to_phone}: {type(exc).__name__}')
        return False


def advisor_text(advisor, text):
    """Formato visible para el cliente de cada mensaje escrito por un asesor."""
    return f"*{advisor.strip()} · Texeira Travel:*\n{text.strip()}"


def update_request(ticket, status, advisor, note, send_to_customer=False,
                   notify_customer=False, send_closing=False, outcome=None):
    """Cambia el estado del ticket.

    - send_to_customer: envía la nota al cliente (obligatorio; si falla, revierte).
    - notify_customer: al tomar (pending -> in_progress) avisa al cliente que un
      asesor ya lo atiende (cortesía; no revierte si falla).
    - send_closing: al cerrar envía el agradecimiento y el bot vuelve a atender
      (cortesía; no revierte si falla).
    - outcome: diccionario opcional que recibe el resultado de cada envío.
    """
    for flag in (send_to_customer, notify_customer, send_closing):
        if not isinstance(flag, bool):
            raise ValueError('La opción de envío debe ser verdadera o falsa.')
    if status not in {'in_progress','closed'} or not advisor.strip():
        raise ValueError('Indica el asesor y un estado válido.')
    if status == 'closed' and not note.strip():
        raise ValueError('Describe el resultado de la atención antes de cerrar.')
    if send_to_customer and not note.strip():
        raise ValueError('Escribe la respuesta que deseas enviar.')
    note_body = advisor_text(advisor, note) if send_to_customer else ''
    with connection() as conn:
        # BEGIN IMMEDIATE eliminado: incompatible con PostgreSQL vía db_adapter.
        # El bloqueo pesimista se logra con FOR UPDATE en la sentencia SELECT.
        lock = ' FOR UPDATE' if is_postgres() else ''
        row=conn.execute('SELECT * FROM requests WHERE id=?' + lock,(ticket,)).fetchone()
        if not row: raise ValueError('Solicitud inexistente.')
        row = dict(row)
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
            _deliver(row['user_id'], note_body)

    # Tras confirmar el ticket: registrar en la memoria para que el bot conserve
    # el contexto de lo que respondió el asesor, y enviar mensajes de cortesía.
    customer = row['user_id']
    advisor_name = advisor.strip()
    on_whatsapp = row['channel'] == 'whatsapp'
    result = {'message_sent': send_to_customer, 'customer_notified': False, 'closing_sent': False}
    if send_to_customer:
        _history_append(customer, 'ai', note_body, {'author': 'advisor', 'advisor': advisor_name, 'handoff_id': ticket})
    if on_whatsapp and notify_customer and status == 'in_progress' and row['status'] == 'pending':
        cust_lang = _customer_language(customer)
        text = taken_message(advisor_name, cust_lang)
        if _deliver_best_effort(customer, text, buttons=[end_handoff_button(cust_lang)]):
            result['customer_notified'] = True
            _history_append(customer, 'ai', text, {'author': 'advisor', 'advisor': advisor_name, 'handoff_id': ticket, 'event': 'handoff_taken'})
    if on_whatsapp and send_closing and status == 'closed':
        text = closing_message(advisor_name, _customer_language(customer))
        if _deliver_best_effort(customer, text):
            result['closing_sent'] = True
            _history_append(customer, 'ai', text, {'author': 'system', 'handoff_id': ticket, 'event': 'handoff_closed'})
    if isinstance(outcome, dict):
        outcome.update(result)
    return send_to_customer


def send_advisor_message(ticket, advisor, text):
    """Mensaje del asesor durante la atención, sin cerrar la solicitud.

    Si el ticket seguía pendiente, escribir al cliente equivale a tomarlo. El
    ticket queda 'in_progress', por lo que el bot permanece en pausa. Incluye
    un botón rápido para que el cliente también pueda finalizar la atención
    cuando su duda o reserva quede resuelta.
    """
    advisor = (advisor or '').strip()[:100]
    text = (text or '').strip()[:2000]
    if not advisor or not text:
        raise ValueError('Indica tu nombre de asesor y el mensaje para el cliente.')
    body = advisor_text(advisor, text)
    with connection() as conn:
        lock = ' FOR UPDATE' if is_postgres() else ''
        row = conn.execute('SELECT * FROM requests WHERE id=?' + lock, (ticket,)).fetchone()
        if not row: raise ValueError('Solicitud inexistente.')
        row = dict(row)
        if row['status'] == 'closed': raise ValueError('La solicitud ya está cerrada.')
        if row['channel'] != 'whatsapp':
            raise ValueError('Esta solicitud no pertenece al canal WhatsApp.')
        changed = conn.execute('UPDATE requests SET status=?,advisor=?,updated_at=? WHERE id=? AND status=?',
                               ('in_progress', advisor, datetime.now(timezone.utc).isoformat(), ticket, row['status']))
        if changed.rowcount != 1:
            raise ValueError('Otro asesor actualizó la solicitud; recarga antes de continuar.')
        cust_lang = _customer_language(row['user_id'])
        _deliver(row['user_id'], body, buttons=[end_handoff_button(cust_lang)])
    _history_append(row['user_id'], 'ai', body, {'author': 'advisor', 'advisor': advisor, 'handoff_id': ticket})
    return True


# ------------------------------------------------------------------
# Pausa del bot mientras un asesor atiende la conversación
# ------------------------------------------------------------------
# Regla: solo un ticket 'in_progress' (un asesor lo tomó) silencia al bot.
# Un ticket 'pending' no lo silencia: todavía nadie atiende y el cliente puede
# seguir consultando. El silencio termina al cerrar el ticket o, como red de
# seguridad, si el asesor no registra actividad en HANDOFF_PAUSE_TIMEOUT_HOURS.
PAUSE_CHANNELS = {'whatsapp'}
_HOOKS = {}


def _pause_timeout_hours():
    try:
        return max(0.0, float(os.getenv('HANDOFF_PAUSE_TIMEOUT_HOURS', '24')))
    except ValueError:
        return 24.0


def _parse_ts(value):
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def active_pause(user_id, channel, now=None):
    """Ticket que mantiene al bot en silencio para este cliente, o None."""
    if channel not in PAUSE_CHANNELS or not user_id:
        return None
    try:
        with connection() as conn:
            row = conn.execute("SELECT * FROM requests WHERE user_id=? AND channel=? AND status='in_progress'",
                               (user_id, channel)).fetchone()
    except Exception as exc:
        # Ante un fallo de lectura el bot responde: es preferible a dejar al cliente sin respuesta.
        print(f'[HANDOFF PAUSE] Estado no disponible, el bot continúa: {type(exc).__name__}')
        return None
    if not row:
        return None
    row = dict(row)
    timeout = _pause_timeout_hours()
    updated = _parse_ts(row.get('updated_at'))
    if timeout and updated:
        now = now or datetime.now(timezone.utc)
        if (now - updated).total_seconds() > timeout * 3600:
            print(f"[HANDOFF PAUSE] Ticket {row['id']} sin actividad del asesor en {timeout:g} h; el bot retoma.")
            return None
    return row


def record_paused_message(user_id, text, ticket):
    """Guarda el mensaje del cliente durante la pausa (lo verá el asesor y el bot).

    Si no puede guardarse, lanza la excepción para que Meta reintente la entrega
    y el mensaje no se pierda.
    """
    _history_append(user_id, 'human', text,
                    {'handoff_id': ticket.get('id'), 'during_advisor_pause': True}, strict=True)


def _history_append(user_id, role, content, metadata=None, strict=False):
    add = _HOOKS.get('add_to_history')
    if add is None:
        if strict:
            raise RuntimeError('Memoria de conversación no disponible.')
        return False
    try:
        add(user_id, role, content, metadata=metadata)
        return True
    except Exception as exc:
        if strict:
            raise
        print(f'[HANDOFF] No se pudo registrar el mensaje en la memoria: {type(exc).__name__}')
        return False


def _customer_language(user_id):
    """Idioma de los últimos mensajes del cliente; español por defecto."""
    get_hist = _HOOKS.get('get_history')
    detect = _HOOKS.get('detect_language')
    if not get_hist or not detect:
        return 'es'
    try:
        texts = [h.get('content', '') for h in get_hist(user_id) if h.get('role') == 'human'][-3:]
        lang = detect(' '.join(texts)) if texts else 'es'
    except Exception:
        return 'es'
    return lang if lang in ('es', 'en', 'pt') else 'es'


def taken_message(advisor, language):
    return _request_message(
        language,
        es=f"👋 Hola, soy {advisor}, asesor(a) de Texeira Travel. Ya tengo tu consulta y te responderé por este mismo chat en unos minutos.",
        en=f"👋 Hi, I'm {advisor}, an advisor at Texeira Travel. I have your request and will reply in this same chat in a few minutes.",
        pt=f"👋 Olá, sou {advisor}, assessor(a) da Texeira Travel. Já recebi sua consulta e responderei por este mesmo chat em alguns minutos.",
    )


def closing_message(advisor, language):
    return _request_message(
        language,
        es=(f"✅ Tu consulta fue atendida por {advisor}. ¡Muchas gracias por confiar en Texeira Travel! 🙌\n\n"
            "Si necesitas algo más, escríbeme por aquí: vuelvo a estar disponible para ayudarte con tours, precios y horarios 😊"),
        en=(f"✅ Your request was handled by {advisor}. Thank you very much for choosing Texeira Travel! 🙌\n\n"
            "If you need anything else, just write here: I'm available again to help you with tours, prices and schedules 😊"),
        pt=(f"✅ Sua consulta foi atendida por {advisor}. Muito obrigado por confiar na Texeira Travel! 🙌\n\n"
            "Se precisar de mais alguma coisa, escreva aqui: estou disponível novamente para ajudar com passeios, preços e horários 😊"),
    )


def end_handoff_button(language='es'):
    """Botón rápido de WhatsApp (<= 20 caracteres) para que el cliente finalice la atención."""
    lang = language if language in ('es', 'en', 'pt') else 'es'
    title = _request_message(
        lang,
        es='✅ Finalizar atención',
        en='✅ End conversation',
        pt='✅ Encerrar conversa',
    )
    return {'id': f'btn_end_handoff:{lang}', 'title': title[:20]}


def customer_closing_message(advisor, previous_status, language):
    """Mensaje de agradecimiento y reactivación cuando el propio cliente finaliza la atención."""
    advisor = (advisor or '').strip()
    if previous_status == 'in_progress' or advisor:
        who_es = advisor or 'nuestro asesor'
        who_en = advisor or 'our advisor'
        who_pt = advisor or 'nosso assessor'
        return _request_message(
            language,
            es=(f"✅ Dimos por finalizada tu atención con {who_es}. ¡Muchas gracias por confiar en Texeira Travel! 🙌\n\n"
                "Tu asistente virtual vuelve a estar activo para ayudarte con tours, precios y horarios 😊"),
            en=(f"✅ We have closed your conversation with {who_en}. Thank you very much for choosing Texeira Travel! 🙌\n\n"
                "Your virtual assistant is active again to help you with tours, prices and schedules 😊"),
            pt=(f"✅ Encerramos seu atendimento com {who_pt}. Muito obrigado por confiar na Texeira Travel! 🙌\n\n"
                "Seu assistente virtual está ativo novamente para ajudar com passeios, preços e horários 😊"),
        )
    if previous_status == 'pending':
        return _request_message(
            language,
            es=("✅ Tu solicitud de atención con un asesor fue finalizada. ¡Muchas gracias por comunicarte con Texeira Travel! 🙌\n\n"
                "Sigo disponible por aquí para ayudarte con tours, precios y horarios 😊"),
            en=("✅ Your request to speak with an advisor has been closed. Thank you very much for contacting Texeira Travel! 🙌\n\n"
                "I'm still here to help you with tours, prices and schedules 😊"),
            pt=("✅ Sua solicitação de atendimento com um assessor foi encerrada. Muito obrigado por falar com a Texeira Travel! 🙌\n\n"
                "Continuo disponível por aqui para ajudar com passeios, preços e horários 😊"),
        )
    return _request_message(
        language,
        es=("✅ Tu atención con el asesor ya se encuentra finalizada. ¡Muchas gracias por confiar en Texeira Travel! 🙌\n\n"
            "¿En qué más puedo ayudarte hoy con nuestros tours, precios u horarios? 😊"),
        en=("✅ Your advisor session is already closed. Thank you very much for choosing Texeira Travel! 🙌\n\n"
            "How else can I help you today with our tours, prices or schedules? 😊"),
        pt=("✅ Seu atendimento com o assessor já está encerrado. Muito obrigado por confiar na Texeira Travel! 🙌\n\n"
            "Como posso ajudar você hoje com nossos passeios, preços ou horários? 😊"),
    )


def close_requested_by_customer(text):
    """Reconoce únicamente solicitudes EXPLÍCITAS del cliente para finalizar la atención
    humana o volver al bot (nunca un simple 'gracias', para no cortar al asesor a mitad de charla).
    """
    if not text:
        return False
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower()) if not unicodedata.combining(c))
    q = re.sub(r'^[^a-z0-9]+', '', normalized).strip(' .!¿?¡\'"')
    if not q:
        return False

    neg_close = [
        r'\b(no|todavia\s+no|aun\s+no|nunca|jamas)\s+(quiero\s+|deseo\s+)?(finaliz\w*|termin\w*|cerr\w*|cancel\w*|volv\w*|regres\w*)\b',
        r'\b(do\s+not|don\'?t|not\s+yet|never)\s+(want\s+to\s+)?(end|finish|close|cancel|return)\b',
        r'\b(nao|ainda\s+nao|nunca)\s+(quero\s+|desejo\s+)?(encerr\w*|finaliz\w*|fech\w*|cancel\w*|volt\w*)\b',
    ]
    if any(re.search(pat, q) for pat in neg_close):
        return False

    exact_close = {
        'finalizar conversacion', 'finalizar la conversacion',
        'finalizar atencion', 'finalizar la atencion',
        'finalizar consulta', 'finalizar la consulta', 'finalizar chat',
        'terminar conversacion', 'terminar atencion', 'terminar consulta',
        'cerrar conversacion', 'cerrar atencion', 'cerrar consulta', 'cerrar solicitud',
        'cancelar solicitud', 'cancelar asesor', 'cancelar atencion',
        'volver al bot', 'volver al asistente', 'regresar al bot', 'regresar al asistente',
        'continuar con el bot', 'seguir con el bot',
        'end conversation', 'finish conversation', 'close conversation', 'end chat',
        'end session', 'close request', 'cancel request', 'cancel advisor',
        'return to bot', 'back to bot', 'back to assistant', 'continue with bot',
        'encerrar conversa', 'finalizar conversa', 'fechar conversa',
        'encerrar atendimento', 'finalizar atendimento', 'fechar solicitacao',
        'cancelar solicitacao', 'cancelar assessor',
        'voltar ao bot', 'voltar para o bot', 'voltar ao assistente', 'continuar com o bot',
    }
    if q in exact_close:
        return True

    close_patterns = [
        r'\b(quiero\s+|deseo\s+|quisiera\s+|por\s+favor\s+|puedes\s+)?(finalizar|terminar|cerrar|cancelar|dar\s+por\s+finalizada|dar\s+por\s+terminada)\s+(la\s+|mi\s+|esta\s+|el\s+)?(conversacion|atencion|consulta|solicitud|chat|asesor\w*)(\s+humana?|\s+de\s+reserva)?\b',
        r'\b(quiero\s+|deseo\s+|quisiera\s+)?(volver|regresar|continuar|seguir)\s+(con\s+|a\s+|al\s+)(el\s+)?(bot|asistente|chat\s+automatico|ia)\b',
        r'\b(ya\s+(me\s+atendieron|fue\s+resuelt[oa]|resolvieron\s+mi\s+(duda|consulta)|quedo\s+resuelt[oa]))\b',
        r'\b(i\s+want\s+to\s+|please\s+|can\s+you\s+)?(end|finish|close|cancel)\s+(the\s+|my\s+|this\s+)?(conversation|chat|session|support|request|advisor)\b',
        r'\b(i\s+want\s+to\s+|please\s+)?(return|go\s+back|switch\s+back|continue)\s+(to|with)\s+(the\s+)?(bot|virtual\s+assistant|assistant|ai)\b',
        r'\b(quero\s+|desejo\s+|gostaria\s+de\s+|por\s+favor\s+)?(encerrar|finalizar|fechar|cancelar)\s+(a\s+|minha\s+|esta\s+|o\s+)?(conversa|atendimento|consulta|solicitacao|chat|assessor\w*)\b',
        r'\b(quero\s+|desejo\s+)?(voltar|retornar|continuar)\s+(ao|para\s+o|com\s+o)\s+(bot|assistente|ia)\b',
        r'\b(ja\s+fui\s+atendid[oa]|minha\s+duvida\s+foi\s+resolvida)\b',
    ]
    return any(re.search(pat, q) for pat in close_patterns)


def close_by_customer(user_id, channel, language=None, user_text=''):
    """Permite que el cliente finalice su solicitud abierta ('pending' o 'in_progress')
    y reactive de inmediato al bot IA sin perder el contexto conversacional.
    """
    lang = language if language in ('es', 'en', 'pt') else None
    if not lang:
        detect = _HOOKS.get('detect_language')
        detected = detect(user_text) if (detect and user_text) else None
        lang = detected if detected in ('es', 'en', 'pt') else _customer_language(user_id)

    closed_row = None
    prev_status = None
    prev_advisor = ''
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        lock = ' FOR UPDATE' if is_postgres() else ''
        row = conn.execute(
            "SELECT * FROM requests WHERE user_id=? AND channel=? AND status!='closed'" + lock,
            (user_id, channel),
        ).fetchone()
        if row:
            row = dict(row)
            prev_status = row.get('status')
            prev_advisor = (row.get('advisor') or '').strip()
            prev_note = (row.get('note') or '').strip()
            advisor_val = prev_advisor or 'Cliente (autocierre)'
            tag = '[Finalizado por el cliente]'
            note_val = f'{prev_note}\n{tag}'.strip() if (prev_note and tag not in prev_note) else (prev_note or tag)
            changed = conn.execute(
                "UPDATE requests SET status='closed', advisor=?, note=?, updated_at=? WHERE id=? AND status=?",
                (advisor_val, note_val, now, row['id'], prev_status),
            )
            if changed.rowcount == 1:
                closed_row = row

    reply = customer_closing_message(prev_advisor, prev_status if closed_row else None, lang)
    recorded_user_text = (user_text or '').strip() or _request_message(
        lang, es='Finalizar atención', en='End conversation', pt='Encerrar conversa',
    )
    ticket_meta = {'handoff_id': closed_row['id']} if closed_row else {}
    _history_append(user_id, 'human', recorded_user_text,
                    dict(ticket_meta, event='customer_close_request'))
    _history_append(user_id, 'ai', reply,
                    dict(ticket_meta, author='system', event='handoff_closed_by_customer'))
    return {
        'closed': closed_row is not None,
        'ticket_id': closed_row['id'] if closed_row else None,
        'previous_status': prev_status if closed_row else 'closed',
        'advisor': prev_advisor,
        'language': lang,
        'response': reply,
    }


def conversation_since(user_id, created_at, ticket_id=None, limit=30):
    """Mensajes desde la creación del ticket, etiquetados por autor, para el panel."""
    get_hist = _HOOKS.get('get_history')
    if not get_hist:
        return []
    start = _parse_ts(created_at)
    # El turno que abrió la solicitud se guarda segundos antes de crear el ticket.
    since = start.timestamp() - 5 if start else None
    out = []
    try:
        messages = get_hist(user_id)
    except Exception:
        return []
    for m in messages:
        ts = m.get('timestamp')
        if since is not None and isinstance(ts, (int, float)) and ts < since:
            continue
        meta = m.get('metadata') or {}
        if ticket_id and meta.get('handoff_id') and meta.get('handoff_id') != ticket_id:
            continue
        if m.get('role') == 'human':
            author = 'cliente'
        elif meta.get('author') == 'advisor':
            author = 'asesor'
        else:
            author = 'bot'
        out.append({'author': author, 'content': m.get('content', ''), 'timestamp': ts,
                    'advisor': meta.get('advisor', '')})
    return out[-limit:]


def requested(text):
    if close_requested_by_customer(text):
        return False
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    q = normalized.strip(' .!¿?¡\'"')

    # Una recomendación citada no es una solicitud de transferencia.
    if re.search(r'\b(te recomiendo|i recommend|we recommend|recomendo|recomendamos)\b', q):
        return False
    if re.search(r'^(talk|speak) to (an? )?(agent|advisor).*\bfor (details|information|info)\b', q):
        return False
    if re.search(r'^se\s+(?:eu\s+)?(?:precisar|quiser|necessitar)\b', q):
        return False

    # 1. Comprobar negación explícita hacia la atención humana:
    # "no quiero hablar con un asesor", "no deseo asesor", "no me llamen", "i don't want to speak to an advisor", etc.
    negation_patterns = [
        r'\b(no|tampoco|nunca|jamas)\s+(quiero|deseo|necesito|quisiera|busco|voy\s+a|pienso)\s+(hablar|conversar|comunicar|contactar|llamar)?.*?\b(asesor\w*|agente\w*|persona\w*|humano\w*|operador\w*|alguien|advisor\w*)\b',
        r'\b(no|tampoco|nunca|jamas)\s+(quiero|deseo|necesito|quisiera)\s+(un\s+|una\s+|algun\s+|alguna\s+)?(asesor\w*|agente\w*|persona\w*|humano\w*|advisor\w*)\b',
        r'\b(no|sin|tampoco|nunca|jamas)\s+(hablar|conversar|comunicar|comunicarme|contactar|contactarme|llamar|transferir|derivar|pasar|pasarme|conectar|conectarme)\s+(con\s+|a\s+)?.*?\b(asesor\w*|agente\w*|persona\w*|humano\w*|operador\w*|advisor\w*)\b',
        r'\b(no|tampoco)\s+(me\s+)?(llamen|contacten|comuniquen|transfieran|deriven|pasen)\b',
        r'\b(no|sin)\s+(un\s+|una\s+)?(asesor\w*|agente\w*|advisor\w*)\b',
        r'\b(do\s+not|don\'?t|never)\s+(want|need|wish)\s+(to\s+)?(speak|talk|chat|contact|call)?.*?\b(agent\w*|advisor\w*|human\w*|person\w*|representative\w*)\b',
        r'\b(do\s+not|don\'?t)\s+(call|contact|transfer|connect)\s+me\b',
        r'\b(without\s+an?\s+(agent|advisor|human))\b',
        # Português: recusar atendimento ou reserva não registra uma solicitação.
        r'\b(?:nao|nunca)\s+(?:quero|desejo|preciso|gostaria|vou|pretendo)\s+(?:de\s+)?(?:me\s+)?(?:(?:falar|conversar|consultar|contatar|contactar|comunicar|solicitar|pedir|fazer)\s+)?(?:(?:com|a|ao|de)\s+)?(?:um\s+|uma\s+|o\s+|a\s+)?(?:assessor\w*|agente\w*|pessoa\w*|humano\w*|atendente\w*|representante\w*|reservar|reserva)\b',
        r'\b(?:nao|sem)\s+(?:falar|conversar|consultar|contatar|contactar|conectar|transferir)\s+(?:(?:com|a|ao)\s+)?(?:um\s+|uma\s+|o\s+|a\s+)?(?:assessor\w*|agente\w*|pessoa\w*|humano\w*|atendente\w*|representante\w*)\b',
        r'\b(?:nao|sem)\s+(?:um\s+|uma\s+)?(?:assessor\w*|agente\w*|atendente\w*)\b',
        r'\bnao\s+(?:me\s+)?(?:ligue|liguem|contate|contatem|contacte|contactem|transfira|transfiram|conecte|conectem|solicitar|reservar)\b',
    ]
    for neg_pat in negation_patterns:
        if re.search(neg_pat, q):
            return False

    exact_phrases = {
        'asesor', 'asesora', 'asesores',
        'advisor', 'advisors', 'agent', 'agents', 'human agent', 'human advisor',
        'hablar con un asesor', 'hablar con una asesora', 'hablar con un agente',
        'hablar con una persona', 'hablar con un humano', 'hablar con alguien',
        'quiero hablar con un asesor', 'quiero hablar con una asesora',
        'quiero hablar con una persona', 'quiero hablar con un humano', 'quiero hablar con alguien',
        'necesito un asesor', 'necesito una asesora', 'necesito un agente',
        'necesito hablar con un asesor', 'necesito hablar con una persona',
        'solicitar asesor', 'solicitar agente', 'atencion humana', 'ayuda humana',
        'atencion de una persona', 'ayuda de una persona',
        'comunicame con un asesor', 'comunicarme con un asesor',
        'deseo contactar a un asesor', 'contactar a un asesor',
        'solicitar reserva', 'solicitar una reserva', 'hacer una reserva', 'hacer reserva',
        'quiero reservar', 'deseo reservar', 'quisiera reservar', 'reservar', 'reservar tour',
        'speak to an agent', 'i want to speak to an agent',
        'speak to an advisor', 'i want to speak to an advisor',
        'talk to an agent', 'talk to an advisor', 'talk to a human', 'speak to a human', 'speak to a person',
        'talk to a person', 'i want to talk to a person',
        'human support', 'human help', 'i need human help', 'i need an advisor',
        'request reservation', 'request a reservation', 'book now', 'book tour', 'book a tour',
        'i want to book', 'booking request',
        'assessor', 'assessora', 'atendente', 'consultar assessor',
        'falar com um assessor', 'falar com uma assessora', 'falar com um atendente',
        'quero falar com um assessor', 'preciso de um assessor', 'solicitar assessor',
        'atendimento humano', 'ajuda humana', 'solicitar uma reserva', 'fazer uma reserva',
    }
    if q in exact_phrases:
        return True

    patterns = [
        # Hablar / comunicarse / contactar con/a asesor / persona / humano / agente / advisor
        r'\b(quiero|quisiera|deseo|necesito|puedo|busco|favor\s+de|por\s+favor)?\s*(hablar|conversar|comunicarme|comunicame|contactar|contactarme|conectar|conectame|pasarme|pasame)\s+(con\s+|a\s+)?(un\s+|una\s+|algun\s+|alguna\s+)?(asesor\w*|persona\w*|humano\w*|agente\w*|operador\w*|advisor\w*|alguien)\b',
        # Solicitar que le llamen o contacten directamente
        r'\b(quiero\s+que\s+me\s+llamen|pueden\s+llamarme|me\s+pueden\s+llamar|favor\s+de\s+llamarme|llamenme)\b',
        r'\b(pueden\s+contactarme|me\s+pueden\s+contactar|quiero\s+que\s+me\s+contacten|contactenme)\b',
        # Solicitudes de reserva explícitas
        r'\b(solicitar|pedir|hacer|quiero|quisiera|deseo|necesito)\s+(una\s+)?reserva(\s+de|\s+para|\s+sobre|\s+del)?\b',
        r'\b(solicitud\s+de\s+reserva|quiero\s+reservar|deseo\s+reservar|quisiera\s+reservar|como\s+reservo|para\s+reservar)\b',
        # Ayuda / atención humana
        r'\b(ayuda|atencion|soporte|asistencia)\s+(humana?|de\s+una\s+persona|personalizada)\b',
        # En inglés
        r'\b(human\s+support|human\s+help|human\s+assistance)\b',
        r'\b(i\s+want\s+to|i\s+need\s+to|can\s+i|i\s+need|please|i\s+would\s+like\s+to)?\s*(speak|talk|chat|contact)\s*(to|with)?\s*(a\s+|an\s+)?(human|person|agent|advisor|representative)\b',
        r'\b(call\s+me|please\s+call\s+me|can\s+you\s+call\s+me)\b',
        r'\b(connect\s+me\s+(with|to)\s+(an?\s+)?(agent|advisor|human|representative))\b',
        r'\b(request\s+(a\s+)?reservation|i\s+(want|would\s+like|need)\s+to\s+book|book\s+now|booking\s+request)\b',
        # Português, incluindo os textos canônicos dos botões :pt.
        r'\b(?:quero|gostaria\s+de|desejo|preciso|posso|por\s+favor)?\s*(?:falar|conversar|consultar|contatar|contactar)\s+(?:(?:com|a|ao)\s+)?(?:um\s+|uma\s+)?(?:assessor\w*|atendente\w*|agente\w*|pessoa\w*|humano\w*|representante\w*)\b',
        r'\b(?:preciso|quero|desejo)\s+(?:de\s+)?(?:um\s+|uma\s+)?(?:assessor\w*|atendente\w*)\b',
        r'\b(?:atendimento|ajuda|assistencia|suporte)\s+human[oa]\b',
        r'\b(?:solicitar|pedir|fazer)\s+(?:uma\s+)?reserva\b',
        r'\b(?:quero|desejo|gostaria\s+de)\s+reservar\b',
    ]
    for pat in patterns:
        if re.search(pat, q):
            return True
    return False



def get_advisor_whatsapp_phone(ns=None):
    """
    Obtiene el número telefónico de WhatsApp del asesor humano.
    Prioridad:
    1. ns.get('ADVISOR_WHATSAPP_PHONE') o ns.get('ADVISOR_PHONE')
    2. Base de datos (agency_settings: 'advisor_whatsapp_phone' o 'advisor_phone')
    3. Variable de entorno ADVISOR_WHATSAPP_PHONE o ADVISOR_PHONE
    4. Si está vacío, 'none', 'false', '0' o 'disabled', retorna None (enlace deshabilitado).
    5. Por defecto, retorna '51953767860' (número oficial registrado en documentos de Texeira Travel).
    """
    val = None
    if isinstance(ns, dict):
        val = ns.get('ADVISOR_WHATSAPP_PHONE') or ns.get('ADVISOR_PHONE')
    if not val:
        try:
            from catalog_service import get_agency_setting
            val = get_agency_setting('advisor_whatsapp_phone') or get_agency_setting('advisor_phone')
        except Exception:
            val = None
    if not val:
        val = os.getenv('ADVISOR_WHATSAPP_PHONE') or os.getenv('ADVISOR_PHONE')

    if val is not None:
        s = str(val).strip()
        if s.lower() in {'none', 'false', '0', 'disabled', 'off', 'null', ''}:
            return None
        digits = re.sub(r'\D', '', s)
        if not digits:
            return None
        if len(digits) == 9 and digits.startswith('9'):
            return f"51{digits}"
        return digits

    return '51953767860'


def get_advisor_whatsapp_link_text(language='es', ns=None):
    """
    Construye el texto con enlace directo a WhatsApp para el turista.
    Si el número está deshabilitado o vacío, retorna cadena vacía.
    """
    phone = get_advisor_whatsapp_phone(ns)
    if not phone:
        return ""
    link = f"https://wa.me/{phone}"
    if language == 'en':
        return f"\n\n👉 You can also contact our advisor directly on WhatsApp: {link}"
    elif language == 'pt':
        return f"\n\n👉 Você também pode falar diretamente com nosso assessor no WhatsApp: {link}"
    else:
        return f"\n\n👉 También puedes coordinar directamente con nuestro asesor en WhatsApp: {link}"


def notify_advisor(row, send_fn=None, advisor_phone=None):
    """
    Envía una notificación push vía WhatsApp al número del asesor humano
    cuando se registra una nueva solicitud de derivación (handoff).
    """
    phone = advisor_phone or get_advisor_whatsapp_phone()
    if not phone:
        print(f"[ADVISOR NOTIFY] Aviso no enviado para ticket {row.get('id')}: número de asesor ausente o deshabilitado.")
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

    # Importación circular eliminada: app.py importa handoff_support durante
    # su inicialización, lo que causaría ImportError. Si send_fn no se inyectó
    # como parámetro, se registra el aviso en el log y se retorna False.
    print(f"[ADVISOR NOTIFY] send_fn no disponible para ticket {row.get('id')}. "
          "Configura ADVISOR_WHATSAPP_PHONE e inyecta send_fn desde app.py.")
    return False


def _request_message(language, *, es, en, pt):
    """Preserva o idioma do cliente sem alterar o estado da solicitação."""
    return {'es': es, 'en': en, 'pt': pt}.get(language, es)


def _update_request_history(ns, user_id, response):
    history = ns.get('conversation_history', {}).get(user_id, [])
    if history and history[-1].get('role') == 'ai':
        if 'update_last_history_response' in ns:
            ns['update_last_history_response'](user_id, response)
        else:
            history[-1]['content'] = response


def apply_request(ns, result, user_id, channel, question):
    if not result.get('handoff_requested'): return result
    result=dict(result)
    language=result.get('handoff_language', 'es')
    try:
        get_hist = ns.get('get_history', lambda uid: []) if isinstance(ns, dict) else getattr(ns, 'get_history', lambda uid: [])
        history = get_hist(user_id)
        # Identificar si es una solicitud de reserva y tour seleccionado
        is_booking = bool(re.search(r'\b(reserva\w*|reserv|book\w*)\b', question, re.IGNORECASE))
        tour_name = ""
        try:
            from trial_support import detect_entity_from_question
            eid = detect_entity_from_question(question)
            if not eid or eid == "unknown":
                for h in reversed(history[:-2]):
                    if h.get('role') == 'human':
                        cand = detect_entity_from_question(h.get('content', ''))
                        if cand and cand != 'unknown':
                            eid = cand
                            break
            if eid and eid != "unknown":
                from catalog_service import get_tour
                t_data = get_tour(eid)
                if t_data and t_data.get('name'):
                    tour_name = t_data['name']
                elif 'support' in ns and 'CATALOG' in ns['support'] and eid in ns['support']['CATALOG']:
                    tour_name = ns['support']['CATALOG'][eid].get('name', eid)
        except Exception:
            pass

        from catalog_service import is_deactivated_tour, is_sold_out_tour
        if is_booking and eid and is_deactivated_tour(eid):
            disp_name = tour_name or eid
            result['response'] = _request_message(
                language,
                es=f"*{disp_name}* no figura actualmente en nuestro catálogo activo (no se encuentra disponible). Puedes explorar otros tours o consultar este destino con un asesor.",
                en=f"*{disp_name}* is not currently in our active catalog (not available). You can explore other tours or consult this destination with an advisor.",
                pt=f"*{disp_name}* não está disponível no nosso catálogo ativo. Você pode explorar outros passeios ou consultar este destino com um assessor.",
            )
            result.update(route='evidence_inactive_tour', response_route='evidence_inactive_tour', entity_id=eid, resolved_autonomously=False, handoff_registered=False)
            _update_request_history(ns, user_id, result['response'])
            return result

        is_sold_out = False
        is_date_sold_out = False
        is_date_limited = False
        parsed_booking_date = None
        date_formatted = ""
        date_notes = ""
        if is_booking and eid:
            try:
                from catalog_service import is_sold_out_tour, parse_date_from_query, get_tour_availability_on_date, format_date_localized
                parsed_booking_date = parse_date_from_query(question)
                if not parsed_booking_date and history:
                    for h in reversed(history[:-1]):
                        if h.get('role') == 'human':
                            cand_d = parse_date_from_query(h.get('content', ''))
                            if cand_d:
                                parsed_booking_date = cand_d
                                break

                if parsed_booking_date:
                    date_info = get_tour_availability_on_date(eid, parsed_booking_date)
                    date_formatted = format_date_localized(parsed_booking_date, language)
                    date_notes = str(date_info.get("notes") or "").strip()
                    if date_info.get("status") == "sold_out":
                        is_date_sold_out = True
                    elif date_info.get("status") == "limited":
                        is_date_limited = True

                is_sold_out = bool(is_sold_out_tour(eid)) or is_date_sold_out
            except Exception:
                is_sold_out = False

        ticket_question = question
        if is_booking:
            if is_date_sold_out and parsed_booking_date:
                prefix = f"[Reserva - FECHA AGOTADA: {parsed_booking_date.isoformat()}"
            elif is_date_limited and parsed_booking_date:
                prefix = f"[Reserva - FECHA LIMITADA: {parsed_booking_date.isoformat()}"
            elif is_sold_out:
                prefix = "[Reserva - AGOTADO"
            else:
                prefix = "[Reserva"
            # Nota interna del bloqueo: visible solo para el asesor en el ticket.
            if (is_date_sold_out or is_date_limited) and date_notes:
                prefix += f" (Nota: {date_notes[:120]})"

            if tour_name and tour_name.lower() not in question.lower():
                ticket_question = f"{prefix} - {tour_name}] {question}"
            elif not question.lower().startswith("[reserva"):
                ticket_question = f"{prefix}] {question}"

        row, created = create_request(user_id, channel, ticket_question, history[:-2])
        result.update(handoff_id=row['id'], handoff_status=row['status'], handoff_registered=True)
        # Verificar si las notificaciones al asesor están habilitadas en BD o ns
        notifications_enabled = False
        try:
            from catalog_service import get_agency_setting
            db_notif = get_agency_setting('advisor_notifications_enabled')
            if db_notif is not None:
                notifications_enabled = str(db_notif).lower() in ('true', '1', 'yes', 'on')
            elif isinstance(ns, dict):
                notifications_enabled = bool(ns.get('ADVISOR_NOTIFICATIONS_ENABLED', False))
        except Exception:
            notifications_enabled = bool(ns.get('ADVISOR_NOTIFICATIONS_ENABLED', False)) if isinstance(ns, dict) else False

        if created and channel in {'whatsapp', 'messenger'} and notifications_enabled:
            send_fn = ns.get('send_whatsapp_message')
            advisor_phone = get_advisor_whatsapp_phone(ns)
            try:
                notify_advisor(row, send_fn=send_fn, advisor_phone=advisor_phone)
            except Exception as e:
                print(f"[ADVISOR NOTIFY] Error silencioso al notificar asesor: {e}")

        link_txt_es = get_advisor_whatsapp_link_text('es', ns)
        link_txt_en = get_advisor_whatsapp_link_text('en', ns)
        link_txt_pt = get_advisor_whatsapp_link_text('pt', ns)

        if is_booking:
            if created:
                if is_date_sold_out and parsed_booking_date:
                    t_disp = tour_name or 'este tour'
                    result['response'] = _request_message(
                        language,
                        es=f"Registré tu solicitud sobre {t_disp} para el {date_formatted}. Actualmente esa fecha figura con cupos agotados en el catálogo oficial, pero nuestro asesor verificará si existen liberaciones de última hora o cupos en lista de espera. Tu reserva aún no está confirmada.{link_txt_es}",
                        en=f"I registered your request regarding {t_disp} for {date_formatted}. That date is currently marked sold out in the official catalog, but our advisor will check for last-minute releases or waitlist spots. Your reservation is not yet confirmed.{link_txt_en}",
                        pt=f"Registrei sua solicitação sobre {t_disp} para {date_formatted}. Essa data consta com vagas esgotadas no catálogo oficial, mas nosso assessor verificará se há liberações de última hora ou lista de espera. Sua reserva ainda não está confirmada.{link_txt_pt}",
                    )
                elif is_date_limited and parsed_booking_date:
                    t_disp = tour_name or 'este tour'
                    result['response'] = _request_message(
                        language,
                        es=f"Registré tu solicitud sobre {t_disp} para el {date_formatted}. Esa fecha cuenta con cupos limitados y alta demanda; nuestro asesor te atenderá a la brevedad para verificar disponibilidad y coordinar tu reserva. Tu reserva aún no está confirmada.{link_txt_es}",
                        en=f"I registered your request regarding {t_disp} for {date_formatted}. That date has limited spots and high demand; our advisor will assist you shortly to verify availability and secure your reservation. Your reservation is not yet confirmed.{link_txt_en}",
                        pt=f"Registrei sua solicitação sobre {t_disp} para {date_formatted}. Essa data conta com vagas limitadas e alta procura; nosso assessor atenderá você em breve para verificar disponibilidade e coordinar sua reserva. Sua reserva ainda não está confirmada.{link_txt_pt}",
                    )
                elif is_sold_out:
                    t_disp = tour_name or 'este tour'
                    result['response'] = _request_message(
                        language,
                        es=f"Registré tu solicitud sobre {t_disp}. Actualmente figura sin cupos disponibles en el catálogo oficial, pero nuestro asesor verificará si existen liberaciones de última hora o cupos en lista de espera. Tu reserva aún no está confirmada.{link_txt_es}",
                        en=f"I registered your request regarding {t_disp}. It is currently marked with no spots available in the catalog, but our advisor will check for last-minute releases or waitlist spots. Your reservation is not yet confirmed.{link_txt_en}",
                        pt=f"Registrei sua solicitação sobre {t_disp}. Atualmente consta sem vagas disponíveis no catálogo, mas nosso assessor verificará si há liberações de última hora ou lista de espera. Sua reserva ainda não está confirmada.{link_txt_pt}",
                    )
                elif tour_name:
                    result['response'] = _request_message(
                        language,
                        es=f"Registré tu solicitud sobre {tour_name}. Está pendiente de atención por un asesor; tu reserva aún no está confirmada.{link_txt_es}",
                        en=f"I registered your request regarding {tour_name}. It is pending review by an advisor; your reservation is not yet confirmed.{link_txt_en}",
                        pt=f"Registrei sua solicitação sobre {tour_name}. Ela aguarda atendimento por um assessor; sua reserva ainda não está confirmada.{link_txt_pt}",
                    )
                else:
                    result['response'] = _request_message(
                        language,
                        es=f"Registré tu solicitud de reserva. Está pendiente de atención por un asesor; tu reserva aún no está confirmada.{link_txt_es}",
                        en=f"I registered your reservation request. It is pending review by an advisor; your reservation is not yet confirmed.{link_txt_en}",
                        pt=f"Registrei sua solicitação de reserva. Ela aguarda atendimento por um assessor; sua reserva ainda não está confirmada.{link_txt_pt}",
                    )
            else:
                if row['status'] == 'in_progress':
                    result['response'] = _request_message(
                        language,
                        es=f"Tu solicitud sobre {tour_name or 'tu reserva'} (Ticket {row['id']}) ya está en atención por un asesor. Tu reserva aún no está confirmada.",
                        en=f"Your request regarding {tour_name or 'your reservation'} (Ticket {row['id']}) is already being attended by an advisor. Your reservation is not yet confirmed.",
                        pt=f"Sua solicitação sobre {tour_name or 'sua reserva'} (Ticket {row['id']}) já está em atendimento por um assessor. Sua reserva ainda não está confirmada.",
                    )
                else:
                    result['response'] = _request_message(
                        language,
                        es=f"Ya tienes una solicitud registrada (Ticket {row['id']}) pendiente de atención por un asesor. Tu reserva aún no está confirmada; te atenderemos a la brevedad.{link_txt_es}",
                        en=f"You already have a registered request (Ticket {row['id']}) pending review by an advisor. Your reservation is not yet confirmed; we will assist you shortly.{link_txt_en}",
                        pt=f"Você já tem uma solicitação registrada (Ticket {row['id']}) aguardando atendimento por um assessor. Sua reserva ainda não está confirmada; você pode continuar consultando o bot.{link_txt_pt}",
                    )
        else:
            if created:
                result['response'] = _request_message(
                    language,
                    es=f"Tu solicitud {row['id']} está registrada y pendiente de atención humana. "
                    f"Aún no ha sido atendida. Puedes seguir haciendo consultas al bot.{link_txt_es}",
                    en=f"Your request {row['id']} is registered and pending human attention. "
                    f"It has not been handled yet. You can continue asking the bot questions.{link_txt_en}",
                    pt=f"Sua solicitação {row['id']} está registrada e aguarda atendimento humano. "
                    f"Ela ainda não foi atendida. Você pode continuar consultando o bot.{link_txt_pt}",
                )
            else:
                if row['status'] == 'in_progress':
                    result['response'] = _request_message(
                        language,
                        es=f"Tu solicitud {row['id']} ya está en atención. Aún no está cerrada.",
                        en=f"Your request {row['id']} is being handled. It is not closed yet.",
                        pt=f"Sua solicitação {row['id']} já está em atendimento. Ela ainda não foi encerrada.",
                    )
                else:
                    result['response'] = _request_message(
                        language,
                        es=f"Ya tienes una solicitud registrada ({row['id']}) pendiente de atención humana. "
                        f"Aún no ha sido atendida. Puedes seguir haciendo consultas al bot.{link_txt_es}",
                        en=f"You already have a registered request ({row['id']}) pending human attention. "
                        f"It has not been handled yet. You can continue asking the bot questions.{link_txt_en}",
                        pt=f"Você já tem uma solicitação registrada ({row['id']}) aguardando atendimento humano. "
                        f"Ela ainda não foi atendida. Você pode continuar consultando o bot.{link_txt_pt}",
                    )
    except (sqlite3.Error, Exception):
        result['response']=_request_message(
            language,
            es='No pude registrar la solicitud. Intenta nuevamente o usa los contactos de la agencia.',
            en='I could not register the request. Please try again or use the agency contact details.',
            pt='Não consegui registrar a solicitação. Tente novamente ou use os contatos da agência.',
        )
        result.update(handoff_registered=False,handoff_status='registration_failed')
    result['resolved_autonomously']=False
    # Mantener exactamente la respuesta final en el historial.
    _update_request_history(ns, user_id, result['response'])
    return result


def install(ns):
    # Acceso a la memoria compartida sin importar app.py (evita importación circular).
    _HOOKS.update(
        add_to_history=ns.get('add_to_history'),
        get_history=ns.get('get_history'),
        detect_language=ns.get('detect_language'),
    )
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
                elif lang == 'pt':
                    if 'assessor' not in response_text.lower():
                        result['response'] += '\nEscreva \U0001f449 *assessor* para falar com nossa equipe na agência.'
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
        lang = ns.get('detect_language', lambda q: 'es')(question)
        text=_request_message(
            lang,
            es='Registrando solicitud de atención humana.',
            en='Registering a request for human assistance.',
            pt='Registrando uma solicitação de atendimento humano.',
        )
        if 'add_history_turn' in ns:
            ns['add_history_turn'](user_id, question, text)
        else:
            ns['add_to_history'](user_id,'human',question)
            ns['add_to_history'](user_id,'ai',text)
        return dict(response=text,is_fallback=False,is_predefined=True,is_escalation=False,
                    resolved_autonomously=False,needs_agency_confirmation=True,
                    handoff_requested=True,handoff_language=lang,
                    response_route='human_request',route='human_request')
    ns['rag_chain']=chain
    from auth_middleware import panel_csrf_token
    csrf=panel_csrf_token('handoff')
    app=ns['app']

    def local(request):
        if os.getenv('ALLOW_CLOUD_RUN') or os.getenv('K_SERVICE'):
            return True
        return request.client is not None and request.client.host in {'127.0.0.1','::1','testclient'}

    @app.get('/handoffs',response_class=HTMLResponse)
    async def panel(request:Request):
        if not local(request): return HTMLResponse('Acceso local requerido',status_code=403)
        from admin_theme import decorate
        return HTMLResponse(decorate(PANEL.replace('__CSRF__',csrf), 'handoffs'), headers={'Cache-Control': 'no-store'})

    @app.get('/handoffs/data')
    async def data(request:Request):
        if not local(request): return JSONResponse({'error':'Acceso local requerido'},status_code=403)
        with connection() as conn:
            rows=[dict(r) for r in conn.execute('SELECT * FROM requests ORDER BY created_at DESC LIMIT 200')]
        for row in rows:
            if row.get('status') != 'closed':
                # Conversación en vivo: mensajes del cliente, del asesor y del bot desde la solicitud.
                row['conversation'] = conversation_since(row['user_id'], row.get('created_at'), ticket_id=row.get('id'))
                row['bot_paused'] = row.get('status') == 'in_progress' and row.get('channel') in PAUSE_CHANNELS
        return JSONResponse(rows)

    @app.post('/handoffs/{ticket}/message')
    async def message(ticket:str,request:Request):
        if not local(request) or request.headers.get('X-Handoff-CSRF')!=csrf:
            return JSONResponse({'error':'Solicitud no autorizada'},status_code=403)
        try:
            body=await request.json()
            send_advisor_message(ticket,str(body.get('advisor','')),str(body.get('text','')))
            return JSONResponse({'ok':True,'message_sent':True})
        except AdvisorDeliveryError as exc:
            return JSONResponse({'ok':False,'message_sent':False,'error':str(exc)},status_code=502)
        except (ValueError,TypeError,AttributeError) as exc:
            return JSONResponse({'error':str(exc)},status_code=400)

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
            notify_customer=body.get('notify_customer',False)
            send_closing=body.get('send_closing',False)
            outcome={}
            msg_sent=update_request(ticket,status,advisor,note,send_to_customer,
                                    notify_customer=notify_customer,send_closing=send_closing,outcome=outcome)
            return JSONResponse({'ok':True, 'message_sent': msg_sent,
                                 'customer_notified': outcome.get('customer_notified', False),
                                 'closing_sent': outcome.get('closing_sent', False)})
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
  .live-chat { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; margin: 12px 0; max-height: 360px; overflow-y: auto; }
  .msg { margin: 8px 0; padding: 8px 12px; border-radius: 10px; max-width: 85%; }
  .msg p { margin: 4px 0 0; white-space: pre-wrap; font-size: 14px; }
  .msg-who { font-size: 12px; font-weight: 700; color: var(--muted); }
  .msg-cliente { background: #ffffff; border: 1px solid #e2e8f0; }
  .msg-asesor { background: #dcfce7; margin-left: auto; }
  .msg-bot { background: #e0f2fe; margin-left: auto; }
  .pause-banner { background: #fef3c7; color: #92400e; border-radius: 8px; padding: 10px 12px; font-size: 14px; font-weight: 600; }
  .btn-send { background: var(--primary); color: white; }
  .btn-send:hover { background: var(--primary-hover); }
  fieldset { border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px 14px 14px; margin: 14px 0 0; }
  legend { font-weight: 700; font-size: 14px; color: #334155; padding: 0 6px; }
</style>
<header>
  <div>
    <h1>🛎️ Consola de Asesores — Texeira Travel</h1>
    <p style="margin: 4px 0 0; color: var(--muted); font-size: 14px;">Gestión de consultas escaladas y atención humana por WhatsApp</p>
  </div>
  <div>
    <button id="refresh" class="btn-refresh">🔄 Actualizar</button>
  </div>
</header>
<div class="admin-toolbar" aria-label="Filtrar solicitudes">
<button data-state="pending" aria-pressed="true">Pendientes</button>
<button data-state="in_progress" aria-pressed="false">En atención</button>
<button data-state="closed" aria-pressed="false">Cerradas</button>
<button data-state="all" aria-pressed="false">Todas</button>
<input id="ticketSearch" type="search" aria-label="Buscar solicitud" placeholder="Buscar cliente, consulta o ticket">
</div>
<p id="visibleCount" role="status"></p>
<p id="feedback" role="status"></p>
<main id="list"></main>
<script>
const stateNames = { pending: 'Pendiente', in_progress: 'En atención', closed: 'Cerrada' };
const stateBadges = { pending: 'badge-pending', in_progress: 'badge-in_progress', closed: 'badge-closed' };
let selectedState = 'pending';
function filterTickets(){
  const query = document.getElementById('ticketSearch').value.toLocaleLowerCase().trim();
  let count = 0;
  document.querySelectorAll('.ticket').forEach(ticket => {
    ticket.hidden = (selectedState !== 'all' && ticket.dataset.state !== selectedState) || !ticket.dataset.search.includes(query);
    if (!ticket.hidden) count++;
  });
  document.getElementById('visibleCount').textContent = count ? `${count} solicitudes · Abre una para consultar el historial y atenderla.` : 'No hay solicitudes con estos filtros.';
}
document.querySelectorAll('[data-state]').forEach(button => button.onclick = () => {
  selectedState = button.dataset.state;
  document.querySelectorAll('[data-state]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
  filterTickets();
});
document.getElementById('ticketSearch').oninput = filterTickets;
const elem = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

async function load(keepOpenId) {
  const list = document.getElementById('list');
  try {
    const r = await fetch('/handoffs/data');
    if (!r.ok) throw Error('No se pudieron cargar las solicitudes.');
    const rows = await r.json();
    list.replaceChildren();
    if (!rows.length) {
      list.append(elem('p', '', 'No hay solicitudes registradas en este momento.'));
      filterTickets();
      return;
    }
    for (const x of rows) {
      const a = elem('details', 'ticket');
      a.dataset.id = x.id;
      a.dataset.state = x.status;
      if (keepOpenId && keepOpenId === x.id) a.open = true;
      a.dataset.search = `${x.id} ${x.user_id} ${x.question} ${x.advisor || ''}`.toLocaleLowerCase();
      const overview = elem('summary');
      
      const head = elem('div', 'card-header');
      head.append(
        elem('h2', '', `Ticket #${x.id}`),
        elem('span', `badge ${stateBadges[x.status] || ''}`, stateNames[x.status] || x.status)
      );
      overview.append(head);

      const meta = elem('div', 'client-meta');
      meta.textContent = `Canal: ${x.channel} · Cliente: ${x.user_id} · Fecha: ${new Date(x.created_at).toLocaleString()}`;
      overview.append(meta);

      const query = elem('div', 'client-query');
      query.textContent = `Consulta: "${x.question}"`;
      overview.append(query);
      a.append(overview);

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
        const isWhatsapp = x.channel === 'whatsapp';

        if (x.bot_paused) {
          a.append(elem('p', 'pause-banner', '⏸️ Bot en pausa: solo tú respondes a este cliente. El bot volverá a atenderlo cuando tú o el cliente finalicen la conversación.'));
        } else if (x.status === 'pending' && isWhatsapp) {
          a.append(elem('p', 'client-meta', 'Mientras nadie tome la solicitud, el bot sigue respondiendo al cliente. Al tomarla, el bot se pausa.'));
        }

        if (x.conversation && x.conversation.length) {
          const live = elem('div', 'live-chat');
          live.append(elem('strong', '', '💬 Conversación desde la solicitud'));
          for (const m of x.conversation) {
            const who = m.author === 'cliente' ? '👤 Cliente' : (m.author === 'asesor' ? `🧑‍💼 ${m.advisor || 'Asesor'}` : '🤖 Bot');
            const when = m.timestamp ? ' · ' + new Date(m.timestamp * 1000).toLocaleString() : '';
            const line = elem('div', `msg msg-${m.author}`);
            line.append(elem('span', 'msg-who', who + when), elem('p', '', m.content));
            live.append(line);
          }
          a.append(live);
          setTimeout(() => { live.scrollTop = live.scrollHeight; }, 0);
        }

        const formDiv = elem('div');
        const hasAdvisorMessages = Array.isArray(x.conversation) && x.conversation.some(m => m.author === 'asesor');

        const lWho = elem('label', '', 'Nombre del Asesor');
        const who = elem('input');
        who.type = 'text';
        who.placeholder = 'Ej: Eugenio Maldonado';
        who.value = x.advisor || '';
        who.id = `advisor-${x.id}`;
        lWho.htmlFor = who.id;
        formDiv.append(lWho, who);
        const needName = () => {
          if (who.value.trim()) return true;
          alert('Por favor ingresa tu nombre de asesor.'); who.focus(); return false;
        };

        const lNote = elem('label', '', x.status === 'in_progress' && isWhatsapp
          ? 'Mensaje para el cliente / Nota de cierre'
          : 'Respuesta al cliente / Nota de atención');
        const note = elem('textarea');
        note.placeholder = x.status === 'in_progress' && isWhatsapp
          ? 'Escribe un mensaje para seguir conversando con el cliente, o el resultado final antes de finalizar...'
          : 'Escribe aquí el mensaje para el cliente o el resultado de la atención...';
        note.value = x.note || '';
        note.id = `note-${x.id}`;
        lNote.htmlFor = note.id;
        formDiv.append(lNote, note);

        let notifyCheck = null;
        if (x.status === 'pending' && isWhatsapp) {
          const notifyLabel = elem('label', 'checkbox-group');
          notifyCheck = elem('input');
          notifyCheck.type = 'checkbox';
          notifyCheck.checked = true;
          notifyLabel.append(notifyCheck, ' Avisar al cliente por WhatsApp que ya lo estoy atendiendo (pausa al bot)');
          formDiv.append(notifyLabel);
        }

        let sendCheck = null;
        let closingCheck = null;
        if (isWhatsapp) {
          const checkLabel = elem('label', 'checkbox-group');
          sendCheck = elem('input');
          sendCheck.type = 'checkbox';
          sendCheck.checked = !hasAdvisorMessages;
          checkLabel.append(sendCheck, hasAdvisorMessages
            ? ' Enviar también este texto al WhatsApp del cliente al finalizar'
            : ' Enviar esta respuesta directamente al WhatsApp del cliente al finalizar');
          const closingLabel = elem('label', 'checkbox-group');
          closingCheck = elem('input');
          closingCheck.type = 'checkbox';
          closingCheck.checked = true;
          closingLabel.append(closingCheck, ' Enviar mensaje de finalización y agradecimiento (reactivar bot IA)');
          formDiv.append(checkLabel, closingLabel);
        }

        const btnGroup = elem('div', 'btn-group');

        if (x.status === 'pending') {
          const bTake = elem('button', 'btn-take', '✋ Tomar solicitud');
          bTake.onclick = async () => {
            if (!needName()) return;
            bTake.disabled = true;
            try { await sendUpdate(x.id, 'in_progress', who.value, note.value, false, { notify_customer: !!(notifyCheck && notifyCheck.checked) }); }
            finally { bTake.disabled = false; }
          };
          btnGroup.append(bTake);
        }

        if (isWhatsapp && x.status === 'in_progress') {
          const bSend = elem('button', 'btn-send', '📨 Enviar mensaje (seguir atendiendo)');
          bSend.onclick = async () => {
            if (!needName()) return;
            if (!note.value.trim()) { alert('Escribe el mensaje para el cliente.'); note.focus(); return; }
            bSend.disabled = true;
            try { await sendMessage(x.id, who.value, note.value); }
            finally { bSend.disabled = false; }
          };
          btnGroup.append(bSend);
        }

        const updateCloseLabel = () => {
          bClose.textContent = (sendCheck && sendCheck.checked) ? '🚀 Responder y Finalizar' : '✅ Finalizar conversación';
        };
        const bClose = elem('button', 'btn-close', '✅ Finalizar conversación');
        updateCloseLabel();
        if (sendCheck) sendCheck.onchange = updateCloseLabel;

        bClose.onclick = async () => {
          if (!needName()) return;
          if (!note.value.trim()) { alert('Describe el resultado o respuesta de la atención antes de finalizar.'); note.focus(); return; }
          bClose.disabled = true;
          try {
            await sendUpdate(x.id, 'closed', who.value, note.value, !!(sendCheck && sendCheck.checked),
                             { send_closing: !!(closingCheck && closingCheck.checked) });
          }
          finally { bClose.disabled = false; }
        };
        btnGroup.append(bClose);
        formDiv.append(btnGroup);
        a.append(formDiv);
      }

      list.append(a);
    }
    filterTickets();
  } catch (err) {
    list.replaceChildren(elem('p', 'error', err.message));
  }
}

function showFeedback(ok, text) {
  const fb = document.getElementById('feedback');
  fb.className = ok ? 'success' : 'error';
  fb.textContent = text;
  if (ok) setTimeout(() => { fb.textContent = ''; }, 5000);
}

async function sendUpdate(ticketId, status, advisor, note, sendToCustomer, extra) {
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
      body: JSON.stringify(Object.assign({
        status: status,
        advisor: advisor,
        note: note,
        send_to_customer: sendToCustomer
      }, extra || {}))
    });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || 'Error al actualizar');
    const parts = [status === 'closed' ? 'Conversación finalizada; el bot vuelve a atender al cliente.' : 'Solicitud tomada; el bot queda en pausa para este cliente.'];
    if (d.message_sent) parts.push('Nota enviada por WhatsApp.');
    if (d.customer_notified) parts.push('Se avisó al cliente.');
    if (extra && extra.notify_customer && !d.customer_notified) parts.push('⚠️ No se pudo avisar al cliente por WhatsApp.');
    if (d.closing_sent) parts.push('Agradecimiento enviado.');
    if (extra && extra.send_closing && !d.closing_sent) parts.push('⚠️ No se pudo enviar el agradecimiento (¿pasaron más de 24 h desde el último mensaje del cliente?).');
    showFeedback(true, parts.join(' '));
    if (status === 'in_progress' && selectedState === 'pending') {
      selectedState = 'in_progress';
      document.querySelectorAll('[data-state]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.state === 'in_progress')));
    }
    await load(status === 'in_progress' ? ticketId : null);
  } catch (e) {
    showFeedback(false, e.message);
  }
}

async function sendMessage(ticketId, advisor, text) {
  const fb = document.getElementById('feedback');
  fb.className = '';
  fb.textContent = 'Enviando...';
  try {
    const r = await fetch(`/handoffs/${ticketId}/message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Handoff-CSRF':'__CSRF__'
      },
      body: JSON.stringify({ advisor: advisor, text: text })
    });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || 'No se pudo enviar el mensaje');
    showFeedback(true, 'Mensaje enviado por WhatsApp. El bot sigue en pausa hasta que finalices la conversación.');
    await load(ticketId);
  } catch (e) {
    showFeedback(false, e.message);
  }
}

document.getElementById('refresh').onclick = () => load();
load();
</script></html>'''

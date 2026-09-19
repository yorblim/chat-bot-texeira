"""Registro operativo: aceptación de API no equivale a entrega o resolución."""
import sqlite3
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

from runtime_settings import state_file
from db_adapter import is_postgres, get_db_session
DB=Path(os.environ['SQLITE_DB_PATH']) if 'SQLITE_DB_PATH' in os.environ else state_file('trial_logs.db')

@contextmanager
def connection():
    if is_postgres():
        with get_db_session() as conn:
            yield conn
    else:
        conn=sqlite3.connect(str(DB),timeout=15)
        conn.row_factory=sqlite3.Row
        conn.execute('''CREATE TABLE IF NOT EXISTS operational_events (
            id TEXT PRIMARY KEY, received_at TEXT NOT NULL,
            completed_at TEXT, status TEXT NOT NULL,
            generation_ms REAL, response_attempt_ms REAL,
            route TEXT, model_claims_resolved INTEGER NOT NULL DEFAULT 0,
            provider_rate_limit INTEGER NOT NULL DEFAULT 0, handoff_id TEXT)''')
        try:
            with conn: yield conn
        finally: conn.close()

def start():
    event_id=uuid.uuid4().hex
    with connection() as conn:
        conn.execute('INSERT INTO operational_events(id,received_at,status) VALUES(?,?,?)',
                     (event_id,datetime.now(timezone.utc).isoformat(),'processing'))
    return event_id

def finish(event_id, status, generation_ms, response_attempt_ms, result=None):
    if status not in {'api_accepted','send_failed','processing_failed'}:
        raise ValueError('Estado operativo inválido')
    result=result or {}
    with connection() as conn:
        conn.execute('''UPDATE operational_events SET completed_at=?,status=?,generation_ms=?,response_attempt_ms=?,
            route=?,model_claims_resolved=?,provider_rate_limit=?,handoff_id=? WHERE id=? AND status='processing' ''',
            (datetime.now(timezone.utc).isoformat(),status,generation_ms,response_attempt_ms,
             result.get('response_route'),int(bool(result.get('resolved_autonomously'))),
             int(bool(result.get('is_rate_limit'))),result.get('handoff_id'),event_id))

def summary():
    with connection() as conn:
        row=dict(conn.execute('''SELECT COUNT(*) AS received,
            COALESCE(SUM(CASE WHEN status='api_accepted' THEN 1 ELSE 0 END),0) AS api_accepted,
            COALESCE(SUM(CASE WHEN status='send_failed' THEN 1 ELSE 0 END),0) AS send_failed,
            COALESCE(SUM(CASE WHEN status='processing_failed' THEN 1 ELSE 0 END),0) AS processing_failed,
            COALESCE(SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END),0) AS processing,
            COALESCE(SUM(provider_rate_limit),0) AS provider_rate_limits,
            AVG(generation_ms) AS generation_ms,
            AVG(CASE WHEN status='api_accepted' THEN response_attempt_ms END) AS api_acceptance_ms,
            MIN(received_at) AS observed_since FROM operational_events''').fetchone())
        row['api_acceptance_pct']=round(100*row['api_accepted']/row['received'],2) if row['received'] else None
    # Solicitudes únicas; repetir "asesor" no aumenta el total.
    import handoff_support as h
    with h.connection() as conn:
        row['human_requests']={r['status']:r['n'] for r in conn.execute("SELECT status,COUNT(*) n FROM requests WHERE channel='whatsapp' GROUP BY status")}
    row.update(delivery_confirmed=None,resolution_validated=None,availability_pct=None,after_hours=None,
               scope='Mensajes de texto WhatsApp admitidos y no duplicados desde la instalación; sin reconstruir eventos históricos')
    return row

def install(app):
    def _is_allowed(request: Request) -> bool:
        if os.getenv('ALLOW_CLOUD_RUN') or os.getenv('K_SERVICE'):
            return True
        return request.client is not None and request.client.host in {'127.0.0.1', '::1', 'testclient'}

    @app.get('/operational-metrics/data')
    async def data(request:Request):
        if not _is_allowed(request):
            return JSONResponse({'error':'Acceso local requerido'},status_code=403)
        return JSONResponse(summary())

    @app.get('/operational-metrics',response_class=HTMLResponse)
    async def page(request:Request):
        if not _is_allowed(request):
            return HTMLResponse('Acceso local requerido',status_code=403)
        return HTMLResponse(PAGE)

PAGE='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Métricas operativas — Texeira</title><style>body{font:16px system-ui;max-width:900px;margin:40px auto;padding:20px;color:#18333b;background:#f4f7f8}table{width:100%;border-collapse:collapse;background:white}td,th{padding:14px;border-bottom:1px solid #ccd}th{text-align:left}button{padding:10px;font:inherit}</style>
<h1>Métricas operativas de WhatsApp</h1><p>Envío aceptado por Meta no significa entrega al teléfono ni consulta resuelta. Los errores permanecen en el total.</p><p>Se cuentan mensajes de texto admitidos y no duplicados desde esta versión, sin reconstruir eventos antiguos. Las solicitudes humanas corresponden a WhatsApp desde la instalación de su panel.</p>
<a href="/handoffs">Solicitudes humanas</a> <button id="refresh">Actualizar</button><p id="since"></p><table><thead><tr><th>Indicador</th><th>Valor</th></tr></thead><tbody id="rows"></tbody></table>
<p>La latencia empieza al recibir el webhook en el servidor. No mide el tiempo desde que el usuario escribió en su teléfono. Una solicitud cerrada refleja el resultado registrado por el asesor, no una confirmación automática del cliente.</p>
<p>Entrega al teléfono, resolución validada, disponibilidad y atención fuera de horario: todavía no medidas. El horario debe confirmarlo la agencia.</p>
<script>async function load(){const r=await fetch('/operational-metrics/data');if(!r.ok)throw Error('No se pudieron consultar las métricas');const d=await r.json();document.getElementById('since').textContent=d.observed_since?'Desde: '+new Date(d.observed_since).toLocaleString():'Aún no hay eventos nuevos.';const rows=[['Mensajes registrados',d.received],['Envíos aceptados por Meta',d.api_accepted],['Envíos fallidos',d.send_failed],['Fallos de procesamiento',d.processing_failed],['Pendientes de procesamiento',d.processing],['Errores por límite del proveedor',d.provider_rate_limits],['Aceptación API sobre todos los mensajes (%)',d.api_acceptance_pct],['Preparación de respuesta: promedio (ms)',d.generation_ms],['Hasta aceptación API: promedio de envíos aceptados (ms)',d.api_acceptance_ms],['Solicitudes humanas pendientes',d.human_requests.pending||0],['Solicitudes humanas en atención',d.human_requests.in_progress||0],['Solicitudes cerradas por el asesor',d.human_requests.closed||0]];const root=document.getElementById('rows');root.replaceChildren();for(const [k,v] of rows){const tr=document.createElement('tr');for(const text of [k,v===null?'Sin datos':typeof v==='number'?String(Math.round(v*100)/100):v]){const td=document.createElement('td');td.textContent=text;tr.append(td)}root.append(tr)}}document.getElementById('refresh').onclick=()=>load().catch(e=>document.getElementById('since').textContent=e.message);load().catch(e=>document.getElementById('since').textContent=e.message)</script></html>'''

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
    if status not in {'api_accepted', 'send_failed', 'processing_failed', 'send_uncertain'}:
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
            COALESCE(SUM(CASE WHEN status='send_uncertain' THEN 1 ELSE 0 END),0) AS send_uncertain,
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
        from admin_theme import decorate
        return HTMLResponse(decorate(PAGE, 'metrics'))

PAGE='''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Métricas operativas de WhatsApp — Texeira Travel</title>
<style>
  .metrics-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; margin-bottom: 24px; }
  .metrics-group { background: #fff; border: 1px solid #dbe4ee; border-radius: 12px; padding: 20px; }
  .metrics-group.full-width { grid-column: 1 / -1; }
  .metrics-group h2 { margin: 0 0 14px 0; font-size: 16px; color: #174363; display: flex; align-items: center; gap: 8px; font-weight: 700; }
  .metrics-table { width: 100%; border-collapse: collapse; }
  .metrics-table th, .metrics-table td { padding: 10px 14px; text-align: left; font-size: 14px; border-bottom: 1px solid #eef3f8; }
  .metrics-table th { background: #f8fafc; color: #52657b; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }
  .metrics-table tr:last-child td { border-bottom: none; }
  .metrics-table td.val { text-align: right; font-weight: 700; font-family: ui-monospace, monospace; color: #172b43; }
  .metrics-table td.val-highlight { color: #1769aa; }
  .since-badge { display: inline-block; font-size: 13px; color: #52657b; margin-top: 6px; }
  @media(max-width: 800px) {
    .metrics-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<header class="header">
  <div>
    <h1>📈 Métricas operativas de WhatsApp</h1>
    <p>Telemetría de webhooks, latencia y atención humana en tiempo real</p>
  </div>
  <button id="refresh" class="btn" style="background:#1769aa;color:white;border:none;padding:8px 16px;font-weight:600;border-radius:8px;">🔄 Actualizar</button>
</header>

<div class="admin-note" style="margin-bottom: 22px;">
  <strong>ℹ️ Alcance de medición y limitaciones técnicas</strong>
  <p style="margin: 4px 0 0;">El <strong>envío aceptado por Meta</strong> indica recepción técnica en la API de WhatsApp Cloud, pero <em>no acredita</em> entrega física en el teléfono ni consulta resuelta para el cliente. Los errores de red o proveedor permanecen contabilizados en el total.</p>
  <div class="since-badge" id="since">Cargando eventos...</div>
</div>

<div class="metrics-grid">
  <div class="metrics-group full-width">
    <h2>📨 Mensajería y Envíos WhatsApp</h2>
    <table class="metrics-table">
      <thead>
        <tr><th>Indicador de Tráfico y Envíos</th><th style="text-align:right">Valor</th></tr>
      </thead>
      <tbody id="rows-traffic"></tbody>
    </table>
  </div>

  <div class="metrics-group">
    <h2>⏱️ Tiempos de Respuesta (Latencia)</h2>
    <table class="metrics-table">
      <thead>
        <tr><th>Etapa de Procesamiento</th><th style="text-align:right">Promedio</th></tr>
      </thead>
      <tbody id="rows-latency"></tbody>
    </table>
  </div>

  <div class="metrics-group">
    <h2>🛎️ Solicitudes de Atención Humana</h2>
    <table class="metrics-table">
      <thead>
        <tr><th>Estado de la Solicitud</th><th style="text-align:right">Cantidad</th></tr>
      </thead>
      <tbody id="rows-human"></tbody>
    </table>
    <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid #eef3f8;">
      <a href="/handoffs" style="font-size: 13px; color: #1769aa; font-weight: 600; text-decoration: none;">Abrir consola de Atención al cliente →</a>
    </div>
  </div>
</div>

<details class="admin-method">
  <summary>Metodología, definiciones técnicas y limitaciones</summary>
  <div style="font-size: 13px; line-height: 1.6; color: #52657b; margin-top: 12px;">
    <p>• <strong>Inicio de latencia:</strong> Se registra a partir de la llegada del webhook al servidor. No contempla la transmisión previa desde el dispositivo del usuario.</p>
    <p>• <strong>Estado de solicitudes:</strong> Una solicitud cerrada refleja la acción explícita registrada por el asesor en la consola, no una confirmación automática del cliente.</p>
    <p>• <strong>Métricas no medidas automáticamente:</strong> La entrega física al teléfono, confirmación de lectura, resolución validada del caso y cobertura fuera de horario no están instrumentadas de forma autónoma.</p>
    <p>• <strong>Período y origen:</strong> Se contabilizan eventos admitidos y desduplicados desde el arranque de esta versión, sin reconstrucción retrospectiva de sesiones anteriores.</p>
  </div>
</details>

<script>
function fmtVal(v, suffix='') {
  if (v === null || v === undefined) return 'Sin datos';
  if (typeof v === 'number') {
    const rounded = Math.round(v * 100) / 100;
    return String(rounded) + suffix;
  }
  return String(v) + suffix;
}

function fillRows(tbodyId, rows) {
  const root = document.getElementById(tbodyId);
  root.replaceChildren();
  for (const [label, val, highlight] of rows) {
    const tr = document.createElement('tr');
    const tdLabel = document.createElement('td');
    tdLabel.textContent = label;
    const tdVal = document.createElement('td');
    tdVal.className = 'val' + (highlight ? ' val-highlight' : '');
    tdVal.textContent = val;
    tr.append(tdLabel, tdVal);
    root.append(tr);
  }
}

async function load() {
  const r = await fetch('/operational-metrics/data');
  if (!r.ok) throw Error('No se pudieron consultar las métricas');
  const d = await r.json();
  document.getElementById('since').textContent = d.observed_since
    ? 'Observado desde: ' + new Date(d.observed_since).toLocaleString()
    : 'Aún no hay eventos registrados en este período.';

  fillRows('rows-traffic', [
    ['Mensajes entrantes registrados', fmtVal(d.received)],
    ['Envíos aceptados por la API de Meta', fmtVal(d.api_accepted), true],
    ['Tasa de aceptación API (%)', fmtVal(d.api_acceptance_pct, '%'), true],
    ['Envíos fallidos (red o proveedor)', fmtVal(d.send_failed)],
    ['Envíos con resultado incierto (retenidos para revisión)', fmtVal(d.send_uncertain)],
    ['Fallos internos de procesamiento', fmtVal(d.processing_failed)],
    ['Mensajes pendientes de procesamiento', fmtVal(d.processing)],
    ['Bloqueos por límite del proveedor (rate limits)', fmtVal(d.provider_rate_limits)]
  ]);

  fillRows('rows-latency', [
    ['Preparación de respuesta (RAG / motor)', fmtVal(d.generation_ms, ' ms')],
    ['Hasta aceptación API en envíos exitosos', fmtVal(d.api_acceptance_ms, ' ms'), true]
  ]);

  const hr = d.human_requests || {};
  fillRows('rows-human', [
    ['Solicitudes pendientes de atención', fmtVal(hr.pending || 0), (hr.pending || 0) > 0],
    ['Solicitudes en curso de atención', fmtVal(hr.in_progress || 0)],
    ['Solicitudes cerradas por el asesor', fmtVal(hr.closed || 0)]
  ]);
}

document.getElementById('refresh').onclick = () => load().catch(e => document.getElementById('since').textContent = e.message);
load().catch(e => document.getElementById('since').textContent = e.message);
</script>
</html>'''

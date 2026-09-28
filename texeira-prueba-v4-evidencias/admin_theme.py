"""Shared presentation for administrative pages; no business logic."""

STYLE = '''<style>
:root {
  --bg-primary: #f4f7fb;
  --bg-card: #ffffff;
  --bg-secondary: #eef3f8;
  --text-primary: #172b43;
  --text-secondary: #52657b;
  --border: #dbe4ee;
  --primary: #1769aa;
  --primary-hover: #12558b;
  --bg: #f4f7fb;
  --card: #ffffff;
  --text: #172b43;
  --muted: #52657b;
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
}
body {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif !important;
  background: #f4f7fb !important;
  color: #172b43 !important;
  max-width: 1280px !important;
  margin: 0 auto !important;
  padding: 24px !important;
  line-height: 1.5;
}
.container { max-width: 100% !important; padding: 0 !important; margin: 0 !important; }

/* Global Navigation Bar */
.admin-nav {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  padding: 12px 0 20px;
  border-bottom: 1px solid #dbe4ee;
  margin-bottom: 24px;
  width: 100%;
}
.admin-nav strong {
  margin-right: auto;
  font-size: 18px;
  font-weight: 700;
  color: #174363;
  letter-spacing: -0.3px;
}
.admin-nav a {
  padding: 8px 14px;
  border-radius: 8px;
  text-decoration: none;
  color: #52657b;
  font-weight: 600;
  font-size: 14px;
  transition: all .15s ease;
}
.admin-nav a:hover {
  background: #eaf0f7;
  color: #172b43;
}
.admin-nav a[aria-current=page] {
  background: #e3effb;
  color: #12558b;
  font-weight: 700;
}

/* Header Cards */
header, .header {
  background: #fff !important;
  border: 1px solid #dbe4ee !important;
  box-shadow: none !important;
  border-radius: 12px !important;
  padding: 22px 24px !important;
  margin-bottom: 22px !important;
  color: #172b43 !important;
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  flex-wrap: wrap !important;
  gap: 16px !important;
  position: static !important;
  width: 100% !important;
}
header::before, header::after, .header::before, .header::after { display: none !important; }
header > div:first-child, .header > div:first-child, .header-content > div:first-child {
  flex: 1 1 280px;
  min-width: 0;
}
h1, .header h1, header h1 {
  color: #172b43 !important;
  font-size: 24px !important;
  font-weight: 700 !important;
  letter-spacing: -0.4px !important;
  margin: 0 0 4px 0 !important;
  line-height: 1.25 !important;
}
h2 { font-size: 18px; color: #172b43; }
header p, .header p, .subtitle {
  color: #52657b !important;
  font-size: 14px !important;
  margin: 0 !important;
  line-height: 1.4 !important;
}
.nav-links a { display: none !important; }
.header-content a[href^="/"] { display: none !important; }
.header-badge {
  background: #edf4fb !important;
  color: #26527d !important;
  border: 1px solid #dbe4ee !important;
  padding: 6px 14px !important;
  border-radius: 20px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  white-space: nowrap !important;
}
.header-content {
  width: 100% !important;
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  flex-wrap: wrap !important;
  gap: 16px !important;
}

/* Base Buttons & Accessibility Focus */
button, .btn {
  border-radius: 8px;
  min-height: 38px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s ease;
}
button:disabled { opacity: .55; cursor: wait; }
a:focus-visible, button:focus-visible, input:focus-visible, summary:focus-visible, select:focus-visible, textarea:focus-visible {
  outline: 3px solid #79b5e6 !important;
  outline-offset: 2px !important;
}

/* KPI Grid */
.kpi-grid {
  display: grid !important;
  grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
  gap: 14px !important;
  margin-bottom: 24px !important;
}
.kpi-card {
  background: #fff !important;
  border: 1px solid #dbe4ee !important;
  box-shadow: none !important;
  animation: none !important;
  border-radius: 12px !important;
  padding: 18px 20px !important;
  transition: border-color .15s ease !important;
}
.kpi-card:hover {
  border-color: #b9d0e6 !important;
  transform: none !important;
  box-shadow: 0 4px 12px rgba(23,105,170,0.06) !important;
}
.kpi-value {
  font-size: 28px !important;
  font-weight: 700 !important;
  line-height: 1.2 !important;
  margin-bottom: 4px !important;
}
.kpi-label {
  color: #52657b !important;
  font-size: 13px !important;
  font-weight: 500 !important;
}
.kpi-icon { display: none !important; }

/* Tables */
.table-container {
  background: #fff !important;
  border: 1px solid #dbe4ee !important;
  border-radius: 12px !important;
  box-shadow: none !important;
  animation: none !important;
  overflow-x: auto !important;
  -webkit-overflow-scrolling: touch !important;
  margin-bottom: 24px !important;
  width: 100% !important;
}
table {
  background: #fff;
  width: 100%;
  border-collapse: collapse;
}
thead, th {
  background: #eef3f8 !important;
  color: #40566e !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  text-transform: uppercase !important;
  letter-spacing: .4px !important;
  padding: 12px 14px !important;
  border-bottom: 1px solid #dbe4ee !important;
  text-align: left;
}
td {
  padding: 12px 14px !important;
  border-bottom: 1px solid #eef3f8 !important;
  color: #172b43 !important;
  font-size: 14px !important;
}
tbody tr { background: #fff !important; }
tbody tr:hover { background: #f8fafc !important; }
tbody tr:last-child td { border-bottom: none !important; }
.user-id, .id-badge, .lang-badge, .channel-badge {
  background: #edf4fb !important;
  color: #26527d !important;
  border-radius: 6px !important;
  padding: 2px 8px !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  display: inline-block !important;
}
.message-cell, .response-cell, .timestamp { color: #52657b !important; }
.footer { color: #52657b !important; text-align: center; font-size: 13px; margin: 32px 0 16px; }

/* Toolbar & Filters (Handoffs) */
.admin-toolbar {
  display: flex !important;
  gap: 10px !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  margin: 18px 0 !important;
  width: 100% !important;
}
.admin-toolbar button {
  background: #fff;
  border: 1px solid #c9d5e3;
  color: #243c55;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  transition: all .15s ease;
}
.admin-toolbar button:hover { background: #f1f5f9; }
.admin-toolbar button[aria-pressed=true] {
  background: #1769aa !important;
  color: #fff !important;
  border-color: #1769aa !important;
}
.admin-toolbar input[type=search], .admin-toolbar input[type=text] {
  flex: 1 1 240px;
  min-width: 180px;
  padding: 9px 14px;
  border: 1px solid #c9d5e3;
  border-radius: 8px;
  font: inherit;
  font-size: 14px;
  background: #fff;
}
#visibleCount {
  color: #52657b;
  font-size: 14px;
  margin: 10px 0 16px;
  font-weight: 500;
}

/* Handoff Tickets */
.ticket {
  background: #fff !important;
  border: 1px solid #dbe4ee !important;
  border-radius: 12px !important;
  margin: 12px 0 !important;
  padding: 0 !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03) !important;
  overflow: hidden !important;
  width: 100% !important;
}
.ticket > summary {
  padding: 16px 20px !important;
  list-style: none !important;
  color: #172b43 !important;
  cursor: pointer !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 8px !important;
  background: #fff !important;
  width: 100% !important;
}
.ticket > summary::-webkit-details-marker { display: none !important; }
.ticket > summary::after {
  content: 'Abrir solicitud ↓';
  font-size: 13px;
  color: #1769aa;
  font-weight: 600;
  align-self: flex-start;
  margin-top: 4px;
}
.ticket[open] > summary::after {
  content: 'Cerrar detalle ↑';
}
.ticket[open] > summary {
  border-bottom: 1px solid #eef3f8 !important;
  background: #fbfdff !important;
}
.ticket > :not(summary) {
  margin-left: 20px !important;
  margin-right: 20px !important;
}
.ticket > :last-child {
  margin-bottom: 20px !important;
}
.ticket h2 {
  margin: 0 !important;
  font-size: 16px !important;
  color: #172b43 !important;
}
.ticket .card-header {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  gap: 8px !important;
  flex-wrap: wrap !important;
  margin-bottom: 2px !important;
  width: 100% !important;
}
.ticket .client-meta {
  color: #52657b !important;
  font-size: 13px !important;
  word-break: break-word !important;
  overflow-wrap: anywhere !important;
}
.ticket .client-query {
  background: #f8fafc !important;
  border-left: 3px solid #1769aa !important;
  border-radius: 4px !important;
  padding: 10px 12px !important;
  font-size: 14px !important;
  color: #172b43 !important;
  margin: 4px 0 0 !important;
  word-break: break-word !important;
  overflow-wrap: anywhere !important;
}
.ticket[hidden] { display: none !important; }

/* Badges */
.badge {
  display: inline-block !important;
  padding: 3px 10px !important;
  border-radius: 999px !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  white-space: nowrap !important;
  letter-spacing: .3px !important;
}
.badge-pending { background: #fef3c7 !important; color: #92400e !important; }
.badge-in_progress { background: #dbeafe !important; color: #1e40af !important; }
.badge-closed { background: #dcfce7 !important; color: #166534 !important; }

/* Catalog Cards & Grid */
.grid {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 18px !important;
  width: 100% !important;
}
.card, .tour-card {
  background: #fff !important;
  border: 1px solid #dbe4ee !important;
  box-shadow: none !important;
  animation: none !important;
  border-radius: 12px !important;
  padding: 20px !important;
  display: flex !important;
  flex-direction: column !important;
  justify-content: space-between !important;
  transition: border-color .15s ease !important;
}
.card:hover, .tour-card:hover {
  border-color: #b9d0e6 !important;
  transform: none !important;
  box-shadow: 0 4px 12px rgba(23,105,170,0.06) !important;
}
.card-top {
  display: flex !important;
  justify-content: space-between !important;
  align-items: flex-start !important;
  gap: 10px !important;
  margin-bottom: 12px !important;
  flex-wrap: wrap !important;
  width: 100% !important;
}
.tour-title {
  font-size: 16px !important;
  font-weight: 700 !important;
  color: #172b43 !important;
  margin: 0 !important;
  line-height: 1.3 !important;
}
.tour-id {
  display: inline-block !important;
  font-size: 11px !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
  color: #52657b !important;
  background: #edf4fb !important;
  padding: 2px 7px !important;
  border-radius: 4px !important;
  margin-top: 4px !important;
}
.badge-canonical {
  background: #e0f2fe !important;
  color: #0369a1 !important;
  white-space: nowrap !important;
}
.badge-custom {
  background: #f3e8ff !important;
  color: #7e22ce !important;
  white-space: nowrap !important;
}
.toolbar {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  gap: 12px !important;
  margin-bottom: 20px !important;
  flex-wrap: wrap !important;
  width: 100% !important;
}
.search-box {
  flex: 1 1 260px !important;
  max-width: 480px !important;
  position: relative !important;
  display: flex !important;
  align-items: center !important;
}
.search-icon {
  position: absolute !important;
  left: 12px !important;
  top: 50% !important;
  transform: translateY(-50%) !important;
  color: #52657b !important;
  pointer-events: none !important;
  font-size: 14px !important;
  line-height: 1 !important;
  z-index: 2 !important;
}
.search-box input {
  width: 100% !important;
  padding: 10px 14px 10px 36px !important;
  font-size: 14px !important;
  border: 1px solid #c9d5e3 !important;
  border-radius: 8px !important;
  background: #fff !important;
}
.card-actions {
  display: flex !important;
  gap: 8px !important;
  flex-wrap: wrap !important;
  margin-top: 14px !important;
  padding-top: 12px !important;
  border-top: 1px solid #eef3f8 !important;
  width: 100% !important;
}
.card-actions button, .card-actions .btn {
  flex: 1 1 calc(50% - 4px) !important;
  min-width: 70px !important;
  min-height: 36px !important;
  height: 36px !important;
  padding: 6px 10px !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  border-radius: 8px !important;
  border: 1px solid #dbe4ee !important;
  background: #fff !important;
  color: #172b43 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
}
.card-actions button:hover, .card-actions .btn:hover { background: #f1f5f9 !important; }
.card-actions .btn-danger {
  color: #a63333 !important;
  border-color: #fed7d7 !important;
  background: #fff !important;
}
.card-actions .btn-danger:hover {
  background: #fee2e2 !important;
  border-color: #fca5a5 !important;
}

/* Informative Notes & Methodology */
.admin-note {
  padding: 14px 18px;
  border: 1px solid #dbe4ee;
  background: #edf4fb;
  border-radius: 10px;
  color: #26527d;
  font-size: 14px;
  line-height: 1.5;
  width: 100%;
}
.admin-method {
  margin: 24px 0;
  padding: 18px 20px;
  border: 1px solid #dbe4ee;
  border-radius: 10px;
  background: #fff;
  width: 100%;
}
.admin-method summary {
  cursor: pointer;
  font-weight: 600;
  color: #174363;
  font-size: 14px;
}

/* Responsive Media Queries */
@media(max-width: 1024px) {
  .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }
}
@media(max-width: 700px) {
  body {
    padding: 12px !important;
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
  }
  .admin-nav {
    display: grid !important;
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 6px !important;
    padding: 8px 0 16px !important;
    margin-bottom: 16px !important;
    width: 100% !important;
  }
  .admin-nav strong {
    grid-column: 1 / -1 !important;
    margin-bottom: 4px !important;
    font-size: 17px !important;
  }
  .admin-nav a {
    padding: 7px 4px !important;
    font-size: 12px !important;
    min-height: 34px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    background: #edf4fb;
    border-radius: 6px !important;
    line-height: 1.2 !important;
    word-break: normal !important;
  }
  .admin-nav a[aria-current=page] {
    background: #1769aa !important;
    color: #fff !important;
  }
  header, .header {
    padding: 16px !important;
    margin-bottom: 16px !important;
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 12px !important;
  }
  header > div, .header > div, .header-content > div,
  header > div:first-child, .header > div:first-child, .header-content > div:first-child {
    flex: 0 0 auto !important;
    width: 100% !important;
    min-height: 0 !important;
  }
  h1, .header h1, header h1 {
    font-size: 20px !important;
  }
  header button, .header button, .header-badge {
    align-self: flex-start !important;
  }
  .toolbar {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 10px !important;
  }
  .toolbar > div {
    width: 100% !important;
    flex: 0 0 auto !important;
  }
  .toolbar button {
    width: 100% !important;
  }
  .search-box {
    flex: 0 0 auto !important;
    width: 100% !important;
    max-width: 100% !important;
    min-height: 0 !important;
  }
  .admin-toolbar {
    gap: 6px !important;
  }
  .admin-toolbar button {
    flex: 1 1 calc(50% - 6px) !important;
    padding: 8px 6px !important;
    text-align: center !important;
    font-size: 12px !important;
  }
  .admin-toolbar input[type=search], .admin-toolbar input[type=text] {
    flex: 1 1 100% !important;
    width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }
  .ticket {
    max-width: 100% !important;
    box-sizing: border-box !important;
  }
  .ticket > summary {
    padding: 14px 16px !important;
  }
  .ticket > :not(summary) {
    margin-left: 14px !important;
    margin-right: 14px !important;
  }
  .ticket > :last-child {
    margin-bottom: 16px !important;
  }
  .ticket input[type=text], .ticket textarea {
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }
  .ticket .btn-group {
    display: flex !important;
    flex-direction: column !important;
    gap: 8px !important;
  }
  .ticket .btn-group button {
    width: 100% !important;
    flex: 1 1 100% !important;
  }
  .modal-backdrop {
    padding: 10px !important;
    align-items: flex-start !important;
    overflow-y: auto !important;
  }
  .modal {
    padding: 16px !important;
    max-height: 94vh !important;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }
  .form-row {
    grid-template-columns: 1fr !important;
    gap: 8px !important;
  }
  .grid {
    grid-template-columns: 1fr !important;
  }
  .card, .tour-card {
    padding: 14px !important;
    box-sizing: border-box !important;
  }
  .card-actions button, .card-actions .btn {
    font-size: 12px !important;
    padding: 6px 4px !important;
  }
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 10px !important;
  }
  .kpi-grid > .kpi-card:last-child {
    grid-column: span 2 !important;
  }
  .kpi-card {
    padding: 14px 12px !important;
  }
  .kpi-value {
    font-size: 22px !important;
  }
  .kpi-label {
    font-size: 12px !important;
  }
  .metrics-grid {
    grid-template-columns: 1fr !important;
    gap: 14px !important;
  }
  .metrics-group {
    padding: 14px !important;
    box-sizing: border-box !important;
  }
  .metrics-table th, .metrics-table td {
    padding: 8px 6px !important;
    font-size: 13px !important;
  }
}
</style>'''

def navigation(current):
    links = [
        ('dashboard', '/dashboard', 'Resumen'),
        ('handoffs', '/handoffs', 'Atención al cliente'),
        ('catalogo', '/catalogo', 'Catálogo'),
        ('metrics', '/operational-metrics', 'Métricas')
    ]
    return '<nav class="admin-nav" aria-label="Navegación principal"><strong>Texeira Travel</strong>' + ''.join(
        f'<a href="{url}"' + (' aria-current="page"' if key == current else '') + f'>{label}</a>'
        for key, url, label in links) + '</nav>'

def decorate(html, current):
    # Legacy templates without an explicit body are normalized here.
    html = html.replace('</style>', '</style>' + STYLE, 1)
    if '<body>' in html:
        return html.replace('<body>', '<body>' + navigation(current), 1)
    marker = html.index('</style>', html.index(STYLE)) + len('</style>')
    return html[:marker] + navigation(current) + html[marker:]

"""
catalog_ui.py — Interfaz Web Moderna para Gestión de Catálogo y Tarifas de Texeira Travel.

Genera el HTML y Vanilla JS para /catalogo. Permite a los administradores
editar precios vigentes, horarios, registrar nuevos destinos turísticos
y subir fotos y folletos PDF sincronizados con WhatsApp.
"""

def get_catalog_html(csrf_token: str) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Catálogo y Tarifas de Tours — Texeira Travel</title>
  <style>
    :root {{
      --primary: #0284c7;
      --primary-hover: #0369a1;
      --success: #16a34a;
      --warning: #d97706;
      --danger: #dc2626;
      --bg: #f8fafc;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --radius: 10px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      padding: 24px;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .container {{
      max-width: 1140px;
      margin: 0 auto;
    }}
    header {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px 24px;
      margin-bottom: 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      color: #0369a1;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .subtitle {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .nav-links {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .nav-links a {{
      color: var(--muted);
      text-decoration: none;
      font-size: 14px;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: 6px;
      transition: all 0.2s;
    }}
    .nav-links a:hover, .nav-links a.active {{
      color: var(--primary);
      background: #e0f2fe;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      font-size: 14px;
      font-weight: 600;
      border-radius: 8px;
      border: none;
      cursor: pointer;
      transition: all 0.2s;
      text-decoration: none;
    }}
    .btn-primary {{
      background: var(--primary);
      color: white;
    }}
    .btn-primary:hover {{
      background: var(--primary-hover);
    }}
    .btn-secondary {{
      background: white;
      border: 1px solid var(--border);
      color: var(--text);
    }}
    .btn-secondary:hover {{
      background: #f1f5f9;
    }}
    .btn-sm {{
      padding: 4px 10px;
      font-size: 12px;
    }}
    .btn-danger {{
      background: #fee2e2;
      border: 1px solid #fca5a5;
      color: #b91c1c;
    }}
    .btn-danger:hover {{
      background: #fca5a5;
      color: #7f1d1d;
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .search-box {{
      position: relative;
      flex: 1;
      max-width: 380px;
    }}
    .search-box input {{
      width: 100%;
      padding: 10px 14px 10px 36px;
      font-size: 14px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: white;
    }}
    .search-icon {{
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      pointer-events: none;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 18px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.15s, box-shadow 0.15s;
    }}
    .card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 12px rgba(0,0,0,0.06);
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }}
    .tour-title {{
      font-size: 16px;
      font-weight: 700;
      color: #0f172a;
      margin: 0 0 4px;
    }}
    .tour-id {{
      font-size: 12px;
      color: var(--muted);
      font-family: monospace;
    }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .badge-canonical {{
      background: #e0f2fe;
      color: #0369a1;
    }}
    .badge-custom {{
      background: #f3e8ff;
      color: #7e22ce;
    }}
    .tour-details {{
      font-size: 13px;
      color: #334155;
      margin: 10px 0;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .detail-row {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .price-tag {{
      font-size: 15px;
      font-weight: 700;
      color: var(--success);
      background: #dcfce7;
      padding: 2px 8px;
      border-radius: 6px;
    }}
    .price-missing {{
      font-size: 13px;
      color: var(--warning);
      background: #fef3c7;
      padding: 2px 8px;
      border-radius: 6px;
      font-weight: 600;
    }}
    .assets-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px dashed var(--border);
      font-size: 12px;
    }}
    .thumb {{
      width: 44px;
      height: 44px;
      border-radius: 6px;
      object-fit: cover;
      border: 1px solid var(--border);
    }}
    .card-actions {{
      display: flex;
      gap: 8px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--border);
    }}
    /* Modales */
    .modal-backdrop {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.5);
      backdrop-filter: blur(2px);
      z-index: 999;
      justify-content: center;
      align-items: center;
      padding: 20px;
    }}
    .modal {{
      background: white;
      border-radius: var(--radius);
      width: 100%;
      max-width: 620px;
      max-height: 90vh;
      overflow-y: auto;
      padding: 24px;
      box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
    }}
    .rate-card {{
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }}
    .rate-badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 4px;
      text-transform: uppercase;
    }}
    .rate-badge-student {{ background: #e0e7ff; color: #3730a3; }}
    .rate-badge-child {{ background: #fef3c7; color: #92400e; }}
    .rate-badge-promo {{ background: #fee2e2; color: #991b1b; }}
    .rate-badge-adult {{ background: #f1f5f9; color: #475569; }}
    .rate-badge-custom {{ background: #f3e8ff; color: #6b21a8; }}
    .modal-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
    }}
    .modal-title {{
      font-size: 18px;
      font-weight: 700;
      color: #0369a1;
      margin: 0;
    }}
    .form-group {{
      margin-bottom: 14px;
    }}
    .form-group label {{
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #334155;
      margin-bottom: 4px;
    }}
    .form-group input, .form-group textarea, .form-group select {{
      width: 100%;
      padding: 9px 12px;
      font-size: 14px;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-family: inherit;
    }}
    .form-row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 14px;
      box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2);
      display: none;
      z-index: 1000;
      animation: fadeIn 0.2s ease-in-out;
    }}
    .toast.success {{ background: var(--success); }}
    .toast.error {{ background: var(--danger); }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>🗺️ Catálogo de Tours y Tarifas</h1>
        <p class="subtitle">Texeira Travel — Gestión de precios, horarios, folletos e imágenes sincronizados con el chatbot</p>
      </div>
      <div class="nav-links">
        <a href="/handoffs">🛎️ Asesores</a>
        <a href="/catalogo" class="active">🗺️ Catálogo</a>
        <a href="/dashboard">📊 Dashboard</a>
        <a href="/operational-metrics">📈 Métricas</a>
        <button id="btnNewTour" class="btn btn-primary">+ Nuevo Tour</button>
      </div>
    </header>

    <div class="toolbar">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="Buscar tour por nombre o destino...">
      </div>
      <div>
        <button id="btnRefresh" class="btn btn-secondary">🔄 Actualizar</button>
      </div>
    </div>

    <div id="toursGrid" class="grid">
      <!-- Se carga dinámicamente con JavaScript -->
    </div>
  </div>

  <!-- Modal: Crear / Editar Tour -->
  <div id="tourModal" class="modal-backdrop">
    <div class="modal">
      <div class="modal-header">
        <h3 id="modalTourTitle" class="modal-title">Editar Tour</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeModal('tourModal')">✕</button>
      </div>
      <form id="tourForm">
        <input type="hidden" id="formIsEdit" value="0">
        <div class="form-group">
          <label>Identificador Único (entity_id)</label>
          <input type="text" id="formEntityId" placeholder="ej: tour-huacachina" required>
        </div>
        <div class="form-group">
          <label>Nombre del Tour</label>
          <input type="text" id="formName" placeholder="ej: Tour Huacachina & Tubulares" required>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Precio Oficial</label>
            <input type="text" id="formPrice" placeholder="ej: 35.00">
          </div>
          <div class="form-group">
            <label>Moneda</label>
            <select id="formCurrency">
              <option value="USD">USD ($)</option>
              <option value="PEN">PEN (S/)</option>
            </select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Horario</label>
            <input type="text" id="formSchedule" placeholder="ej: 10:00-14:00 / 14:00-18:00">
          </div>
          <div class="form-group">
            <label>Duración</label>
            <input type="text" id="formDuration" placeholder="ej: 1 día / 4 horas">
          </div>
        </div>
        <div class="form-group">
          <label>Palabras Clave / Alias (separadas por comas)</label>
          <input type="text" id="formAliases" placeholder="ej: huacachina, tubulares, dunas, sandboard">
        </div>
        <div class="form-group">
          <label>Inclusiones</label>
          <textarea id="formIncludes" rows="2" placeholder="ej: Transporte turístico, guía profesional, paseos en tubular..."></textarea>
        </div>
        <div class="form-group">
          <label>Exclusiones</label>
          <textarea id="formExcludes" rows="2" placeholder="ej: Boletos de ingreso no incluidos..."></textarea>
        </div>
        <div style="display:flex; justify-content: flex-end; gap: 8px; margin-top: 18px;">
          <button type="button" class="btn btn-secondary" onclick="closeModal('tourModal')">Cancelar</button>
          <button type="submit" class="btn btn-primary">Guardar Tour</button>
        </div>
      </form>

      <!-- Sección de Tarifas Especiales / Flexibles -->
      <div id="ratesSection" style="margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <h4 style="margin: 0; font-size: 15px; color: #0369a1;">Tarifas Especiales / Flexibles</h4>
            <p style="margin: 2px 0 0; font-size: 12px; color: var(--muted);">Precios para estudiantes, menores, promociones o tarifas personalizadas.</p>
          </div>
          <button type="button" id="btnAddRate" class="btn btn-secondary btn-sm" onclick="showRateForm()">+ Nueva Tarifa</button>
        </div>

        <div id="rateFormBox" style="display: none; background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 14px; margin-bottom: 14px;">
          <h5 id="rateFormTitle" style="margin: 0 0 10px; font-size: 13px; color: var(--text); font-weight: 700;">Agregar Tarifa Especial</h5>
          <input type="hidden" id="rateId" value="">
          <div class="form-row">
            <div class="form-group">
              <label>Categoría</label>
              <select id="rateCategory">
                <option value="student">Estudiante</option>
                <option value="child">Menor / Niño</option>
                <option value="promo">Promoción</option>
                <option value="adult">Adulto</option>
                <option value="custom">Otra personalizada</option>
              </select>
            </div>
            <div class="form-group">
              <label>Nombre de la Tarifa</label>
              <input type="text" id="rateName" placeholder="ej: Tarifa Estudiante Universitario">
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Precio</label>
              <input type="text" id="ratePrice" placeholder="ej: 25.00">
            </div>
            <div class="form-group">
              <label>Moneda</label>
              <select id="rateCurrency">
                <option value="USD">USD ($)</option>
                <option value="PEN">PEN (S/)</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label>Condiciones / Requisitos</label>
            <input type="text" id="rateConditions" placeholder="ej: Carnet universitario vigente o menores de 17 años">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Vigencia Desde (opcional)</label>
              <input type="date" id="rateValidFrom">
            </div>
            <div class="form-group">
              <label>Vigencia Hasta (opcional)</label>
              <input type="date" id="rateValidTo">
            </div>
          </div>
          <div class="form-group" style="display: flex; align-items: center; gap: 8px;">
            <input type="checkbox" id="rateIsActive" checked style="width: auto; margin: 0;">
            <label for="rateIsActive" style="margin: 0; font-weight: normal; cursor: pointer;">Tarifa activa (disponible para el bot)</label>
          </div>
          <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="hideRateForm()">Cancelar</button>
            <button type="button" class="btn btn-primary btn-sm" onclick="saveRate()">Guardar Tarifa</button>
          </div>
        </div>

        <div id="tourRatesList">
          <!-- Cargado dinámicamente -->
        </div>
      </div>
    </div>
  </div>

  <!-- Modal: Subir Archivo (Foto o Folleto) -->
  <div id="assetModal" class="modal-backdrop">
    <div class="modal">
      <div class="modal-header">
        <h3 id="modalAssetTitle" class="modal-title">Subir Archivo</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeModal('assetModal')">✕</button>
      </div>
      <form id="assetForm">
        <input type="hidden" id="assetEntityId">
        <input type="hidden" id="assetType">
        <p id="assetTourLabel" style="font-size: 14px; font-weight: 600; color: #0369a1; margin: 0 0 14px;"></p>
        <div class="form-group">
          <label id="assetFileLabel">Seleccionar Archivo</label>
          <input type="file" id="assetFileInput" required>
        </div>
        <div style="display:flex; justify-content: flex-end; gap: 8px; margin-top: 18px;">
          <button type="button" class="btn btn-secondary" onclick="closeModal('assetModal')">Cancelar</button>
          <button type="submit" class="btn btn-primary" id="btnUploadSubmit">Subir y Guardar</button>
        </div>
      </form>
    </div>
  </div>

  <div id="toast" class="toast"></div>

  <script>
    const CSRF_TOKEN = "{csrf_token}";
    let TOURS_DATA = [];

    function showToast(msg, type='success') {{
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'toast ' + type;
      t.style.display = 'block';
      setTimeout(() => {{ t.style.display = 'none'; }}, 3500);
    }}

    function openModal(id) {{
      document.getElementById(id).style.display = 'flex';
    }}

    function closeModal(id) {{
      document.getElementById(id).style.display = 'none';
    }}

    async function loadTours() {{
      const grid = document.getElementById('toursGrid');
      try {{
        const r = await fetch('/api/catalog/tours');
        if (!r.ok) throw new Error('Error al consultar catálogo');
        TOURS_DATA = await r.json();
        renderTours(TOURS_DATA);
      }} catch (err) {{
        grid.innerHTML = '<p style="color:var(--danger)">No se pudo cargar el catálogo de tours.</p>';
      }}
    }}

    function renderTours(tours) {{
      const grid = document.getElementById('toursGrid');
      grid.innerHTML = '';
      if (!tours.length) {{
        grid.innerHTML = '<p style="color:var(--muted)">No se encontraron tours con ese criterio.</p>';
        return;
      }}

      tours.forEach(t => {{
        const card = document.createElement('div');
        card.className = 'card';

        const priceHtml = t.official_price
          ? `<span class="price-tag">${{t.currency}} ${{t.official_price}}</span>`
          : `<span class="price-missing">Tarifa no fijada</span>`;

        const badgeCls = t.is_canonical ? 'badge-canonical' : 'badge-custom';
        const badgeTxt = t.is_canonical ? 'Canónico F1/F2' : 'Personalizado';

        const photoHtml = t.photo_filename
          ? `<img src="/images/${{t.photo_filename}}" class="thumb" alt="${{t.name}}"> <span style="color:var(--success)">📷 Foto lista</span>`
          : `<span style="color:var(--muted)">📷 Sin foto</span>`;

        const brochureHtml = t.brochure_filename
          ? `<a href="/brochures/${{t.brochure_filename}}" target="_blank" style="color:var(--primary); font-weight:600; text-decoration:none;">📄 Ver PDF</a>`
          : `<span style="color:var(--muted)">📄 Sin folleto</span>`;

        card.innerHTML = `
          <div>
            <div class="card-top">
              <div>
                <h3 class="tour-title">${{t.name}}</h3>
                <div class="tour-id">${{t.entity_id}}</div>
              </div>
              <span class="badge ${{badgeCls}}">${{badgeTxt}}</span>
            </div>
            <div class="tour-details">
              <div class="detail-row">
                <strong>Precio:</strong> ${{priceHtml}}
              </div>
              <div class="detail-row">
                <strong>Horario:</strong> <span>${{t.schedule || 'Por confirmar'}}</span>
              </div>
              ${{t.duration ? `<div class="detail-row"><strong>Duración:</strong> <span>${{t.duration}}</span></div>` : ''}}
            </div>
            <div class="assets-row">
              ${{photoHtml}}
              <span style="color:var(--border)">|</span>
              ${{brochureHtml}}
            </div>
          </div>
          <div class="card-actions">
            <button class="btn btn-secondary btn-sm" onclick="editTour('${{t.entity_id}}')">✏️ Editar</button>
            <button class="btn btn-secondary btn-sm" onclick="openUploadModal('${{t.entity_id}}', 'photo')">📷 Foto</button>
            <button class="btn btn-secondary btn-sm" onclick="openUploadModal('${{t.entity_id}}', 'brochure')">📄 Folleto</button>
            <button class="btn btn-danger btn-sm" onclick="deleteTour('${{t.entity_id}}')" title="Eliminar o desactivar este tour del bot">🗑️ Eliminar</button>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    document.getElementById('searchInput').addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase().trim();
      const filtered = TOURS_DATA.filter(t =>
        t.name.toLowerCase().includes(q) ||
        t.entity_id.toLowerCase().includes(q) ||
        (t.aliases && t.aliases.some(a => a.toLowerCase().includes(q)))
      );
      renderTours(filtered);
    }});

    document.getElementById('btnRefresh').addEventListener('click', loadTours);

    let CURRENT_TOUR_RATES = [];

    document.getElementById('btnNewTour').addEventListener('click', () => {{
      document.getElementById('tourForm').reset();
      document.getElementById('formIsEdit').value = '0';
      document.getElementById('formEntityId').disabled = false;
      document.getElementById('modalTourTitle').textContent = 'Registrar Nuevo Tour';
      hideRateForm();
      loadTourRates(null);
      openModal('tourModal');
    }});

    async function deleteTour(entityId) {{
      const t = TOURS_DATA.find(x => x.entity_id === entityId);
      const tourName = t ? t.name : entityId;
      const confirmMsg = '¿Eliminar o desactivar el tour "' + tourName + '" del bot?\\n\\n• Tours canónicos: quedan desactivados (no visibles en WhatsApp).\\n• Tours personalizados: se eliminan definitivamente.\\n\\nEsta acción se puede revertir volviendo a activarlo.';
      if (!confirm(confirmMsg)) return;
      try {{
        const r = await fetch(`/api/catalog/tours/${{entityId}}`, {{
          method: 'DELETE',
          headers: {{'X-Requested-With': 'XMLHttpRequest', 'X-Catalog-CSRF': CSRF_TOKEN}}
        }});
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || 'Error al eliminar');
        alert(d.message || 'Tour eliminado correctamente.');
        loadTours();
      }} catch(e) {{
        alert('Error: ' + e.message);
      }}
    }}

    function editTour(entityId) {{
      const t = TOURS_DATA.find(x => x.entity_id === entityId);
      if (!t) return;
      document.getElementById('formIsEdit').value = '1';
      document.getElementById('formEntityId').value = t.entity_id;
      document.getElementById('formEntityId').disabled = true;
      document.getElementById('formName').value = t.name;
      document.getElementById('formPrice').value = t.official_price || '';
      document.getElementById('formCurrency').value = t.currency || 'USD';
      document.getElementById('formSchedule').value = t.schedule || '';
      document.getElementById('formDuration').value = t.duration || '';
      document.getElementById('formAliases').value = (t.aliases || []).join(', ');
      document.getElementById('formIncludes').value = t.includes || '';
      document.getElementById('formExcludes').value = t.excludes || '';
      document.getElementById('modalTourTitle').textContent = 'Editar Tour: ' + t.name;
      hideRateForm();
      loadTourRates(t.entity_id);
      openModal('tourModal');
    }}

    function showRateForm(rateData = null) {{
      document.getElementById('rateFormBox').style.display = 'block';
      if (rateData) {{
        document.getElementById('rateFormTitle').textContent = 'Editar Tarifa Especial';
        document.getElementById('rateId').value = rateData.id || '';
        document.getElementById('rateCategory').value = rateData.rate_category || 'custom';
        document.getElementById('rateName').value = rateData.rate_name || '';
        document.getElementById('ratePrice').value = rateData.price != null ? rateData.price : '';
        document.getElementById('rateCurrency').value = rateData.currency || 'USD';
        document.getElementById('rateConditions').value = rateData.conditions || '';
        document.getElementById('rateValidFrom').value = rateData.valid_from || '';
        document.getElementById('rateValidTo').value = rateData.valid_to || '';
        document.getElementById('rateIsActive').checked = rateData.is_active !== 0 && rateData.is_active !== false;
      }} else {{
        document.getElementById('rateFormTitle').textContent = 'Agregar Tarifa Especial';
        document.getElementById('rateId').value = '';
        document.getElementById('rateCategory').value = 'student';
        document.getElementById('rateName').value = '';
        document.getElementById('ratePrice').value = '';
        document.getElementById('rateCurrency').value = document.getElementById('formCurrency').value || 'USD';
        document.getElementById('rateConditions').value = '';
        document.getElementById('rateValidFrom').value = '';
        document.getElementById('rateValidTo').value = '';
        document.getElementById('rateIsActive').checked = true;
      }}
    }}

    function hideRateForm() {{
      document.getElementById('rateFormBox').style.display = 'none';
      document.getElementById('rateId').value = '';
    }}

    async function loadTourRates(entityId) {{
      const listEl = document.getElementById('tourRatesList');
      if (!entityId) {{
        listEl.innerHTML = '<p style="color:var(--muted); font-size: 13px; margin: 4px 0;">Guarda el tour primero para asociar tarifas especiales.</p>';
        document.getElementById('btnAddRate').style.display = 'none';
        return;
      }}
      document.getElementById('btnAddRate').style.display = 'inline-flex';
      listEl.innerHTML = '<p style="color:var(--muted); font-size: 12px; margin: 4px 0;">Cargando tarifas...</p>';
      try {{
        const r = await fetch('/api/catalog/tours/' + encodeURIComponent(entityId) + '/rates?all=1');
        if (!r.ok) throw new Error('Error al cargar tarifas');
        const data = await r.json();
        CURRENT_TOUR_RATES = Array.isArray(data) ? data : data.rates;
        if (!Array.isArray(CURRENT_TOUR_RATES)) throw new Error('Respuesta de tarifas inválida');
        renderTourRates(CURRENT_TOUR_RATES);
      }} catch (err) {{
        listEl.innerHTML = '<p style="color:var(--danger); font-size: 12px; margin: 4px 0;">No se pudieron cargar las tarifas especiales.</p>';
      }}
    }}

    function escapeRateText(value) {{
      const node = document.createElement('span');
      node.textContent = String(value ?? '');
      return node.innerHTML;
    }}

    function renderTourRates(rates) {{
      const listEl = document.getElementById('tourRatesList');
      listEl.innerHTML = '';
      if (!rates || !rates.length) {{
        listEl.innerHTML = '<p style="color:var(--muted); font-size: 13px; margin: 4px 0;">No hay tarifas especiales registradas para este tour.</p>';
        return;
      }}

      const catBadges = {{
        student: {{ label: '🎓 Estudiante', cls: 'rate-badge-student' }},
        child: {{ label: '👶 Menor', cls: 'rate-badge-child' }},
        promo: {{ label: '🏷️ Promo', cls: 'rate-badge-promo' }},
        adult: {{ label: '👤 Adulto', cls: 'rate-badge-adult' }},
        custom: {{ label: '⭐ Especial', cls: 'rate-badge-custom' }}
      }};

      rates.forEach(rate => {{
        const item = document.createElement('div');
        item.className = 'rate-card';
        const b = catBadges[rate.rate_category] || catBadges.custom;
        const activeText = rate.is_active ? '<span style="color:var(--success); font-size: 11px; font-weight:600;">● Activa</span>' : '<span style="color:var(--muted); font-size: 11px; font-weight:600;">○ Inactiva</span>';
        const dateRange = (rate.valid_from || rate.valid_to)
          ? `<div style="font-size: 11px; color: var(--muted); margin-top: 2px;">📅 Vigencia: ${{escapeRateText(rate.valid_from || 'Inicio')}} al ${{escapeRateText(rate.valid_to || 'Siempre')}}</div>`
          : '';
        const condText = rate.conditions
          ? `<div style="font-size: 12px; color: #475569; margin-top: 2px;">ℹ️ ${{escapeRateText(rate.conditions)}}</div>`
          : '';

        item.innerHTML = `
          <div style="flex: 1;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span class="rate-badge ${{b.cls}}">${{b.label}}</span>
              <strong style="font-size: 13px;">${{escapeRateText(rate.rate_name)}}</strong>
              <span class="price-tag" style="font-size: 13px;">${{escapeRateText(rate.currency)}} ${{escapeRateText(rate.price)}}</span>
              ${{activeText}}
            </div>
            ${{condText}}
            ${{dateRange}}
          </div>
          <div style="display: flex; gap: 6px;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="editRateById(${{rate.id}})">✏️</button>
            <button type="button" class="btn btn-danger btn-sm" onclick="deleteRateById(${{rate.id}})">🗑️</button>
          </div>
        `;
        listEl.appendChild(item);
      }});
    }}

    function editRateById(rateId) {{
      const r = CURRENT_TOUR_RATES.find(x => x.id === rateId);
      if (r) {{
        showRateForm(r);
      }}
    }}

    async function saveRate() {{
      const entityId = document.getElementById('formEntityId').value.trim();
      if (!entityId) {{
        showToast('Debe guardar el tour primero', 'error');
        return;
      }}
      const rateIdVal = document.getElementById('rateId').value;
      const category = document.getElementById('rateCategory').value;
      const name = document.getElementById('rateName').value.trim();
      const priceVal = document.getElementById('ratePrice').value.trim();
      const currency = document.getElementById('rateCurrency').value;
      const conditions = document.getElementById('rateConditions').value.trim();
      const valid_from = document.getElementById('rateValidFrom').value || null;
      const valid_to = document.getElementById('rateValidTo').value || null;
      const is_active = document.getElementById('rateIsActive').checked ? 1 : 0;

      if (!name) {{
        showToast('Ingrese un nombre para la tarifa', 'error');
        return;
      }}
      const price = Number(priceVal);
      if (!priceVal || !Number.isFinite(price) || price < 0) {{
        showToast('Ingrese un precio numérico válido', 'error');
        return;
      }}

      const payload = {{
        rate_category: category, rate_name: name, price, currency, conditions,
        valid_from, valid_to, is_active
      }};
      if (rateIdVal) {{
        payload.id = parseInt(rateIdVal, 10);
      }}

      try {{
        const r = await fetch('/api/catalog/tours/' + encodeURIComponent(entityId) + '/rates', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            'X-Catalog-CSRF': CSRF_TOKEN
          }},
          body: JSON.stringify(payload)
        }});
        const res = await r.json();
        if (r.ok && res.ok) {{
          showToast('Tarifa guardada correctamente');
          hideRateForm();
          loadTourRates(entityId);
        }} else {{
          showToast(res.error || 'Error al guardar tarifa', 'error');
        }}
      }} catch (err) {{
        showToast('Error de conexión', 'error');
      }}
    }}

    async function deleteRateById(rateId) {{
      if (!confirm('¿Eliminar esta tarifa especial?')) return;
      try {{
        const r = await fetch('/api/catalog/rates/' + rateId, {{
          method: 'DELETE',
          headers: {{
            'X-Catalog-CSRF': CSRF_TOKEN
          }}
        }});
        const res = await r.json();
        if (r.ok && res.ok) {{
          showToast('Tarifa eliminada');
          const entityId = document.getElementById('formEntityId').value.trim();
          loadTourRates(entityId);
        }} else {{
          showToast(res.error || 'Error al eliminar tarifa', 'error');
        }}
      }} catch (err) {{
        showToast('Error de conexión', 'error');
      }}
    }}

    document.getElementById('tourForm').addEventListener('submit', async (e) => {{
      e.preventDefault();
      const entity_id = document.getElementById('formEntityId').value.trim();
      const name = document.getElementById('formName').value.trim();
      const official_price = document.getElementById('formPrice').value.trim();
      const currency = document.getElementById('formCurrency').value;
      const schedule = document.getElementById('formSchedule').value.trim();
      const duration = document.getElementById('formDuration').value.trim();
      const aliases = document.getElementById('formAliases').value;
      const includes = document.getElementById('formIncludes').value.trim();
      const excludes = document.getElementById('formExcludes').value.trim();

      const payload = {{
        entity_id, name, official_price, currency, schedule,
        duration, aliases, includes, excludes
      }};

      try {{
        const r = await fetch('/api/catalog/tours', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            'X-Catalog-CSRF': CSRF_TOKEN
          }},
          body: JSON.stringify(payload)
        }});
        const res = await r.json();
        if (r.ok && res.ok) {{
          showToast('Tour guardado exitosamente');
          closeModal('tourModal');
          loadTours();
        }} else {{
          showToast(res.error || 'Error al guardar tour', 'error');
        }}
      }} catch (err) {{
        showToast('Error de conexión con el servidor', 'error');
      }}
    }});

    function openUploadModal(entityId, assetType) {{
      const t = TOURS_DATA.find(x => x.entity_id === entityId);
      if (!t) return;
      document.getElementById('assetEntityId').value = entityId;
      document.getElementById('assetType').value = assetType;
      document.getElementById('assetTourLabel').textContent = t.name;
      document.getElementById('assetFileInput').value = '';
      if (assetType === 'photo') {{
        document.getElementById('modalAssetTitle').textContent = '📷 Subir Foto del Tour';
        document.getElementById('assetFileLabel').textContent = 'Seleccionar Imagen (JPG, PNG):';
        document.getElementById('assetFileInput').accept = 'image/jpeg,image/png';
      }} else {{
        document.getElementById('modalAssetTitle').textContent = '📄 Subir Folleto Oficial';
        document.getElementById('assetFileLabel').textContent = 'Seleccionar Folleto en PDF:';
        document.getElementById('assetFileInput').accept = 'application/pdf';
      }}
      openModal('assetModal');
    }}

    document.getElementById('assetForm').addEventListener('submit', async (e) => {{
      e.preventDefault();
      const entityId = document.getElementById('assetEntityId').value;
      const assetType = document.getElementById('assetType').value;
      const fileInput = document.getElementById('assetFileInput');
      if (!fileInput.files.length) return;

      const file = fileInput.files[0];
      const formData = new FormData();
      formData.append('file', file);
      formData.append('asset_type', assetType);

      const btn = document.getElementById('btnUploadSubmit');
      btn.disabled = true;
      btn.textContent = 'Subiendo...';

      try {{
        const r = await fetch(`/api/catalog/upload/${{entityId}}`, {{
          method: 'POST',
          headers: {{ 'X-Catalog-CSRF': CSRF_TOKEN }},
          body: formData
        }});
        const res = await r.json();
        if (r.ok && res.ok) {{
          showToast('Archivo subido y guardado exitosamente');
          closeModal('assetModal');
          loadTours();
        }} else {{
          showToast(res.error || 'Error al subir archivo', 'error');
        }}
      }} catch (err) {{
        showToast('Error de conexión', 'error');
      }} finally {{
        btn.disabled = false;
        btn.textContent = 'Subir y Guardar';
      }}
    }});

    // Cargar tours al iniciar
    loadTours();
  </script>
</body>
</html>"""

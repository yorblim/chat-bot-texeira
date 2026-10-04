"""
catalog_ui.py — Interfaz Web Moderna para Gestión de Catálogo y Tarifas de Texeira Travel.

Genera el HTML y Vanilla JS para /catalogo. Permite a los administradores
editar precios vigentes, horarios, registrar nuevos destinos turísticos,
gestionar tarifas especiales con control de vigencia y subir fotos y folletos
sincronizados con el chatbot de WhatsApp.
"""

def get_catalog_html(csrf_token: str) -> str:
    from admin_theme import decorate
    return decorate(f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Catálogo de Tours y Tarifas — Texeira Travel</title>
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
      max-width: 1180px;
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
    .btn:focus-visible {{
      outline: 2px solid var(--primary);
      outline-offset: 2px;
    }}
    .btn-primary {{
      background: var(--primary);
      color: white;
    }}
    .btn-primary:hover:not(:disabled) {{
      background: var(--primary-hover);
    }}
    .btn-primary:disabled {{
      opacity: 0.65;
      cursor: not-allowed;
    }}
    .btn-secondary {{
      background: white;
      border: 1px solid var(--border);
      color: var(--text);
    }}
    .btn-secondary:hover:not(:disabled) {{
      background: #f1f5f9;
    }}
    .btn-danger {{
      background: #fee2e2;
      border: 1px solid #fca5a5;
      color: #b91c1c;
    }}
    .btn-danger:hover:not(:disabled) {{
      background: #fca5a5;
      color: #7f1d1d;
    }}
    .btn-sm {{
      padding: 4px 10px;
      font-size: 12px;
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
      min-width: 220px;
    }}
    .search-box input {{
      width: 100%;
      padding: 10px 14px 10px 36px;
      font-size: 14px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: white;
    }}
    .search-box input:focus-visible {{
      outline: 2px solid var(--primary);
    }}
    .search-icon {{
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      pointer-events: none;
    }}
    .filter-group {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .select-input {{
      padding: 9px 12px;
      font-size: 13px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: white;
      color: var(--text);
      font-family: inherit;
    }}
    .select-input:focus-visible {{
      outline: 2px solid var(--primary);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
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
    .card.inactive-card {{
      opacity: 0.75;
      border-color: #cbd5e1;
      background: #fafafa;
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
      gap: 8px;
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
      white-space: nowrap;
    }}
    .badge-canonical {{
      background: #e0f2fe;
      color: #0369a1;
    }}
    .badge-custom {{
      background: #f3e8ff;
      color: #7e22ce;
    }}
    .badge-inactive {{
      background: #fee2e2;
      color: #991b1b;
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
      font-size: 14px;
      font-weight: 700;
      color: var(--success);
      background: #dcfce7;
      padding: 2px 8px;
      border-radius: 6px;
    }}
    .price-missing {{
      font-size: 12px;
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
      flex-wrap: wrap;
    }}

    /* Modales */
    .modal-backdrop {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.55);
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
      max-width: 740px;
      max-height: 90vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 20px 25px -5px rgba(0,0,0,0.15);
    }}
    .modal-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 22px;
      border-bottom: 1px solid var(--border);
      background: white;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .modal-title {{
      font-size: 17px;
      font-weight: 700;
      color: #0369a1;
      margin: 0;
    }}
    .modal-tabs {{
      display: flex;
      border-bottom: 1px solid var(--border);
      background: #f8fafc;
      padding: 0 22px;
      gap: 4px;
    }}
    .modal-tab-btn {{
      padding: 10px 16px;
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      font-size: 13px;
      font-weight: 600;
      color: var(--muted);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }}
    .modal-tab-btn:hover {{
      color: var(--text);
    }}
    .modal-tab-btn.active {{
      color: var(--primary);
      border-bottom-color: var(--primary);
      background: white;
      border-top-left-radius: 6px;
      border-top-right-radius: 6px;
    }}
    .modal-tab-btn:disabled {{
      opacity: 0.5;
      cursor: not-allowed;
    }}
    .tab-badge {{
      background: #e2e8f0;
      color: #334155;
      font-size: 11px;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 10px;
    }}
    .modal-tab-btn.active .tab-badge {{
      background: #e0f2fe;
      color: #0369a1;
    }}
    .modal-body {{
      padding: 22px;
      overflow-y: auto;
      flex: 1;
    }}
    .tab-pane {{
      display: none;
    }}
    .tab-pane.active {{
      display: block;
    }}

    .form-section-title {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #0369a1;
      margin: 16px 0 10px;
      padding-bottom: 4px;
      border-bottom: 1px solid #f1f5f9;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .form-section-title:first-child {{
      margin-top: 0;
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
      background: white;
    }}
    .form-group input:focus-visible, .form-group textarea:focus-visible, .form-group select:focus-visible {{
      outline: 2px solid var(--primary);
    }}
    .form-group textarea {{
      resize: vertical;
    }}
    .form-help {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 4px;
      line-height: 1.4;
    }}
    .field-req {{
      color: var(--danger);
      font-weight: bold;
    }}
    .form-row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .form-actions-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      flex-wrap: wrap;
      gap: 12px;
    }}

    /* Tarifas Cards */
    .rate-card {{
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
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

    .rate-status {{
      display: inline-block;
      font-size: 11px;
      font-weight: 600;
      padding: 2px 7px;
      border-radius: 4px;
      white-space: nowrap;
    }}
    .rate-status-active {{ background: #dcfce7; color: #15803d; }}
    .rate-status-scheduled {{ background: #e0f2fe; color: #0369a1; }}
    .rate-status-expired {{ background: #fef3c7; color: #b45309; }}
    .rate-status-disabled {{ background: #f1f5f9; color: #64748b; }}

    .rate-card-actions {{
      display: flex;
      gap: 6px;
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

    /* Responsive Móvil (320px - 640px) */
    @media (max-width: 640px) {{
      body {{ padding: 12px !important; }}
      header {{ padding: 14px 16px; margin-bottom: 16px; }}
      h1 {{ font-size: 18px; }}
      .grid {{ grid-template-columns: 1fr; gap: 14px; }}
      .form-row {{ grid-template-columns: 1fr; gap: 8px; }}
      .modal-backdrop {{ padding: 8px; }}
      .modal {{ max-height: 96vh; }}
      .modal-header {{ padding: 12px 14px; }}
      .modal-tabs {{ padding: 0 12px; }}
      .modal-tab-btn {{ padding: 8px 10px; font-size: 12px; }}
      .modal-body {{ padding: 14px; }}
      .form-actions-bar {{ position: sticky; bottom: 0; background: white; padding-top: 12px; padding-bottom: 6px; z-index: 5; box-shadow: 0 -4px 6px -2px rgba(0,0,0,0.05); }}
      .rate-card {{ flex-direction: column; align-items: flex-start; gap: 10px; word-break: break-word; }}
      .rate-card-actions {{ width: 100%; display: flex; justify-content: flex-end; gap: 6px; }}
      .toolbar {{ flex-direction: column; align-items: stretch; }}
      .search-box {{ max-width: 100%; }}
      .filter-group {{ width: 100%; justify-content: space-between; }}
      .filter-group select {{ flex: 1; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>🗺️ Catálogo de Tours y Tarifas</h1>
        <p class="subtitle">Texeira Travel — Gestión de precios, horarios, folletos e imágenes sincronizados con el chatbot</p>
      </div>
      <div>
        <button id="btnNewTour" class="btn btn-primary">+ Nuevo Tour</button>
      </div>
    </header>

    <div class="toolbar">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="Buscar tour por nombre o destino...">
      </div>
      <div class="filter-group">
        <label for="filterStatus" style="font-size:13px; font-weight:600; color:var(--muted);">Estado:</label>
        <select id="filterStatus" class="select-input">
          <option value="active" selected>Solo activos (visibles)</option>
          <option value="all">Todos los tours</option>
          <option value="inactive">Solo inactivos / archivados</option>
        </select>
        <button id="btnRefresh" class="btn btn-secondary">🔄 Actualizar</button>
      </div>
    </div>

    <div id="toursGrid" class="grid">
      <!-- Se carga dinámicamente con JavaScript -->
    </div>
  </div>

  <!-- Modal: Crear / Editar Tour con Pestañas Independientes -->
  <div id="tourModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modalTourTitle">
    <div class="modal">
      <div class="modal-header">
        <h3 id="modalTourTitle" class="modal-title">Editar Tour</h3>
        <button type="button" class="btn btn-secondary btn-sm" onclick="requestCloseTourModal()" aria-label="Cerrar ventana">✕</button>
      </div>

      <!-- Barra de Pestañas -->
      <div class="modal-tabs">
        <button type="button" id="tabBtnTourData" class="modal-tab-btn active" onclick="switchModalTab('tourData')">
          📋 Datos del Tour
        </button>
        <button type="button" id="tabBtnTourRates" class="modal-tab-btn" onclick="switchModalTab('tourRates')">
          🏷️ Tarifas Especiales <span id="ratesCountBadge" class="tab-badge">0</span>
        </button>
      </div>

      <div class="modal-body">
        <!-- PESTAÑA 1: DATOS DEL TOUR -->
        <div id="tabPaneTourData" class="tab-pane active">
          <form id="tourForm">
            <input type="hidden" id="formIsEdit" value="0">

            <div class="form-section-title">Información Principal</div>
            <div class="form-group">
              <label for="formName">Nombre del Tour <span class="field-req">*</span></label>
              <input type="text" id="formName" placeholder="ej: Tour Huacachina & Tubulares" required>
            </div>

            <div class="form-group" style="display: flex; align-items: flex-start; gap: 8px; margin-top: 8px;">
              <input type="checkbox" id="formIsActive" checked style="width: auto; margin-top: 3px; cursor: pointer;">
              <div>
                <label for="formIsActive" style="margin: 0; font-weight: 600; cursor: pointer;">Tour activo (visible para el bot en WhatsApp y catálogo)</label>
                <div class="form-help">Si se desactiva, el bot no ofrecerá este tour ni responderá consultas sobre él.</div>
              </div>
            </div>

            <div class="form-section-title">Tarifa Base y Tiempos</div>
            <div class="form-row">
              <div class="form-group">
                <label for="formPrice">Precio por persona</label>
                <input type="text" id="formPrice" placeholder="ej: 35.00">
                <div class="form-help">Si se deja vacío, el precio queda por confirmar.</div>
              </div>
              <div class="form-group">
                <label for="formCurrency">Moneda</label>
                <select id="formCurrency" class="select-input">
                  <option value="USD">USD ($)</option>
                  <option value="PEN">PEN (S/)</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="formSchedule">Horario</label>
                <input type="text" id="formSchedule" placeholder="ej: 10:00-14:00 / 14:00-18:00">
                <div class="form-help">Ej: 04:30 - 17:00 / Horario de recojo en intervalo.</div>
              </div>
              <div class="form-group">
                <label for="formDuration">Duración</label>
                <input type="text" id="formDuration" placeholder="ej: Full Day / 1 día / 4 días y 3 noches">
                <div class="form-help">Ej: Full Day, Medio día, 4 días / 3 noches.</div>
              </div>
            </div>

            <div class="form-section-title">Detalles del Itinerario</div>
            <div class="form-group">
              <label for="formIncludes">Qué incluye</label>
              <textarea id="formIncludes" rows="4" placeholder="ej: Transporte turístico ida y vuelta, guía profesional certificado, paseos en tubular..."></textarea>
            </div>
            <div class="form-group">
              <label for="formExcludes">Qué no incluye</label>
              <textarea id="formExcludes" rows="4" placeholder="ej: Boletos de ingreso al área protegida, propinas voluntarias, alimentación no especificada..."></textarea>
            </div>

            <!-- Bloque Desplegable Opciones Avanzadas -->
            <details id="advancedTourOptions" style="margin-top: 16px; border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; background: #f8fafc;">
              <summary style="font-size: 13px; font-weight: 600; color: #334155; cursor: pointer; user-select: none;">
                ⚙️ Opciones avanzadas (ID técnico y otros nombres)
              </summary>
              <div style="margin-top: 12px;">
                <div class="form-group">
                  <label for="formEntityId">Identificador Único (entity_id) <span class="field-req">*</span></label>
                  <input type="text" id="formEntityId" placeholder="ej: tour-huacachina" required>
                  <div class="form-help">Código técnico permanente en el sistema. Al editar un tour existente, este valor se mantiene fijo.</div>
                </div>
                <div class="form-group">
                  <label for="formAliases">Otros nombres para encontrar este tour</label>
                  <textarea id="formAliases" rows="2" placeholder="ej: huacachina, tubulares, dunas, sandboard (separados por comas)"></textarea>
                  <div class="form-help">Palabras clave o alias alternativos que los turistas suelen usar para buscar este destino.</div>
                </div>
              </div>
            </details>

            <div class="form-actions-bar">
              <div style="font-size: 12px; color: var(--muted);">
                ℹ️ Las tarifas especiales se configuran y guardan por separado en su propia pestaña.
              </div>
              <div style="display:flex; gap: 8px;">
                <button type="button" class="btn btn-secondary" onclick="requestCloseTourModal()">Cancelar</button>
                <button type="submit" id="btnSaveTour" class="btn btn-primary">Guardar datos del tour</button>
              </div>
            </div>
          </form>
        </div>

        <!-- PESTAÑA 2: TARIFAS ESPECIALES -->
        <div id="tabPaneTourRates" class="tab-pane">
          <div id="ratesSection">
            <!-- Referencia de Tarifa Base del Tour -->
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: 13px; color: #166534; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
              <div>
                <strong>Tarifa base oficial del tour:</strong>
                <span id="ratesTourBaseRef" class="price-tag" style="margin-left: 6px;">Por confirmar</span>
              </div>
              <div style="font-size: 12px; color: #15803d;">
                ℹ️ Precios alternativos para estudiantes, niños o promociones
              </div>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <div>
                <h4 style="margin: 0; font-size: 15px; color: #0369a1;">Lista de Tarifas Especiales</h4>
                <p style="margin: 2px 0 0; font-size: 12px; color: var(--muted);">Precios diferenciados evaluados por el bot según requisitos del cliente.</p>
              </div>
              <button type="button" id="btnAddRate" class="btn btn-secondary btn-sm" onclick="showRateForm()">+ Añadir tarifa</button>
            </div>

            <!-- Formulario de Tarifa Especial (Oculto por defecto) -->
            <div id="rateFormBox" style="display: none; background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px;">
              <h5 id="rateFormTitle" style="margin: 0 0 12px; font-size: 14px; color: #0369a1; font-weight: 700;">Añadir Tarifa Especial</h5>
              <input type="hidden" id="rateId" value="">
              <div class="form-row">
                <div class="form-group">
                  <label for="rateCategory">Categoría <span class="field-req">*</span></label>
                  <select id="rateCategory" class="select-input">
                    <option value="student">Estudiante</option>
                    <option value="child">Menor / Niño</option>
                    <option value="promo">Promoción</option>
                    <option value="adult">Adulto</option>
                    <option value="custom">Otra personalizada</option>
                  </select>
                </div>
                <div class="form-group">
                  <label for="rateName">Nombre de la Tarifa <span class="field-req">*</span></label>
                  <input type="text" id="rateName" placeholder="ej: Tarifa Estudiante Universitario">
                </div>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label for="ratePrice">Precio final de esta tarifa <span class="field-req">*</span></label>
                  <input type="text" id="ratePrice" placeholder="ej: 25.00">
                  <div class="form-help">Precio total por persona para esta tarifa (no es un descuento porcentual).</div>
                </div>
                <div class="form-group">
                  <label for="rateCurrency">Moneda <span class="field-req">*</span></label>
                  <select id="rateCurrency" class="select-input">
                    <option value="USD">USD ($)</option>
                    <option value="PEN">PEN (S/)</option>
                  </select>
                </div>
              </div>

              <div class="form-group">
                <label for="rateConditions">Condiciones / Requisitos</label>
                <textarea id="rateConditions" rows="3" placeholder="ej: Carnet universitario vigente de pregrado nacional o internacional, o menores de 17 años con documento de identidad"></textarea>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label for="rateValidFrom">Vigencia Desde (opcional)</label>
                  <input type="date" id="rateValidFrom">
                  <div class="form-help">Sin fecha = disponible desde siempre.</div>
                </div>
                <div class="form-group">
                  <label for="rateValidTo">Vigencia Hasta (opcional)</label>
                  <input type="date" id="rateValidTo">
                  <div class="form-help">Sin fecha = sin fecha de vencimiento.</div>
                </div>
              </div>

              <div class="form-group" style="display: flex; align-items: center; gap: 8px; margin-top: 6px;">
                <input type="checkbox" id="rateIsActive" checked style="width: auto; margin: 0; cursor: pointer;">
                <label for="rateIsActive" style="margin: 0; font-weight: 600; cursor: pointer;">Habilitar esta tarifa</label>
              </div>

              <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border);">
                <button type="button" id="btnCancelRate" class="btn btn-secondary btn-sm" onclick="cancelRateEdit()">Cancelar tarifa</button>
                <button type="button" id="btnSaveRate" class="btn btn-primary btn-sm" onclick="saveRate()">Guardar esta tarifa</button>
              </div>
            </div>

            <!-- Contenedor de la lista de tarifas -->
            <div id="tourRatesList">
              <!-- Cargado dinámicamente -->
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal: Subir Archivo (Foto o Folleto) -->
  <div id="assetModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modalAssetTitle">
    <div class="modal" style="max-width: 520px;">
      <div class="modal-header">
        <h3 id="modalAssetTitle" class="modal-title">Subir Archivo</h3>
        <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal('assetModal')" aria-label="Cerrar">✕</button>
      </div>
      <form id="assetForm">
        <div class="modal-body">
          <input type="hidden" id="assetEntityId">
          <input type="hidden" id="assetType">
          <p id="assetTourLabel" style="font-size: 14px; font-weight: 600; color: #0369a1; margin: 0 0 14px;"></p>
          <div class="form-group">
            <label id="assetFileLabel" for="assetFileInput">Seleccionar Archivo</label>
            <input type="file" id="assetFileInput" required>
          </div>
        </div>
        <div style="display:flex; justify-content: flex-end; gap: 8px; padding: 14px 20px; border-top: 1px solid var(--border); background: #f8fafc;">
          <button type="button" class="btn btn-secondary" onclick="closeModal('assetModal')">Cancelar</button>
          <button type="submit" class="btn btn-primary" id="btnUploadSubmit">Subir y Guardar</button>
        </div>
      </form>
    </div>
  </div>

  <div id="toast" class="toast" role="status" aria-live="polite"></div>

  <script>
    const CSRF_TOKEN = "{csrf_token}";
    let TOURS_DATA = [];
    let CURRENT_TOUR_RATES = [];
    let lastFocusedElement = null;

    // Control de sesión del editor y secuencia de peticiones de tarifas
    let currentEditorSessionId = 0;
    let currentRateEditorSessionId = 0;
    let ratesRequestCounter = 0;

    // Snapshot para protección contra pérdida accidental de borradores
    let initialTourSnapshot = null;
    let initialRateSnapshot = null;

    function getConfirmedTourData() {{
      if (initialTourSnapshot) {{
        try {{
          return JSON.parse(initialTourSnapshot);
        }} catch (e) {{}}
      }}
      return null;
    }}

    function restoreTourFormFromSnapshot() {{
      if (!initialTourSnapshot) return;
      try {{
        const snap = JSON.parse(initialTourSnapshot);
        const setVal = (id, val) => {{
          const el = document.getElementById(id);
          if (el) el.value = val ?? '';
        }};
        setVal('formEntityId', snap.entity_id);
        setVal('formName', snap.name);
        setVal('formPrice', snap.price);
        setVal('formCurrency', snap.currency || 'USD');
        setVal('formSchedule', snap.schedule);
        setVal('formDuration', snap.duration);
        setVal('formAliases', snap.aliases);
        setVal('formIncludes', snap.includes);
        setVal('formExcludes', snap.excludes);
        const activeEl = document.getElementById('formIsActive');
        if (activeEl) activeEl.checked = !!snap.is_active;
      }} catch (e) {{}}
    }}

    function updateRatesTourBaseRef() {{
      const refEl = document.getElementById('ratesTourBaseRef');
      if (!refEl) return;
      const confirmed = getConfirmedTourData();
      const hasPrice = confirmed && confirmed.price !== '' && confirmed.price != null;
      if (hasPrice) {{
        refEl.textContent = (confirmed.currency || 'USD') + ' ' + confirmed.price;
      }} else {{
        refEl.textContent = 'Por confirmar';
      }}
    }}

    function showToast(msg, type='success') {{
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'toast ' + type;
      t.style.display = 'block';
      setTimeout(() => {{ t.style.display = 'none'; }}, 3500);
    }}

    function safeFocus(el) {{
      if (el && typeof el.focus === 'function') {{
        try {{ el.focus(); }} catch (e) {{}}
      }}
    }}

    function openModal(id) {{
      lastFocusedElement = document.activeElement;
      const m = document.getElementById(id);
      m.style.display = 'flex';
      const focusable = m && typeof m.querySelector === 'function' ? m.querySelector('input:not([type=hidden]):not([disabled]), textarea, select, button') : null;
      safeFocus(focusable);
    }}

    function closeModal(id) {{
      if (id === 'tourModal') {{
        currentEditorSessionId++;
        ratesRequestCounter++;
      }}
      document.getElementById(id).style.display = 'none';
      safeFocus(lastFocusedElement);
    }}

    // Cálculo de fecha actual en zona horaria oficial de Lima (UTC-5 permanente, sin DST)
    function getLimaDateStr() {{
      const now = new Date();
      // now.getTime() representa el instante absoluto en milisegundos UTC.
      // Restar 5 horas da el calendario oficial de Lima con independencia de la zona horaria del navegador.
      const lima = new Date(now.getTime() - (5 * 3600000));
      return lima.toISOString().slice(0, 10);
    }}

    // Evaluación rigurosa del estado de vigencia de una tarifa
    function getRateStatusInfo(rate) {{
      if (rate.is_active === 0 || rate.is_active === false || rate.is_active === '0') {{
        return {{ label: '○ Deshabilitada', cls: 'rate-status-disabled' }};
      }}
      const today = getLimaDateStr();
      if (rate.valid_from && today < rate.valid_from) {{
        return {{ label: '⏱️ Programada (desde ' + escapeRateText(rate.valid_from) + ')', cls: 'rate-status-scheduled' }};
      }}
      if (rate.valid_to && today > rate.valid_to) {{
        return {{ label: '⚠️ Vencida (' + escapeRateText(rate.valid_to) + ')', cls: 'rate-status-expired' }};
      }}
      return {{ label: '● Vigente', cls: 'rate-status-active' }};
    }}

    function getTourFormSnapshot() {{
      return JSON.stringify({{
        entity_id: (document.getElementById('formEntityId').value || '').trim(),
        name: (document.getElementById('formName').value || '').trim(),
        price: (document.getElementById('formPrice').value || '').trim(),
        currency: document.getElementById('formCurrency').value,
        schedule: (document.getElementById('formSchedule').value || '').trim(),
        duration: (document.getElementById('formDuration').value || '').trim(),
        aliases: (document.getElementById('formAliases').value || '').trim(),
        includes: (document.getElementById('formIncludes').value || '').trim(),
        excludes: (document.getElementById('formExcludes').value || '').trim(),
        is_active: document.getElementById('formIsActive').checked
      }});
    }}

    function isTourFormDirty() {{
      if (!initialTourSnapshot) return false;
      return getTourFormSnapshot() !== initialTourSnapshot;
    }}

    function getRateFormSnapshot() {{
      return JSON.stringify({{
        id: document.getElementById('rateId').value,
        category: document.getElementById('rateCategory').value,
        name: (document.getElementById('rateName').value || '').trim(),
        price: (document.getElementById('ratePrice').value || '').trim(),
        currency: document.getElementById('rateCurrency').value,
        conditions: (document.getElementById('rateConditions').value || '').trim(),
        valid_from: document.getElementById('rateValidFrom').value,
        valid_to: document.getElementById('rateValidTo').value,
        is_active: document.getElementById('rateIsActive').checked
      }});
    }}

    function isRateFormDirty() {{
      const formBox = document.getElementById('rateFormBox');
      if (!formBox || formBox.style.display === 'none') return false;
      if (!initialRateSnapshot) return false;
      return getRateFormSnapshot() !== initialRateSnapshot;
    }}

    function requestCloseTourModal() {{
      if (isTourFormDirty() || isRateFormDirty()) {{
        const msg = isTourFormDirty() && isRateFormDirty()
          ? 'Tienes cambios sin guardar en los datos del tour y en la tarifa en edición.\\n\\n¿Deseas descartar todos los cambios y cerrar?'
          : (isTourFormDirty()
              ? 'Tienes cambios sin guardar en los datos del tour.\\n\\n¿Deseas descartar esos cambios y cerrar?'
              : 'Tienes una tarifa en edición sin guardar.\\n\\n¿Deseas descartar la tarifa y cerrar?');
        if (!confirm(msg)) return;
        restoreTourFormFromSnapshot();
        hideRateForm();
      }}
      closeModal('tourModal');
    }}

    function switchModalTab(tabKey) {{
      const tabTourData = document.getElementById('tabPaneTourData');
      const tabTourRates = document.getElementById('tabPaneTourRates');
      const btnTourData = document.getElementById('tabBtnTourData');
      const btnTourRates = document.getElementById('tabBtnTourRates');

      if (tabKey === 'tourRates') {{
        // Si va a tarifas pero hay cambios pendientes en los datos del tour
        if (isTourFormDirty()) {{
          if (!confirm('Tienes cambios sin guardar en los datos del tour.\\n\\n¿Deseas descartarlos para ver las tarifas especiales, o permanecer aquí para guardarlos primero?')) {{
            return;
          }}
          // Restaurar valores confirmados al descartar cambios no guardados
          restoreTourFormFromSnapshot();
        }}
        tabTourData.classList.remove('active');
        tabTourRates.classList.add('active');
        btnTourData.classList.remove('active');
        btnTourRates.classList.add('active');

        // Actualizar referencia visual de la tarifa base usando exclusivamente datos confirmados
        updateRatesTourBaseRef();
      }} else {{
        // Si va a datos del tour pero hay una tarifa en edición sin guardar
        if (isRateFormDirty()) {{
          if (!confirm('Tienes una tarifa en edición sin guardar.\\n\\n¿Deseas descartar los cambios de esta tarifa para volver a los datos del tour?')) {{
            return;
          }}
          hideRateForm();
        }}
        tabTourRates.classList.remove('active');
        tabTourData.classList.add('active');
        btnTourRates.classList.remove('active');
        btnTourData.classList.add('active');
      }}
    }}

    // Tecla Escape para cerrar con comprobación de borrador
    if (typeof document.addEventListener === 'function') {{
      document.addEventListener('keydown', (e) => {{
        if (e.key === 'Escape') {{
          const tourModal = document.getElementById('tourModal');
          if (tourModal && tourModal.style.display === 'flex') {{
            requestCloseTourModal();
          }}
          const assetModal = document.getElementById('assetModal');
          if (assetModal && assetModal.style.display === 'flex') {{
            closeModal('assetModal');
          }}
        }}
      }});
    }}

    // Cierre al hacer clic en el backdrop con comprobación de borrador
    document.getElementById('tourModal').addEventListener('click', (e) => {{
      if (e.target.id === 'tourModal') {{
        requestCloseTourModal();
      }}
    }});

    async function loadTours() {{
      const grid = document.getElementById('toursGrid');
      try {{
        // Consultar con ?all=1 para obtener todos los tours (activos e inactivos)
        const r = await fetch('/api/catalog/tours?all=1');
        if (!r.ok) throw new Error('Error al consultar catálogo');
        TOURS_DATA = await r.json();
        filterAndRenderTours();
      }} catch (err) {{
        grid.innerHTML = '<p style="color:var(--danger)">No se pudo cargar el catálogo de tours.</p>';
      }}
    }}

    function filterAndRenderTours() {{
      const q = (document.getElementById('searchInput').value || '').toLowerCase().trim();
      const statusFilter = document.getElementById('filterStatus').value;

      const filtered = TOURS_DATA.filter(t => {{
        const matchesQuery = !q ||
          t.name.toLowerCase().includes(q) ||
          t.entity_id.toLowerCase().includes(q) ||
          (t.aliases && t.aliases.some(a => a.toLowerCase().includes(q)));

        const isActive = t.is_active !== false && t.is_active !== 0;
        let matchesStatus = true;
        if (statusFilter === 'active') matchesStatus = isActive;
        else if (statusFilter === 'inactive') matchesStatus = !isActive;

        return matchesQuery && matchesStatus;
      }});

      renderTours(filtered);
    }}

    function renderTours(tours) {{
      const grid = document.getElementById('toursGrid');
      grid.innerHTML = '';
      if (!tours.length) {{
        grid.innerHTML = '<p style="color:var(--muted)">No se encontraron tours con los criterios seleccionados.</p>';
        return;
      }}

      tours.forEach(t => {{
        const card = document.createElement('div');
        const isActive = t.is_active !== false && t.is_active !== 0;
        card.className = 'card' + (isActive ? '' : ' inactive-card');

        const priceHtml = t.official_price
          ? `<span class="price-tag">${{escapeRateText(t.currency)}} ${{escapeRateText(t.official_price)}}</span>`
          : `<span class="price-missing">Tarifa por confirmar</span>`;

        const badgeCls = t.is_canonical ? 'badge-canonical' : 'badge-custom';
        const badgeTxt = t.is_canonical ? 'Canónico F1/F2' : 'Personalizado';
        const statusBadge = isActive
          ? ''
          : `<span class="badge badge-inactive">⏸️ Inactivo</span>`;

        const photoHtml = t.photo_filename
          ? `<img src="/images/${{escapeRateText(t.photo_filename)}}" class="thumb" alt="${{escapeRateText(t.name)}}"> <span style="color:var(--success)">📷 Foto lista</span>`
          : `<span style="color:var(--muted)">📷 Sin foto</span>`;

        const brochureHtml = t.brochure_filename
          ? `<a href="/brochures/${{escapeRateText(t.brochure_filename)}}" target="_blank" style="color:var(--primary); font-weight:600; text-decoration:none;">📄 Ver PDF</a>`
          : `<span style="color:var(--muted)">📄 Sin folleto</span>`;

        card.innerHTML = `
          <div>
            <div class="card-top">
              <div style="flex:1;min-width:0;padding-right:8px;">
                <h3 class="tour-title">${{escapeRateText(t.name)}}</h3>
                <div class="tour-id">ID: ${{escapeRateText(t.entity_id)}}</div>
              </div>
              <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                <span class="badge ${{badgeCls}}">${{badgeTxt}}</span>
                ${{statusBadge}}
              </div>
            </div>
            <div class="tour-details">
              <div class="detail-row">
                <strong>Precio base:</strong> ${{priceHtml}}
              </div>
              <div class="detail-row">
                <strong>Horario:</strong> <span>${{escapeRateText(t.schedule || 'Por confirmar')}}</span>
              </div>
              ${{t.duration ? `<div class="detail-row"><strong>Duración:</strong> <span>${{escapeRateText(t.duration)}}</span></div>` : ''}}
            </div>
            <div class="assets-row">
              ${{photoHtml}}
              <span style="color:var(--border)">|</span>
              ${{brochureHtml}}
            </div>
          </div>
          <div class="card-actions">
            <button class="btn btn-secondary btn-sm" onclick="editTour('${{escapeRateText(t.entity_id)}}')">✏️ Editar</button>
            <button class="btn btn-secondary btn-sm" onclick="openUploadModal('${{escapeRateText(t.entity_id)}}', 'photo')">📷 Foto</button>
            <button class="btn btn-secondary btn-sm" onclick="openUploadModal('${{escapeRateText(t.entity_id)}}', 'brochure')">📄 Folleto</button>
            <button class="btn btn-danger btn-sm" onclick="deleteTour('${{escapeRateText(t.entity_id)}}')" title="Eliminar o desactivar este tour">${{isActive ? '🗑️ Desactivar' : '🗑️ Eliminar'}}</button>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    document.getElementById('searchInput').addEventListener('input', filterAndRenderTours);
    document.getElementById('filterStatus').addEventListener('change', filterAndRenderTours);
    document.getElementById('btnRefresh').addEventListener('click', loadTours);

    document.getElementById('btnNewTour').addEventListener('click', () => {{
      currentEditorSessionId++;
      ratesRequestCounter++;
      document.getElementById('tourForm').reset();
      document.getElementById('formIsEdit').value = '0';
      document.getElementById('formEntityId').value = '';
      document.getElementById('formEntityId').disabled = false;
      document.getElementById('formIsActive').checked = true;
      document.getElementById('modalTourTitle').textContent = 'Registrar Nuevo Tour';

      const adv = document.getElementById('advancedTourOptions');
      if (adv) adv.open = true; // Abierto por defecto para ingresar el entity_id requerido

      hideRateForm();
      loadTourRates(null);
      switchModalTab('tourData');
      initialTourSnapshot = getTourFormSnapshot();
      updateRatesTourBaseRef();
      openModal('tourModal');
    }});

    async function deleteTour(entityId) {{
      const t = TOURS_DATA.find(x => x.entity_id === entityId);
      const tourName = t ? t.name : entityId;
      const confirmMsg = '¿Eliminar o desactivar el tour "' + tourName + '" del bot?\\n\\n• Tours canónicos: quedan desactivados (no visibles en WhatsApp).\\n• Tours personalizados: se eliminan definitivamente.\\n\\nEsta acción se puede revertir volviendo a activarlo.';
      if (!confirm(confirmMsg)) return;
      try {{
        const r = await fetch(`/api/catalog/tours/${{encodeURIComponent(entityId)}}`, {{
          method: 'DELETE',
          headers: {{'X-Requested-With': 'XMLHttpRequest', 'X-Catalog-CSRF': CSRF_TOKEN}}
        }});
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || 'Error al eliminar');
        showToast(d.message || 'Tour eliminado o desactivado correctamente.');
        loadTours();
      }} catch(e) {{
        showToast('Error: ' + e.message, 'error');
      }}
    }}

    function editTour(entityId) {{
      const t = TOURS_DATA.find(x => x.entity_id === entityId);
      if (!t) return;
      currentEditorSessionId++;
      ratesRequestCounter++;
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
      document.getElementById('formIsActive').checked = (t.is_active !== false && t.is_active !== 0);
      document.getElementById('modalTourTitle').textContent = 'Editar Tour: ' + t.name;

      const adv = document.getElementById('advancedTourOptions');
      if (adv) adv.open = false; // Cerrado al editar para mantener limpio el formulario

      hideRateForm();
      switchModalTab('tourData');
      initialTourSnapshot = getTourFormSnapshot();
      updateRatesTourBaseRef();
      loadTourRates(t.entity_id);
      openModal('tourModal');
    }}

    function showRateForm(rateData = null) {{
      if (isRateFormDirty()) {{
        if (!confirm('Tienes cambios sin guardar en esta tarifa.\\n\\n¿Deseas descartar los cambios?')) {{
          return;
        }}
      }}
      currentRateEditorSessionId++;
      const saveBtn = document.getElementById('btnSaveRate');
      if (saveBtn) {{
        saveBtn.disabled = false;
        saveBtn.textContent = 'Guardar esta tarifa';
      }}
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
        document.getElementById('rateIsActive').checked = (rateData.is_active !== 0 && rateData.is_active !== false);
      }} else {{
        const confirmed = getConfirmedTourData();
        const baseCurrency = (confirmed && confirmed.currency) ? confirmed.currency : (document.getElementById('formCurrency').value || 'USD');
        document.getElementById('rateFormTitle').textContent = 'Añadir Tarifa Especial';
        document.getElementById('rateId').value = '';
        document.getElementById('rateCategory').value = 'student';
        document.getElementById('rateName').value = '';
        document.getElementById('ratePrice').value = '';
        document.getElementById('rateCurrency').value = baseCurrency;
        document.getElementById('rateConditions').value = '';
        document.getElementById('rateValidFrom').value = '';
        document.getElementById('rateValidTo').value = '';
        document.getElementById('rateIsActive').checked = true;
      }}
      initialRateSnapshot = getRateFormSnapshot();
      safeFocus(document.getElementById('rateName'));
    }}

    function hideRateForm() {{
      currentRateEditorSessionId++;
      document.getElementById('rateFormBox').style.display = 'none';
      document.getElementById('rateId').value = '';
      initialRateSnapshot = null;
      const saveBtn = document.getElementById('btnSaveRate');
      if (saveBtn) {{
        saveBtn.disabled = false;
        saveBtn.textContent = 'Guardar esta tarifa';
      }}
    }}

    function cancelRateEdit() {{
      if (isRateFormDirty()) {{
        if (!confirm('Tienes cambios sin guardar en esta tarifa.\\n\\n¿Deseas descartar los cambios?')) return;
      }}
      hideRateForm();
    }}

    async function loadTourRates(entityId) {{
      const listEl = document.getElementById('tourRatesList');
      const badgeEl = document.getElementById('ratesCountBadge');
      const btnAdd = document.getElementById('btnAddRate');
      const tabBtn = document.getElementById('tabBtnTourRates');

      if (!entityId) {{
        ratesRequestCounter++;
        CURRENT_TOUR_RATES = [];
        if (badgeEl) badgeEl.textContent = '0';
        listEl.innerHTML = '<p style="color:var(--muted); font-size: 13px; margin: 8px 0; background:#f8fafc; padding:12px; border-radius:6px; border:1px dashed var(--border);">Guarda los datos del tour primero para asociar tarifas especiales.</p>';
        btnAdd.style.display = 'none';
        return;
      }}

      const reqId = ++ratesRequestCounter;

      btnAdd.style.display = 'inline-flex';
      listEl.innerHTML = '<p style="color:var(--muted); font-size: 13px; margin: 8px 0;">Cargando tarifas...</p>';
      try {{
        const r = await fetch('/api/catalog/tours/' + encodeURIComponent(entityId) + '/rates?all=1');
        if (!r.ok) throw new Error('Error al cargar tarifas');
        const data = await r.json();

        // Si llegó una petición posterior o el formulario ya no corresponde a este tour, ignorar
        const currentOpenId = (document.getElementById('formEntityId').value || '').trim();
        if (reqId !== ratesRequestCounter || (currentOpenId && currentOpenId !== entityId)) {{
          return;
        }}

        CURRENT_TOUR_RATES = Array.isArray(data) ? data : data.rates;
        if (!Array.isArray(CURRENT_TOUR_RATES)) throw new Error('Respuesta de tarifas inválida');
        if (badgeEl) badgeEl.textContent = String(CURRENT_TOUR_RATES.length);
        renderTourRates(CURRENT_TOUR_RATES);
      }} catch (err) {{
        const currentOpenId = (document.getElementById('formEntityId').value || '').trim();
        if (reqId === ratesRequestCounter && (!currentOpenId || currentOpenId === entityId)) {{
          listEl.innerHTML = '<p style="color:var(--danger); font-size: 13px; margin: 8px 0;">No se pudieron cargar las tarifas especiales.</p>';
        }}
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
        listEl.innerHTML = '<p style="color:var(--muted); font-size: 13px; margin: 8px 0;">No hay tarifas especiales registradas para este tour.</p>';
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
        const status = getRateStatusInfo(rate);

        const dateRange = (rate.valid_from || rate.valid_to)
          ? `<div style="font-size: 11px; color: var(--muted); margin-top: 3px;">📅 Vigencia: ${{escapeRateText(rate.valid_from || 'Sin inicio')}} al ${{escapeRateText(rate.valid_to || 'Sin vencimiento')}}</div>`
          : '<div style="font-size: 11px; color: var(--muted); margin-top: 3px;">📅 Vigencia: Permanente (sin límite de fecha)</div>';

        const condText = rate.conditions
          ? `<div style="font-size: 12px; color: #475569; margin-top: 3px;">ℹ️ ${{escapeRateText(rate.conditions)}}</div>`
          : '';

        item.innerHTML = `
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span class="rate-badge ${{b.cls}}">${{b.label}}</span>
              <strong style="font-size: 14px;">${{escapeRateText(rate.rate_name)}}</strong>
              <span class="price-tag">${{escapeRateText(rate.currency)}} ${{escapeRateText(rate.price)}}</span>
              <span class="rate-status ${{status.cls}}">${{status.label}}</span>
            </div>
            ${{condText}}
            ${{dateRange}}
          </div>
          <div class="rate-card-actions">
            <button type="button" class="btn btn-secondary btn-sm" onclick="editRateById(${{rate.id}})" aria-label="Editar tarifa ${{escapeRateText(rate.rate_name)}}" title="Editar tarifa">✏️ Editar</button>
            <button type="button" class="btn btn-danger btn-sm" onclick="deleteRateById(${{rate.id}})" aria-label="Eliminar tarifa ${{escapeRateText(rate.rate_name)}}" title="Eliminar tarifa">🗑️ Eliminar</button>
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
        showToast('Debe guardar los datos del tour primero', 'error');
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
        safeFocus(document.getElementById('rateName'));
        return;
      }}
      const price = Number(priceVal);
      if (!priceVal || !Number.isFinite(price) || price < 0) {{
        showToast('Ingrese un precio numérico válido y no negativo', 'error');
        safeFocus(document.getElementById('ratePrice'));
        return;
      }}
      if (valid_from && valid_to && valid_from > valid_to) {{
        showToast('La fecha de inicio de vigencia no puede ser posterior a la fecha final', 'error');
        safeFocus(document.getElementById('rateValidFrom'));
        return;
      }}

      const payload = {{
        rate_category: category, rate_name: name, price, currency, conditions,
        valid_from, valid_to, is_active
      }};
      if (rateIdVal) {{
        payload.id = parseInt(rateIdVal, 10);
      }}

      const rateSessionAtStart = currentEditorSessionId;
      const rateEditorTokenAtStart = currentRateEditorSessionId;
      const rateIdAtStart = String(rateIdVal ?? '').trim();
      const rateEntityId = entityId;
      const submittedRateSnap = getRateFormSnapshot();

      const btn = document.getElementById('btnSaveRate');
      btn.disabled = true;
      btn.textContent = 'Guardando tarifa…';

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

        // Si la sesión del modal del tour cambió, ignorar completamente
        if (rateSessionAtStart !== currentEditorSessionId) return;

        if (r.ok && res.ok) {{
          showToast('Tarifa guardada correctamente');
          const savedRateId = res.rate_id != null ? res.rate_id : (res.id != null ? res.id : (rateIdAtStart ? parseInt(rateIdAtStart, 10) : null));

          // Solo modificar el formulario si seguimos en el mismo editor de esta tarifa
          if (rateEditorTokenAtStart === currentRateEditorSessionId) {{
            if (getRateFormSnapshot() === submittedRateSnap) {{
              hideRateForm();
            }} else {{
              if (savedRateId != null && savedRateId !== '') {{
                document.getElementById('rateId').value = String(savedRateId);
                document.getElementById('rateFormTitle').textContent = 'Editar Tarifa Especial';
              }}
              const confirmedObj = JSON.parse(submittedRateSnap);
              if (savedRateId != null && savedRateId !== '') {{
                confirmedObj.id = String(savedRateId);
              }}
              initialRateSnapshot = JSON.stringify(confirmedObj);
            }}
          }}

          loadTourRates(rateEntityId);
        }} else {{
          if (rateSessionAtStart === currentEditorSessionId && rateEditorTokenAtStart === currentRateEditorSessionId) {{
            showToast(res.error || 'Error al guardar tarifa', 'error');
          }}
        }}
      }} catch (err) {{
        if (rateSessionAtStart === currentEditorSessionId && rateEditorTokenAtStart === currentRateEditorSessionId) {{
          showToast('Error de conexión al guardar tarifa', 'error');
        }}
      }} finally {{
        if (rateEditorTokenAtStart === currentRateEditorSessionId) {{
          btn.disabled = false;
          btn.textContent = 'Guardar esta tarifa';
        }}
      }}
    }}

    async function deleteRateById(rateId) {{
      const r = CURRENT_TOUR_RATES.find(x => x.id === rateId);
      const rateName = r ? r.rate_name : 'esta tarifa';
      if (!confirm('¿Eliminar la tarifa especial "' + rateName + '"?\\n\\nEsta acción no se puede deshacer.')) return;
      try {{
        const resHttp = await fetch('/api/catalog/rates/' + rateId, {{
          method: 'DELETE',
          headers: {{
            'X-Catalog-CSRF': CSRF_TOKEN
          }}
        }});
        const res = await resHttp.json();
        if (resHttp.ok && res.ok) {{
          showToast('Tarifa eliminada exitosamente');
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
      const isEdit = document.getElementById('formIsEdit').value === '1';
      const entity_id = document.getElementById('formEntityId').value.trim();
      const name = document.getElementById('formName').value.trim();
      const official_price = document.getElementById('formPrice').value.trim();
      const currency = document.getElementById('formCurrency').value;
      const schedule = document.getElementById('formSchedule').value.trim();
      const duration = document.getElementById('formDuration').value.trim();
      const aliases = document.getElementById('formAliases').value;
      const includes = document.getElementById('formIncludes').value.trim();
      const excludes = document.getElementById('formExcludes').value.trim();
      const is_active = document.getElementById('formIsActive').checked;

      if (!entity_id) {{
        showToast('El identificador del tour es obligatorio', 'error');
        const adv = document.getElementById('advancedTourOptions');
        if (adv) adv.open = true;
        safeFocus(document.getElementById('formEntityId'));
        return;
      }}
      if (!name) {{
        showToast('El nombre del tour es obligatorio', 'error');
        safeFocus(document.getElementById('formName'));
        return;
      }}

      const payload = {{
        entity_id, name, official_price, currency, schedule,
        duration, aliases, includes, excludes, is_active
      }};

      // Instantánea exacta de lo enviado al servidor
      const sentSnapshotObj = {{
        entity_id,
        name,
        price: official_price,
        currency,
        schedule,
        duration,
        aliases: (aliases || '').trim(),
        includes,
        excludes,
        is_active: !!is_active
      }};

      const sessionAtStart = currentEditorSessionId;
      const btn = document.getElementById('btnSaveTour');
      btn.disabled = true;
      btn.textContent = 'Guardando datos del tour…';

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

        if (sessionAtStart !== currentEditorSessionId) return;

        if (r.ok && res.ok) {{
          const savedId = res.entity_id || entity_id;
          sentSnapshotObj.entity_id = savedId;
          showToast(isEdit ? 'Datos del tour actualizados exitosamente' : 'Tour creado exitosamente. Ya puedes registrar sus tarifas especiales.');

          // Actualizar snapshot confirmado con lo efectivamente guardado en el servidor
          initialTourSnapshot = JSON.stringify(sentSnapshotObj);
          updateRatesTourBaseRef();

          // Si era creación, conservar la ventana abierta, fijar su identidad y habilitar tarifas
          if (!isEdit) {{
            document.getElementById('formIsEdit').value = '1';
            document.getElementById('formEntityId').value = savedId;
            document.getElementById('formEntityId').disabled = true;
            document.getElementById('modalTourTitle').textContent = 'Editar Tour: ' + (document.getElementById('formName').value.trim() || name);
            loadTourRates(savedId);
          }} else {{
            document.getElementById('modalTourTitle').textContent = 'Editar Tour: ' + (document.getElementById('formName').value.trim() || name);
          }}

          loadTours();
        }} else {{
          showToast(res.error || 'Error al guardar tour', 'error');
        }}
      }} catch (err) {{
        if (sessionAtStart === currentEditorSessionId) {{
          showToast('Error de conexión con el servidor', 'error');
        }}
      }} finally {{
        btn.disabled = false;
        btn.textContent = 'Guardar datos del tour';
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
        const r = await fetch(`/api/catalog/upload/${{encodeURIComponent(entityId)}}`, {{
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
</html>""", 'catalogo')

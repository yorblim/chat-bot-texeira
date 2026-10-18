"""login_ui.py — Interfaz visual moderna para el inicio de sesión de Texeira Travel.

Diseño premium con paleta curada, tipografía Google Fonts (Inter / Outfit),
efectos de micro-animación, toggle de contraseña y diseño 100% responsivo.
"""

def get_login_html(
    error: str = "",
    success_msg: str = "",
    next_url: str = "/catalogo",
    username_val: str = ""
) -> str:
    """Genera el HTML de la página de Login corporativa de Texeira Travel."""
    error_html = ""
    if error:
        error_html = f"""
        <div class="alert alert-error" role="alert">
          <span class="alert-icon">⚠️</span>
          <span>{error}</span>
        </div>
        """

    success_html = ""
    if success_msg:
        success_html = f"""
        <div class="alert alert-success" role="alert">
          <span class="alert-icon">✅</span>
          <span>{success_msg}</span>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Iniciar Sesión — Texeira Travel</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-dark: #070d19;
      --card-bg: rgba(17, 24, 39, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --primary: #0284c7;
      --primary-hover: #0369a1;
      --primary-glow: rgba(14, 165, 233, 0.35);
      --accent: #f59e0b;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --input-bg: rgba(15, 23, 42, 0.8);
      --input-border: rgba(148, 163, 184, 0.2);
      --input-focus: #38bdf8;
      --error-bg: rgba(239, 68, 68, 0.15);
      --error-border: rgba(239, 68, 68, 0.4);
      --error-text: #fca5a5;
      --success-bg: rgba(16, 185, 129, 0.15);
      --success-border: rgba(16, 185, 129, 0.4);
      --success-text: #6ee7b7;
      --font-heading: 'Outfit', sans-serif;
      --font-body: 'Plus Jakarta Sans', sans-serif;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: var(--font-body);
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(circle at 15% 20%, rgba(2, 132, 199, 0.2) 0%, transparent 40%),
        radial-gradient(circle at 85% 80%, rgba(245, 158, 11, 0.15) 0%, transparent 45%),
        linear-gradient(180deg, #070d19 0%, #0b1528 100%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      padding: 24px;
      overflow-x: hidden;
      position: relative;
    }}

    /* Fondo con sutil patrón de líneas de altitud / viajes */
    body::before {{
      content: "";
      position: absolute;
      inset: 0;
      background-image: radial-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px);
      background-size: 32px 32px;
      pointer-events: none;
    }}

    .login-container {{
      width: 100%;
      max-width: 440px;
      position: relative;
      z-index: 1;
    }}

    .brand-header {{
      text-align: center;
      margin-bottom: 28px;
    }}

    .brand-logo-badge {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      background: linear-gradient(135deg, rgba(2, 132, 199, 0.25) 0%, rgba(245, 158, 11, 0.2) 100%);
      border: 1px solid rgba(255, 255, 255, 0.15);
      padding: 8px 18px;
      border-radius: 9999px;
      margin-bottom: 16px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
      backdrop-filter: blur(8px);
    }}

    .brand-logo-icon {{
      font-size: 22px;
    }}

    .brand-logo-text {{
      font-family: var(--font-heading);
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      background: linear-gradient(90deg, #38bdf8, #fbbf24);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .brand-title {{
      font-family: var(--font-heading);
      font-size: 28px;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: -0.5px;
      margin-bottom: 6px;
    }}

    .brand-subtitle {{
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.5;
    }}

    .login-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 36px 32px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05);
      backdrop-filter: blur(16px);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}

    .alert {{
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.45;
      margin-bottom: 22px;
      animation: fadeIn 0.3s ease;
    }}

    .alert-error {{
      background: var(--error-bg);
      border: 1px solid var(--error-border);
      color: var(--error-text);
    }}

    .alert-success {{
      background: var(--success-bg);
      border: 1px solid var(--success-border);
      color: var(--success-text);
    }}

    .alert-icon {{
      font-size: 16px;
      flex-shrink: 0;
      margin-top: 1px;
    }}

    .form-group {{
      margin-bottom: 20px;
    }}

    .form-label {{
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 8px;
    }}

    .input-wrapper {{
      position: relative;
      display: flex;
      align-items: center;
    }}

    .input-icon {{
      position: absolute;
      left: 14px;
      color: var(--text-dim);
      font-size: 16px;
      pointer-events: none;
      transition: color 0.2s ease;
    }}

    .form-input {{
      width: 100%;
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      border-radius: 12px;
      padding: 13px 14px 13px 44px;
      font-size: 14px;
      font-family: inherit;
      color: #ffffff;
      outline: none;
      transition: all 0.2s ease;
    }}

    .form-input::placeholder {{
      color: #475569;
    }}

    .form-input:focus {{
      border-color: var(--input-focus);
      background: rgba(15, 23, 42, 0.95);
      box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
    }}

    .form-input:focus + .input-icon,
    .form-input:focus ~ .input-icon {{
      color: var(--input-focus);
    }}

    .toggle-pwd-btn {{
      position: absolute;
      right: 12px;
      background: none;
      border: none;
      color: var(--text-dim);
      font-size: 16px;
      cursor: pointer;
      padding: 4px;
      border-radius: 6px;
      transition: color 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .toggle-pwd-btn:hover {{
      color: #ffffff;
    }}

    .form-options {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      font-size: 13px;
    }}

    .checkbox-label {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--text-muted);
      cursor: pointer;
      user-select: none;
    }}

    .checkbox-label input[type="checkbox"] {{
      accent-color: var(--primary);
      width: 16px;
      height: 16px;
      cursor: pointer;
    }}

    .btn-submit {{
      width: 100%;
      background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
      color: #ffffff;
      border: none;
      border-radius: 12px;
      padding: 14px 20px;
      font-size: 15px;
      font-weight: 600;
      font-family: var(--font-heading);
      letter-spacing: 0.3px;
      cursor: pointer;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 4px 14px var(--primary-glow);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}

    .btn-submit:hover {{
      background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(14, 165, 233, 0.5);
    }}

    .btn-submit:active {{
      transform: translateY(0);
      box-shadow: 0 2px 8px var(--primary-glow);
    }}

    .btn-submit:disabled {{
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }}

    .footer-note {{
      text-align: center;
      margin-top: 28px;
      font-size: 12px;
      color: var(--text-dim);
      line-height: 1.6;
    }}

    .footer-security {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--text-dim);
    }}

    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(-4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    @media (max-width: 480px) {{
      .login-card {{
        padding: 28px 20px;
        border-radius: 16px;
      }}
      .brand-title {{
        font-size: 24px;
      }}
    }}
  </style>
</head>
<body>

  <div class="login-container">
    <div class="brand-header">
      <div class="brand-logo-badge">
        <span class="brand-logo-icon">🏔️</span>
        <span class="brand-logo-text">Texeira Travel</span>
      </div>
      <h1 class="brand-title">Panel Administrativo</h1>
      <p class="brand-subtitle">Gestión de Catálogo, Reservas y Métricas de Chatbot</p>
    </div>

    <div class="login-card">
      {error_html}
      {success_html}

      <form id="loginForm" method="POST" action="/login" onsubmit="handleSubmit(event)">
        <input type="hidden" name="next" value="{next_url}">

        <div class="form-group">
          <label for="username" class="form-label">Usuario administrativo</label>
          <div class="input-wrapper">
            <span class="input-icon">👤</span>
            <input 
              type="text" 
              id="username" 
              name="username" 
              class="form-input" 
              placeholder="Ingresa tu usuario" 
              value="{username_val}"
              required 
              autocomplete="username"
              autofocus
            >
          </div>
        </div>

        <div class="form-group">
          <label for="password" class="form-label">Contraseña</label>
          <div class="input-wrapper">
            <span class="input-icon">🔒</span>
            <input 
              type="password" 
              id="password" 
              name="password" 
              class="form-input" 
              placeholder="••••••••••••" 
              required 
              autocomplete="current-password"
            >
            <button 
              type="button" 
              class="toggle-pwd-btn" 
              onclick="togglePasswordVisibility()" 
              id="togglePwdBtn"
              title="Mostrar / ocultar contraseña"
              aria-label="Mostrar u ocultar contraseña"
            >
              👁️
            </button>
          </div>
        </div>

        <div class="form-options">
          <label class="checkbox-label">
            <input type="checkbox" name="remember_me" value="1" checked>
            <span>Mantener sesión iniciada (7 días)</span>
          </label>
        </div>

        <button type="submit" id="btnSubmit" class="btn-submit">
          <span>Ingresar al Sistema</span>
          <span style="font-size: 16px;">➔</span>
        </button>
      </form>
    </div>

    <div class="footer-note">
      <div class="footer-security">
        <span>🛡️</span>
        <span>Acceso seguro protegido con tokens criptográficos</span>
      </div>
      <div>Texeira Travel Cusco © 2026. Todos los derechos reservados.</div>
    </div>
  </div>

  <script>
    function togglePasswordVisibility() {{
      const pwdInput = document.getElementById('password');
      const toggleBtn = document.getElementById('togglePwdBtn');
      if (pwdInput.type === 'password') {{
        pwdInput.type = 'text';
        toggleBtn.textContent = '🙈';
      }} else {{
        pwdInput.type = 'password';
        toggleBtn.textContent = '👁️';
      }}
    }}

    function handleSubmit(e) {{
      const btn = document.getElementById('btnSubmit');
      btn.disabled = true;
      btn.innerHTML = '<span>Verificando credenciales...</span> <span style="animation: spin 1s linear infinite;">⏳</span>';
    }}
  </script>
</body>
</html>
"""

"""
chat_ui.py — Interfaz de chat moderna para Texeira Travel Tour.

CAPA DE PRESENTACIÓN ÚNICAMENTE:
- Consume el endpoint /test-chat existente (no agrega lógica de backend).
- Todo el registro de interacciones y métricas sigue igual.
- HTML/CSS/JS vanilla, sin CDNs ni librerías externas.

Características del frontend:
  1. Renderizado markdown simple (**negritas**, viñetas - y *)
  2. Botones de seguimiento contextuales según la respuesta del bot
  3. Indicador "escribiendo" con 3 puntos animados (CSS puro)
  4. Avatar de marca (TT) y estado "En línea" con pulso verde
  5. Timestamps sutiles HH:MM por mensaje
  6. Animaciones de entrada fade-in + slide-up
  7. Diseño responsive (botones con scroll horizontal, viewport 375px)
   8. Estado vacío inicial con mensaje de bienvenida y 4 botones
   9. Manejo de errores con timeout 45s (AbortController) y botón Reintentar
   10. Botones contextuales multilingües (es/en/pt) según detected_language
   11. Acción "Ver más opciones" como flag de navegación UI (sin pasar por RAG)
   12. client_message_id único por mensaje (idempotencia de reintentos)
"""


def get_chat_html() -> str:
    """Genera el HTML completo de la interfaz de chat moderna."""
    return '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Texeira Travel Tour — Chat</title>
    <style>
        :root {
            --bg: #0b141a;
            --bg-panel: #111b21;
            --bg-input: #2a3942;
            --bubble-bot: #202c33;
            --bubble-user: #005c4b;
            --text: #e9edef;
            --text-muted: #8696a0;
            --accent: #00a884;
            --accent-dark: #008069;
            --danger: #e63946;
            --border: #222d34;
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { height: 100%; }
        body {
            font-family: var(--font);
            background: var(--bg);
            color: var(--text);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .app {
            display: flex;
            flex-direction: column;
            height: 100%;
            max-width: 860px;
            margin: 0 auto;
            width: 100%;
            background: var(--bg-panel);
            box-shadow: 0 0 40px rgba(0,0,0,.45);
        }

        /* ---------- Header ---------- */
        .chat-header {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: var(--bg-panel);
            border-bottom: 1px solid var(--border);
        }
        .header-avatar {
            width: 42px; height: 42px; flex-shrink: 0;
            border-radius: 50%;
            background: linear-gradient(135deg, #00a884, #00d4aa);
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 16px; color: #04362c;
            letter-spacing: .5px;
        }
        .header-info { flex: 1; min-width: 0; }
        .header-name { font-weight: 600; font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .header-status {
            display: flex; align-items: center; gap: 6px;
            font-size: 12px; color: var(--text-muted); margin-top: 1px;
        }
        .status-dot {
            width: 9px; height: 9px; border-radius: 50%;
            background: #25d366;
            animation: pulse 2s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(37,211,102,.55); }
            50% { box-shadow: 0 0 0 6px rgba(37,211,102,0); }
        }

        /* ---------- Chat area ---------- */
        .chat-scroll {
            flex: 1;
            overflow-y: auto;
            padding: 16px 14px 8px;
            scroll-behavior: smooth;
        }
        .chat-scroll::-webkit-scrollbar { width: 6px; }
        .chat-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

        /* ---------- Messages ---------- */
        .msg-row {
            display: flex;
            margin-bottom: 10px;
            animation: fadeUp .25s ease both;
        }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(10px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .msg-row.user { justify-content: flex-end; }
        .msg-row.bot { justify-content: flex-start; }
        .msg-row.error { justify-content: center; }
        .msg-avatar {
            width: 30px; height: 30px; flex-shrink: 0;
            border-radius: 50%;
            background: linear-gradient(135deg, #00a884, #00d4aa);
            display: flex; align-items: center; justify-content: center;
            font-size: 14px; color: #04362c;
            margin-right: 8px; align-self: flex-end;
        }
        .msg-body { max-width: 78%; min-width: 0; }
        .bubble {
            padding: 8px 12px;
            border-radius: 12px;
            font-size: 14.5px;
            line-height: 1.45;
            word-wrap: break-word;
        }
        .bot-bubble { background: var(--bubble-bot); border-bottom-left-radius: 4px; }
        .user-bubble { background: var(--bubble-user); border-bottom-right-radius: 4px; }
        .bubble p { margin: 0 0 4px; }
        .bubble p:last-child { margin-bottom: 0; }
        .bubble ul { margin: 4px 0; padding-left: 18px; }
        .bubble li { margin-bottom: 2px; }
        .bubble strong { font-weight: 600; }
        .msg-time {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 3px;
            padding: 0 4px;
        }
        .msg-row.user .msg-time { text-align: right; }

        /* Tour images in bot messages */
        .msg-image-container {
            margin: 8px 0;
            border-radius: 12px;
            overflow: hidden;
            max-width: 320px;
        }
        .msg-image {
            width: 100%;
            height: auto;
            display: block;
            border-radius: 12px;
            object-fit: cover;
            max-height: 200px;
            transition: opacity 0.3s;
        }
        .msg-image:hover {
            opacity: 0.9;
            cursor: pointer;
        }

        /* Error bubble */
        .error-bubble {
            background: rgba(230,57,70,.15);
            border: 1px solid rgba(230,57,70,.45);
            color: #ffb3b8;
            border-radius: 12px;
            padding: 10px 14px;
            font-size: 13.5px;
            max-width: 90%;
            text-align: center;
        }
        .error-bubble .retry-btn {
            display: inline-block;
            margin-top: 8px;
            background: var(--danger);
            color: #fff;
            border: none;
            border-radius: 16px;
            padding: 6px 16px;
            font-size: 12.5px;
            font-weight: 600;
            cursor: pointer;
            font-family: var(--font);
        }
        .error-bubble .retry-btn:hover { background: #c02430; }

        /* ---------- Botones extraídos de listas (pegados al mensaje) ---------- */
        .msg-options {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
        }
        .msg-option-btn {
            background: var(--bg-input);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 6px 12px;
            font-size: 12.5px;
            font-family: var(--font);
            cursor: pointer;
            white-space: nowrap;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            transition: background .15s, transform .15s, border-color .15s;
        }
        .msg-option-btn:hover {
            background: var(--accent);
            border-color: var(--accent);
            transform: translateY(-1px);
        }

        /* ---------- Typing indicator ---------- */
        .typing-bubble {
            display: inline-flex;
            gap: 5px;
            background: var(--bubble-bot);
            border-radius: 12px;
            border-bottom-left-radius: 4px;
            padding: 12px 14px;
        }
        .typing-bubble span {
            width: 7px; height: 7px;
            border-radius: 50%;
            background: var(--text-muted);
            animation: bounce 1.3s ease-in-out infinite;
        }
        .typing-bubble span:nth-child(2) { animation-delay: .18s; }
        .typing-bubble span:nth-child(3) { animation-delay: .36s; }
        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); opacity: .45; }
            30% { transform: translateY(-7px); opacity: 1; }
        }

        /* ---------- Suggestions (scroll horizontal) ---------- */
        .suggestions-wrap {
            position: relative;
            border-top: 1px solid var(--border);
            background: var(--bg-panel);
        }
        .suggestions-wrap::before, .suggestions-wrap::after {
            content: '';
            position: absolute;
            top: 0; bottom: 0;
            width: 26px;
            pointer-events: none;
            z-index: 1;
        }
        .suggestions-wrap::before { left: 0; background: linear-gradient(to right, var(--bg-panel), transparent); }
        .suggestions-wrap::after { right: 0; background: linear-gradient(to left, var(--bg-panel), transparent); }
        .suggestions-row {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            scroll-behavior: smooth;
            padding: 10px 26px;
            -webkit-overflow-scrolling: touch;
        }
        .suggestions-row::-webkit-scrollbar { display: none; }
        .suggestion-btn {
            flex-shrink: 0;
            background: var(--bubble-bot);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 8px 14px;
            font-size: 13px;
            font-family: var(--font);
            cursor: pointer;
            transition: background .15s, transform .15s, border-color .15s;
            white-space: nowrap;
        }
        .suggestion-btn:hover {
            background: var(--accent);
            border-color: var(--accent);
            transform: translateY(-1px);
        }

        /* ---------- Input area ---------- */
        .input-area {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px 14px;
            background: var(--bg-panel);
            border-top: 1px solid var(--border);
        }
        .input-wrapper {
            flex: 1;
            display: flex;
            align-items: center;
            background: var(--bg-input);
            border-radius: 24px;
            padding: 2px 6px 2px 16px;
            min-width: 0;
        }
        #messageInput {
            flex: 1;
            min-width: 0;
            background: transparent;
            border: none;
            outline: none;
            color: var(--text);
            font-size: 14.5px;
            padding: 10px 0;
            font-family: var(--font);
        }
        #messageInput::placeholder { color: var(--text-muted); }
        .send-btn {
            width: 46px; height: 46px; flex-shrink: 0;
            border: none;
            border-radius: 50%;
            background: var(--accent);
            color: #04362c;
            font-size: 20px;
            cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            transition: background .15s, transform .15s;
        }
        .send-btn:hover { background: #00c9a7; transform: scale(1.05); }
        .send-btn:disabled { background: var(--bg-input); color: var(--text-muted); cursor: not-allowed; transform: none; }

        .consent-disclaimer {
            font-size: 11px;
            color: var(--text-muted);
            text-align: center;
            padding: 6px 16px 8px;
            background: var(--bg-panel);
            line-height: 1.3;
            border-top: 1px solid var(--border);
            opacity: 0.85;
        }

        /* ---------- Responsive (mobile 375px) ---------- */
        @media (max-width: 480px) {
            .msg-body { max-width: 85%; }
            .chat-scroll { padding: 12px 10px 6px; }
            .suggestion-btn { padding: 7px 12px; font-size: 12.5px; }
            .header-name { font-size: 15px; }
            .send-btn { width: 42px; height: 42px; }
        }
    </style>
</head>
<body>
    <div class="app">
        <!-- Header con identidad de marca -->
        <div class="chat-header">
            <div class="header-avatar">TT</div>
            <div class="header-info">
                <div class="header-name">Texeira Travel Tour</div>
                <div class="header-status"><span class="status-dot"></span> En línea</div>
            </div>
        </div>

        <!-- Área de mensajes -->
        <div class="chat-scroll" id="chatScroll">
            <div id="chatContainer"></div>
        </div>

        <!-- Botones de seguimiento contextuales -->
        <div class="suggestions-wrap">
            <div class="suggestions-row" id="suggestionsRow"></div>
        </div>

        <!-- Input de mensaje -->
        <div class="input-area">
            <div class="input-wrapper">
                <input type="text" id="messageInput" placeholder="Escribe un mensaje..." autocomplete="off">
            </div>
            <button class="send-btn" id="sendBtn" title="Enviar">➤</button>
        </div>

        <!-- Consentimiento informado Ley N° 29733 (LPDP) -->
        <div class="consent-disclaimer">
            🔒 Al interactuar aceptas el tratamiento de datos para fines informativos conforme a la Ley N° 29733 (LPDP).
        </div>
    </div>

    <script>
        // ---------- Elementos ----------
        var chatContainer = document.getElementById('chatContainer');
        var chatScroll = document.getElementById('chatScroll');
        var suggestionsRow = document.getElementById('suggestionsRow');
        var messageInput = document.getElementById('messageInput');
        var sendBtn = document.getElementById('sendBtn');
        var typingEl = null;
        var lastUserMessage = null;
        var pending = false;

        // Idioma detectado en la última respuesta del bot (viene de /test-chat).
        // Se usa para elegir el set de labels de botones correcto y así no
        // sesgar las métricas de idioma de la investigación.
        var lastDetectedLang = 'es';

        // UUID por mensaje lógico (idempotencia de reintentos en el backend)
        var lastMessageId = null;

        // Contexto de la última acción "Ver más opciones" (para reintentos)
        var lastShowMoreContext = null;

        // user_id único por sesión de navegador (no se usa localStorage a propósito)
        var sessionUserId = (typeof crypto !== 'undefined' && crypto.randomUUID)
            ? crypto.randomUUID()
            : 'web-' + Math.random().toString(36).substr(2, 9);

        // ---------- Labels de botones por idioma ----------
        // Los botones contextuales y genéricos se muestran en el idioma de la
        // conversación. Los botones extraídos de listas del bot NO usan esto:
        // ya heredan el idioma de la respuesta del LLM.
        var BUTTON_LABELS = {
            es: {
                tours: '🏔️ Ver tours',
                precio: '💰 Precios y disponibilidad',
                contacto: '📞 Contacto',
                ayuda: '❓ Ayuda',
                asesor: 'Hablar con un asesor humano',
                formasPago: 'Formas de pago',
                descuentos: '¿Hay descuentos?',
                verPrecio: 'Ver precio',
                queIncluye: '¿Qué incluye?',
                horarios: 'Horarios disponibles'
            },
            en: {
                tours: '🏔️ View tours',
                precio: '💰 Prices and availability',
                contacto: '📞 Contact',
                ayuda: '❓ Help',
                asesor: 'Talk to a human advisor',
                formasPago: 'Payment methods',
                descuentos: 'Any discounts?',
                verPrecio: 'See price',
                queIncluye: 'What\u2019s included?',
                horarios: 'Available schedules'
            },
            pt: {
                tours: '🏔️ Ver passeios',
                precio: '💰 Pre\u00e7os e disponibilidade',
                contacto: '📞 Contato',
                ayuda: '❓ Ajuda',
                asesor: 'Falar com um atendente',
                formasPago: 'Formas de pagamento',
                descuentos: 'Tem descontos?',
                verPrecio: 'Ver pre\u00e7o',
                queIncluye: 'O que est\u00e1 inclu\u00eddo?',
                horarios: 'Hor\u00e1rios dispon\u00edveis'
            }
        };

        // ---------- Utilidades ----------
        function getTime() {
            var d = new Date();
            var h = String(d.getHours()).padStart(2, '0');
            var m = String(d.getMinutes()).padStart(2, '0');
            return h + ':' + m;
        }

        function escapeHtml(text) {
            var div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // ---------- Extracción de listas de opciones (botones por ítem) ----------
        // Regex de emojis: \p{Extended_Pictographic} (soporte moderno).
        // Se construye con el constructor RegExp en try/catch para que navegadores
        // antiguos no rompan todo el script si no soportan property escapes.
        var EMOJI_RE = null;
        try { EMOJI_RE = new RegExp('\\\\p{Extended_Pictographic}', 'gu'); } catch (e) { EMOJI_RE = null; }

        function stripEmoji(text) {
            if (!EMOJI_RE) { return text; }
            return text
                .replace(EMOJI_RE, '')
                .replace(/\uFE0F/g, '')
                .replace(/\d\u20E3/g, '');
        }

        function cleanOptionLabel(raw) {
            var s = String(raw || '').trim();
            s = stripEmoji(s);
            s = s.replace(/^[\s:;,.\u2022-]+/, '').replace(/[\s:;,.-]+$/, '');
            return s.trim();
        }

        function extractOptions(text) {
            var lines = String(text).replace(/\\r\\n/g, '\\n').split('\\n');
            var options = [];
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                var content = null;
                // Líneas que empiezan con -, * o viñeta
                var bulletMatch = line.match(/^\\s*[-*\u2022]\\s*(.+)$/);
                if (bulletMatch) {
                    content = bulletMatch[1];
                } else if (EMOJI_RE) {
                    // Líneas que empiezan con un emoji seguido de texto
                    var trimmed = line.trim();
                    EMOJI_RE.lastIndex = 0;
                    var em = EMOJI_RE.exec(trimmed);
                    if (em && em.index === 0) {
                        content = trimmed.slice(em[0].length);
                    }
                }
                if (content !== null) {
                    var cleaned = cleanOptionLabel(content);
                    if (cleaned.length >= 2) { options.push(cleaned); }
                }
            }
            return options;
        }

        function truncateLabel(label) {
            return label.length > 40 ? label.slice(0, 40).trimEnd() + '\u2026' : label;
        }

        function buildOptionPayload(fullText) {
            var t = String(fullText || '').trim();
            var lower = t.toLowerCase();
            // Si el texto del ítem ya empieza con "información" (ej.
            // "Información sobre tours a Machu Picchu" o "Información de la
            // agencia"), solo se antepone "Quiero" para evitar duplicar la frase.
            if (lower.indexOf('informaci\u00f3n') === 0 || lower.indexOf('informacion') === 0) {
                return 'Quiero ' + t.charAt(0).toLowerCase() + t.slice(1);
            }
            return 'Quiero informaci\u00f3n sobre ' + t.charAt(0).toLowerCase() + t.slice(1);
        }

        function shortenOptionLabel(text) {
            // Quita prefijos de relleno del texto de la opción para que el
            // botón muestre solo lo representativo.
            // Ej: "Información sobre tours a Machu Picchu" → "Tours a Machu Picchu"
            var t = String(text || '').trim();
            var lower = t.toLowerCase();
            var prefixes = [
                'informaci\u00f3n sobre ', 'informacion sobre ',
                'informaci\u00f3n de ', 'informacion de ',
                'informaci\u00f3n ', 'informacion '
            ];
            for (var i = 0; i < prefixes.length; i++) {
                if (lower.indexOf(prefixes[i]) === 0) {
                    var rest = t.slice(prefixes[i].length).trim();
                    // Capitaliza la primera letra: "tours a..." → "Tours a..."
                    return rest.charAt(0).toUpperCase() + rest.slice(1);
                }
            }
            return t;
        }

        function buildOptionButtons(options) {
            var btns = [];
            // Si hay más de 6 ítems, se muestran los primeros 5 + "Ver más opciones"
            var maxItems = options.length > 6 ? 5 : options.length;
            for (var i = 0; i < maxItems; i++) {
                btns.push({
                    // El botón muestra el texto corto y representativo;
                    // el payload conserva el texto completo del ítem.
                    label: truncateLabel(shortenOptionLabel(options[i])),
                    payload: buildOptionPayload(options[i])
                });
            }
            if (options.length > 6) {
                // Acción de navegación UI: NO envía texto libre al backend.
                // El backend responde las opciones restantes sin pasar por RAG
                // y la registra como interaction_type="ui_navigation".
                btns.push({
                    label: 'Ver m\u00e1s opciones',
                    action: 'show_more_options',
                    context: options.slice(5)
                });
            }
            return btns;
        }

        // ---------- Parser markdown simple (negritas **, viñetas - y *) ----------
        function inlineFormat(text) {
            var out = escapeHtml(text);
            out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:var(--accent); font-weight:600; text-decoration:underline;">$1</a>');
            return out;
        }

        function parseMarkdown(text) {
            var lines = text.replace(/\\r\\n/g, '\\n').split('\\n');
            var html = '';
            var inList = false;
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                // Imágenes markdown: ![alt](url)
                var imgMatch = line.match(/^\\s*!\\[([^\\]]*)\\]\\(([^)]+)\\)\\s*$/);
                if (imgMatch) {
                    if (inList) { html += '</ul>'; inList = false; }
                    var alt = escapeHtml(imgMatch[1] || 'Tour image');
                    var src = imgMatch[2];
                    html += '<div class="msg-image-container"><img src="' + src + '" alt="' + alt + '" class="msg-image" loading="lazy" onerror="this.style.display=\\'none\\'"></div>';
                    continue;
                }
                var bulletMatch = line.match(/^\\s*[-*]\\s+(.+)$/);
                if (bulletMatch) {
                    if (!inList) { html += '<ul>'; inList = true; }
                    html += '<li>' + inlineFormat(bulletMatch[1]) + '</li>';
                } else {
                    if (inList) { html += '</ul>'; inList = false; }
                    if (line.trim() === '') { html += '<br>'; }
                    else { html += '<p>' + inlineFormat(line) + '</p>'; }
                }
            }
            if (inList) { html += '</ul>'; }
            return html;
        }

        // ---------- Mensajes ----------
        function addMessage(text, sender, options) {
            var row = document.createElement('div');
            row.className = 'msg-row ' + sender;

            if (sender === 'bot') {
                var avatar = document.createElement('div');
                avatar.className = 'msg-avatar';
                avatar.textContent = 'TT';
                row.appendChild(avatar);
            }

            var body = document.createElement('div');
            body.className = 'msg-body';

            var bubble = document.createElement('div');
            bubble.className = 'bubble ' + (sender === 'user' ? 'user-bubble' : 'bot-bubble');
            if (sender === 'bot') {
                bubble.innerHTML = parseMarkdown(text);
            } else {
                bubble.innerHTML = escapeHtml(text).replace(/\\n/g, '<br>');
            }

            var time = document.createElement('div');
            time.className = 'msg-time';
            time.textContent = getTime() + (sender === 'user' ? '  ✓✓' : '');

            body.appendChild(bubble);
            body.appendChild(time);

            // Botones extraídos de la lista de opciones, pegados a este mensaje
            if (sender === 'bot' && options && options.length) {
                var optRow = document.createElement('div');
                optRow.className = 'msg-options';
                options.forEach(function (opt) {
                    var b = document.createElement('button');
                    b.className = 'msg-option-btn';
                    b.textContent = opt.label;
                    b.addEventListener('click', function () {
                        if (opt.action) {
                            sendShowMore(opt.context || []);
                        } else {
                            sendMessage(opt.payload);
                        }
                    });
                    optRow.appendChild(b);
                });
                body.appendChild(optRow);
            }

            row.appendChild(body);
            chatContainer.appendChild(row);
            scrollBottom();
        }

        function addErrorBubble() {
            // Reemplaza burbujas de error anteriores: no se apilan,
            // siempre queda una sola burbuja de error con su Reintentar.
            var prevErrors = chatContainer.querySelectorAll('.msg-row.error');
            prevErrors.forEach(function (el) { el.remove(); });

            var row = document.createElement('div');
            row.className = 'msg-row error';
            var bubble = document.createElement('div');
            bubble.className = 'error-bubble';
            bubble.innerHTML = '⚠️ No se pudo obtener una respuesta del servidor.';
            var retry = document.createElement('button');
            retry.className = 'retry-btn';
            retry.textContent = 'Reintentar';
            retry.addEventListener('click', function () { retryLast(); });
            bubble.appendChild(retry);
            row.appendChild(bubble);
            chatContainer.appendChild(row);
            scrollBottom();
        }

        function scrollBottom() {
            chatScroll.scrollTop = chatScroll.scrollHeight;
        }

        // ---------- Indicador "escribiendo" (3 puntos animados) ----------
        function showTyping() {
            if (typingEl) { return; }
            typingEl = document.createElement('div');
            typingEl.className = 'msg-row bot';
            typingEl.innerHTML = '<div class="msg-avatar">TT</div>' +
                '<div class="msg-body"><div class="typing-bubble">' +
                '<span></span><span></span><span></span></div></div>';
            chatContainer.appendChild(typingEl);
            scrollBottom();
        }

        function hideTyping() {
            if (typingEl) {
                typingEl.remove();
                typingEl = null;
            }
        }

        // ---------- Botones de seguimiento contextuales ----------
        // Los labels se seleccionan según el idioma de la conversación
        // (lastDetectedLang). Si el idioma no está en el diccionario,
        // se usa español como default (auditoría #1: sin sesgo idiomático).
        function buildSuggestions(botText) {
            var lang = BUTTON_LABELS[lastDetectedLang] ? lastDetectedLang : 'es';
            var L = BUTTON_LABELS[lang];
            var t = botText.toLowerCase();
            var labels;
            if (t.indexOf('no dispongo de esa informaci\u00f3n') !== -1 ||
                t.indexOf('asesor humano') !== -1 ||
                t.indexOf('human advisor') !== -1 ||
                t.indexOf('atendente') !== -1) {
                labels = [L.asesor];
            } else if (t.indexOf('precio') !== -1 || t.indexOf('costo') !== -1 ||
                       t.indexOf('cu\u00e1nto') !== -1 || t.indexOf('price') !== -1 ||
                       t.indexOf('cost') !== -1 || t.indexOf('pre\u00e7o') !== -1) {
                labels = [L.formasPago, L.descuentos];
            } else if (t.indexOf('tour') !== -1 || t.indexOf('paquete') !== -1 ||
                       t.indexOf('package') !== -1 || t.indexOf('passeio') !== -1) {
                labels = [L.verPrecio, L.queIncluye, L.horarios];
            } else {
                labels = [L.tours, L.precio, L.contacto, L.ayuda];
            }
            renderButtons(labels);
        }

        function renderButtons(labels) {
            suggestionsRow.innerHTML = '';
            labels.forEach(function (label) {
                var btn = document.createElement('button');
                btn.className = 'suggestion-btn';
                btn.textContent = label;
                btn.addEventListener('click', function () { sendMessage(label); });
                suggestionsRow.appendChild(btn);
            });
        }

        // ---------- Llamada al backend con timeout de 45s ----------
        function fetchBotReply(message, extra, clientMessageId) {
            var controller = new AbortController();
            var timer = setTimeout(function () { controller.abort(); }, 45000);
            var body = { user_id: sessionUserId, message: message };
            if (extra) {
                if (extra.action) { body.action = extra.action; }
                if (extra.context) { body.context = extra.context; }
            }
            if (clientMessageId) { body.client_message_id = clientMessageId; }
            return fetch('/test-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: controller.signal
            })
            .then(function (resp) {
                clearTimeout(timer);
                if (!resp.ok) { throw new Error('HTTP ' + resp.status); }
                return resp.json();
            })
            .catch(function (err) {
                clearTimeout(timer);
                throw err;
            });
        }

        function handleBotReply(data) {
            hideTyping();
            lastShowMoreContext = null;
            if (data && data.detected_language) {
                lastDetectedLang = data.detected_language;
            }
            if (data && data.response) {
                // PRIORIDAD 1: si la respuesta contiene una lista de opciones
                // (2+ líneas con viñeta o emoji), se generan botones por ítem
                // pegados al mensaje, en lugar de los botones genéricos.
                var options = extractOptions(data.response);
                if (options.length >= 2) {
                    addMessage(data.response, 'bot', buildOptionButtons(options));
                    suggestionsRow.innerHTML = '';
                } else {
                    // FALLBACK: respuesta conversacional sin lista
                    // → se mantiene la lógica anterior (contextuales o genéricos)
                    addMessage(data.response, 'bot', null);
                    buildSuggestions(data.response);
                }
            } else {
                addErrorBubble();
            }
            pending = false;
            sendBtn.disabled = false;
            messageInput.focus();
        }

        function handleBotError() {
            hideTyping();
            addErrorBubble();
            pending = false;
            sendBtn.disabled = false;
            messageInput.focus();
        }

        function sendMessage(text) {
            text = String(text || '').trim();
            if (!text || pending) { return; }

            lastUserMessage = text;
            lastShowMoreContext = null;
            // UUID único por mensaje lógico: se genera UNA vez al enviar y
            // se reutiliza en reintentos (idempotencia en la base de datos).
            lastMessageId = (typeof crypto !== 'undefined' && crypto.randomUUID)
                ? crypto.randomUUID()
                : 'msg-' + Math.random().toString(36).substr(2, 9);
            pending = true;
            sendBtn.disabled = true;

            addMessage(text, 'user');
            messageInput.value = '';
            showTyping();

            fetchBotReply(text, null, lastMessageId).then(handleBotReply).catch(handleBotError);
        }

        // Acción "Ver más opciones": envía un flag de navegación UI al backend
        // en vez de un texto libre. El backend responde las opciones restantes
        // sin pasar por el RAG y la interacción no contamina las métricas.
        function sendShowMore(contextList) {
            if (pending) { return; }
            lastShowMoreContext = contextList || [];
            pending = true;
            sendBtn.disabled = true;
            showTyping();
            fetchBotReply(
                'show_more_options',
                { action: 'show_more_options', context: lastShowMoreContext },
                null
            ).then(handleBotReply).catch(handleBotError);
        }

        function retryLast() {
            if (pending) { return; }
            if (lastShowMoreContext) {
                // Reintento de la acción "Ver más opciones"
                sendShowMore(lastShowMoreContext);
                return;
            }
            if (!lastUserMessage) { return; }
            pending = true;
            sendBtn.disabled = true;
            showTyping();
            // Se reutiliza el MISMO client_message_id: si el backend ya había
            // registrado la interacción, no se crea una fila duplicada.
            fetchBotReply(lastUserMessage, null, lastMessageId).then(handleBotReply).catch(handleBotError);
        }

        // ---------- Eventos ----------
        sendBtn.addEventListener('click', function () { sendMessage(messageInput.value); });
        messageInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { sendMessage(messageInput.value); }
        });

        // ---------- Estado inicial: bienvenida + 4 botones genéricos ----------
        addMessage('¡Hola! 👋 Soy el asistente virtual de Texeira Travel Tour. ¿En qué puedo ayudarte hoy?', 'bot');
        buildSuggestions('');
        messageInput.focus();
    </script>
</body>
</html>'''

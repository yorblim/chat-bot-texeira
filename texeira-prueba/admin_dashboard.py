"""
admin_dashboard.py — Panel de administración HTML para el staff de Texeira Travel Tour.

Genera el HTML del dashboard que se sirve en GET /dashboard.
UI Moderna con diseño limpio, auto-refresh y indicadores visuales.
"""

import json
from pathlib import Path


def _load_evaluation_results() -> dict | None:
    """Carga los resultados de evaluación RAGAS si existen."""
    path = Path(__file__).resolve().parent / "evaluation" / "evaluation_results.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_dashboard_html(metrics: dict, interactions: list[dict]) -> str:
    """
    Genera el HTML completo del dashboard de administración con UI moderna.
    """
    # Calcular tendencia de resolución
    resolution_color = "#10b981" if metrics['resolution_rate_pct'] >= 50 else "#f59e0b"
    escalation_color = "#ef4444" if metrics['escalation_rate_pct'] > 30 else "#10b981"

    # Cargar resultados de evaluación RAGAS
    eval_results = _load_evaluation_results()
    eval_html = ""
    if eval_results and "avg_metrics" in eval_results:
        em = eval_results["avg_metrics"]
        eq = eval_results.get("questions_with_llm_response", 0)
        et = eval_results.get("total_questions", 0)
        elat = eval_results.get("avg_latency_s", 0)

        def _score_color(score):
            if score >= 0.8: return "#10b981"
            if score >= 0.6: return "#f59e0b"
            return "#ef4444"

        def _score_label(score):
            if score >= 0.8: return "EXCELENTE"
            if score >= 0.6: return "BUENO"
            if score >= 0.4: return "MODERADO"
            return "BAJO"

        eval_html = f"""
            <div class="section-header" style="margin-top:32px">
                <div class="section-title">🔬 Evaluación de Calidad RAG (LLM-as-Judge)</div>
                <div style="color:var(--text-secondary);font-size:12px">
                    {eval_results.get("timestamp","")} | {eq}/{et} preguntas evaluadas
                </div>
            </div>
            <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:16px">
                <div class="kpi-card">
                    <div class="kpi-icon" style="background:rgba(16,185,129,0.2)">🛡️</div>
                    <div class="kpi-value" style="color:{_score_color(em.get('faithfulness',0))}">{em.get('faithfulness',0):.2f}</div>
                    <div class="kpi-label">Faithfulness (Anti-alucinación)</div>
                    <div class="kpi-change positive" style="background:rgba({_score_color(em.get('faithfulness',0)).strip('#')[0:2]},100,50,0.2)">{_score_label(em.get('faithfulness',0))}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon" style="background:rgba(59,130,246,0.2)">🎯</div>
                    <div class="kpi-value" style="color:{_score_color(em.get('answer_relevancy',0))}">{em.get('answer_relevancy',0):.2f}</div>
                    <div class="kpi-label">Relevancy (¿Responde lo que preguntan?)</div>
                    <div class="kpi-change positive">{_score_label(em.get('answer_relevancy',0))}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon" style="background:rgba(139,92,246,0.2)">📚</div>
                    <div class="kpi-value" style="color:{_score_color(em.get('context_precision',0))}">{em.get('context_precision',0):.2f}</div>
                    <div class="kpi-label">Context Precision (Recupero docs)</div>
                    <div class="kpi-change positive">{_score_label(em.get('context_precision',0))}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon" style="background:rgba(245,158,11,0.2)">📋</div>
                    <div class="kpi-value" style="color:{_score_color(em.get('completeness',0))}">{em.get('completeness',0):.2f}</div>
                    <div class="kpi-label">Completeness (Info completa)</div>
                    <div class="kpi-change positive">{_score_label(em.get('completeness',0))}</div>
                </div>
            </div>
            <div style="background:var(--bg-card);border-radius:12px;padding:16px 20px;margin-bottom:24px;border:1px solid var(--border)">
                <div style="font-size:13px;color:var(--text-secondary);line-height:1.6">
                    <strong style="color:var(--text-primary)">Interpretación para la tesis:</strong><br>
                    • <strong>Faithfulness ≥ 0.80</strong> = El sistema NO alucina → cumple Ley 29571 (protección al consumidor)<br>
                    • <strong>Relevancy ≥ 0.80</strong> = Las respuestas son útiles y directas para el turista<br>
                    • <strong>Context Precision</strong> = El retriever recupera los documentos correctos (ChromaDB funciona)<br>
                    • <strong>Completeness</strong> = Las respuestas cubren la información disponible en los documentos
                </div>
            </div>
        """

    # Construir filas de la tabla
    rows_html = ""
    for interaction in interactions:
        status_icon = "✅" if interaction['resolved_autonomously'] else "❌"
        status_class = "resolved" if interaction['resolved_autonomously'] else "escalated"
        escalation_badge = '<span class="badge badge-danger">ESCALADO</span>' if interaction['escalated_to_human'] else ""
        channel_icon = {"whatsapp": "💬", "messenger": "📨", "test": "🧪"}.get(interaction['channel'], "💬")

        rows_html += f"""
        <tr class="{status_class}">
            <td><span class="id-badge">#{interaction['id']}</span></td>
            <td><span class="timestamp">{interaction['timestamp'][:16].replace('T', ' ')}</span></td>
            <td><span class="user-id">{interaction['user_id'][:12]}...</span></td>
            <td><span class="channel-badge channel-{interaction['channel']}">{channel_icon} {interaction['channel']}</span></td>
            <td><span class="lang-badge">{interaction['detected_language'].upper()}</span></td>
            <td><div class="message-cell" title="{interaction['user_message'][:200]}">{interaction['user_message'][:40]}...</div></td>
            <td><div class="response-cell" title="{interaction['bot_response'][:200]}">{interaction['bot_response'][:45]}...</div></td>
            <td>{status_icon} {escalation_badge}</td>
            <td><span class="latency {'latency-good' if interaction['latency_ms'] < 5000 else 'latency-bad'}">{interaction['latency_ms']:.0f}ms</span></td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Texeira Travel Tour — Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-primary: #0f172a;
                --bg-secondary: #1e293b;
                --bg-card: #1e293b;
                --bg-card-hover: #334155;
                --text-primary: #f1f5f9;
                --text-secondary: #94a3b8;
                --accent-blue: #3b82f6;
                --accent-green: #10b981;
                --accent-red: #ef4444;
                --accent-yellow: #f59e0b;
                --accent-purple: #8b5cf6;
                --border: #334155;
            }}

            * {{ margin: 0; padding: 0; box-sizing: border-box; }}

            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: var(--bg-primary);
                color: var(--text-primary);
                min-height: 100vh;
            }}

            .container {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 24px;
            }}

            /* Header */
            .header {{
                background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
                border-radius: 20px;
                padding: 32px;
                margin-bottom: 24px;
                position: relative;
                overflow: hidden;
            }}

            .header::before {{
                content: '';
                position: absolute;
                top: -50%;
                right: -20%;
                width: 400px;
                height: 400px;
                background: rgba(255,255,255,0.1);
                border-radius: 50%;
            }}

            .header-content {{
                position: relative;
                z-index: 1;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}

            .header h1 {{
                font-size: 28px;
                font-weight: 700;
                margin-bottom: 8px;
            }}

            .header p {{
                color: rgba(255,255,255,0.8);
                font-size: 14px;
            }}

            .header-badge {{
                background: rgba(255,255,255,0.2);
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 500;
            }}

            /* KPI Grid */
            .kpi-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 16px;
                margin-bottom: 24px;
            }}

            .kpi-card {{
                background: var(--bg-card);
                border-radius: 16px;
                padding: 24px;
                border: 1px solid var(--border);
                transition: all 0.3s ease;
            }}

            .kpi-card:hover {{
                transform: translateY(-4px);
                box-shadow: 0 12px 40px rgba(0,0,0,0.3);
            }}

            .kpi-icon {{
                width: 48px;
                height: 48px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                margin-bottom: 16px;
            }}

            .kpi-icon.blue {{ background: rgba(59,130,246,0.2); }}
            .kpi-icon.green {{ background: rgba(16,185,129,0.2); }}
            .kpi-icon.yellow {{ background: rgba(245,158,11,0.2); }}
            .kpi-icon.purple {{ background: rgba(139,92,246,0.2); }}
            .kpi-icon.indigo {{ background: rgba(99,102,241,0.2); }}

            .kpi-value {{
                font-size: 36px;
                font-weight: 700;
                margin-bottom: 4px;
            }}

            .kpi-label {{
                color: var(--text-secondary);
                font-size: 13px;
                font-weight: 500;
            }}

            .kpi-change {{
                font-size: 12px;
                margin-top: 8px;
                padding: 4px 8px;
                border-radius: 6px;
                display: inline-block;
            }}

            .kpi-change.positive {{ background: rgba(16,185,129,0.2); color: var(--accent-green); }}
            .kpi-change.negative {{ background: rgba(239,68,68,0.2); color: var(--accent-red); }}

            /* Section Header */
            .section-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
            }}

            .section-title {{
                font-size: 18px;
                font-weight: 600;
            }}

            .refresh-btn {{
                background: var(--accent-blue);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s;
            }}

            .refresh-btn:hover {{
                background: #2563eb;
                transform: scale(1.05);
            }}

            /* Table */
            .table-container {{
                background: var(--bg-card);
                border-radius: 16px;
                overflow: hidden;
                border: 1px solid var(--border);
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
            }}

            th {{
                background: var(--bg-secondary);
                padding: 16px 12px;
                text-align: left;
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: var(--text-secondary);
                border-bottom: 1px solid var(--border);
            }}

            td {{
                padding: 14px 12px;
                border-bottom: 1px solid var(--border);
                font-size: 13px;
            }}

            tr:hover {{
                background: var(--bg-card-hover);
            }}

            tr:last-child td {{
                border-bottom: none;
            }}

            .id-badge {{
                background: var(--accent-purple);
                color: white;
                padding: 4px 10px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }}

            .timestamp {{
                color: var(--text-secondary);
                font-size: 12px;
            }}

            .user-id {{
                font-family: monospace;
                background: var(--bg-primary);
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
            }}

            .channel-badge {{
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
            }}

            .channel-whatsapp {{ background: rgba(37,211,102,0.2); color: #25d366; }}
            .channel-messenger {{ background: rgba(0,132,255,0.2); color: #0084ff; }}
            .channel-test {{ background: rgba(148,163,184,0.2); color: #94a3b8; }}

            .lang-badge {{
                background: var(--accent-blue);
                color: white;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }}

            .message-cell, .response-cell {{
                max-width: 200px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                color: var(--text-secondary);
            }}

            .badge-danger {{
                background: var(--accent-red);
                color: white;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 10px;
                font-weight: 600;
                margin-left: 8px;
            }}

            .latency {{
                font-family: monospace;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }}

            .latency-good {{ background: rgba(16,185,129,0.2); color: var(--accent-green); }}
            .latency-bad {{ background: rgba(239,68,68,0.2); color: var(--accent-red); }}

            .resolved {{ background: rgba(16,185,129,0.05); }}
            .escalated {{ background: rgba(239,68,68,0.05); }}

            .no-data {{
                text-align: center;
                padding: 60px 20px;
                color: var(--text-secondary);
            }}

            .no-data-icon {{
                font-size: 48px;
                margin-bottom: 16px;
            }}

            .footer {{
                text-align: center;
                margin-top: 32px;
                padding: 20px;
                color: var(--text-secondary);
                font-size: 13px;
            }}

            /* Responsive */
            @media (max-width: 1200px) {{
                .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
            }}

            @media (max-width: 768px) {{
                .kpi-grid {{ grid-template-columns: 1fr; }}
                .header-content {{ flex-direction: column; gap: 16px; text-align: center; }}
            }}

            /* Animación de carga */
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}

            .kpi-card, .table-container {{
                animation: fadeIn 0.5s ease-out;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-content">
                    <div>
                        <h1>✈️ Texeira Travel Tour</h1>
                        <p>Panel de Control del Agente Conversacional RAG</p>
                    </div>
                    <div class="header-badge">🔄 Auto-refresh: 30s</div>
                </div>
            </div>

            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-icon blue">📊</div>
                    <div class="kpi-value">{metrics['total_interactions']}</div>
                    <div class="kpi-label">Total Interacciones</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon green">⚡</div>
                    <div class="kpi-value">{metrics['avg_latency_ms']:.0f}ms</div>
                    <div class="kpi-label">Latencia Promedio</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon yellow">✅</div>
                    <div class="kpi-value" style="color: {resolution_color}">{metrics['resolution_rate_pct']:.1f}%</div>
                    <div class="kpi-label">Resolución Autónoma</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon purple">🔄</div>
                    <div class="kpi-value" style="color: {escalation_color}">{metrics['escalation_rate_pct']:.1f}%</div>
                    <div class="kpi-label">Escalamiento Humano</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-icon indigo">🌙</div>
                    <div class="kpi-value">{metrics.get('after_hours_count', 0)}</div>
                    <div class="kpi-label">Fuera de Horario (18:00 - 08:00)</div>
                    <div class="kpi-change positive">{metrics.get('after_hours_pct', 0.0):.1f}% del tráfico</div>
                </div>
            </div>

            {eval_html}

            <div class="section-header">
                <div class="section-title">📋 Últimas Interacciones</div>
                <button class="refresh-btn" onclick="location.reload()">🔄 Actualizar</button>
            </div>

            <div class="table-container">
                {"<div class='no-data'><div class='no-data-icon'>📭</div><p>No hay interacciones registradas aún</p><p>Envía mensajes via /test-chat para comenzar</p></div>" if not interactions else f'''
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Fecha</th>
                            <th>Usuario</th>
                            <th>Canal</th>
                            <th>Idioma</th>
                            <th>Mensaje</th>
                            <th>Respuesta</th>
                            <th>Estado</th>
                            <th>Latencia</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
                '''}
            </div>

            <div class="footer">
                Texeira Travel Tour — Agente RAG v1.0 | Investigación Universitaria
            </div>
        </div>

        <script>
            // Auto-refresh cada 30 segundos
            setTimeout(function() {{ location.reload(); }}, 30000);
        </script>
    </body>
    </html>
    """
    return html

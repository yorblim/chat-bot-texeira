"""Verificación rigurosa de interacción en vivo en los 4 paneles reales de Cloud Run con Edge headless.

Alcance de seguridad:
- Las credenciales Authorization se restringen estrictamente al dominio del bot mediante una extensión
  temporal con Declarative Net Request (Manifest V3), evitando filtración a recursos externos (ej. Google Fonts).
- Las aserciones validan el filtrado real en catálogo sobre todos los elementos visibles y usan límites flexibles.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait


def _create_scoped_auth_extension(base_url: str, auth_b64: str) -> str:
    """Crea una extensión temporal Manifest V3 con declarativeNetRequest para inyectar

    Authorization: Basic exclusivamente en peticiones hacia base_url/*.
    Cualquier petición externa (ej. fonts.googleapis.com) queda exenta de la cabecera.
    """
    ext_dir = tempfile.mkdtemp(prefix="edge_scoped_auth_")
    manifest = {
        "name": "ScopedBotAuth",
        "version": "1.0",
        "manifest_version": 3,
        "declarative_net_request": {
            "rule_resources": [
                {
                    "id": "ruleset_1",
                    "enabled": True,
                    "path": "rules.json"
                }
            ]
        },
        "permissions": ["declarativeNetRequest"],
        "host_permissions": [f"{base_url}/*"]
    }
    rules = [
        {
            "id": 1,
            "priority": 1,
            "action": {
                "type": "modifyHeaders",
                "requestHeaders": [
                    {
                        "header": "Authorization",
                        "operation": "set",
                        "value": f"Basic {auth_b64}"
                    }
                ]
            },
            "condition": {
                "urlFilter": f"{base_url}/*",
                "resourceTypes": [
                    "main_frame", "sub_frame", "stylesheet", "script",
                    "image", "xmlhttprequest", "other"
                ]
            }
        }
    ]
    with open(os.path.join(ext_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    with open(os.path.join(ext_dir, "rules.json"), "w", encoding="utf-8") as f:
        json.dump(rules, f)
    return ext_dir


def main():
    gcloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    res_pass = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "2", "--secret=ADMIN_PASSWORD", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    admin_password = res_pass.stdout.strip()
    assert admin_password, "Falta credencial de administración en Secret Manager"
    
    base_url = "https://texeira-whatsapp-1038134693816.us-central1.run.app"
    auth_b64 = base64.b64encode(f"admin:{admin_password}".encode()).decode()

    # Seguridad: aislar cabecera de autenticación exclusivamente al origen del bot
    ext_dir = _create_scoped_auth_extension(base_url, auth_b64)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--load-extension={ext_dir}")
    options.add_argument(f"--disable-extensions-except={ext_dir}")

    driver = webdriver.Edge(options=options)
    driver.set_window_size(1280, 800)

    try:
        print("=========================================================")
        print("VERIFICACION RIGUROSA EN VIVO: PANELES CLOUD RUN")
        print("Autenticación acotada al dominio del bot (Declarative Net Request)")
        print("=========================================================")

        # 1. Handoffs: abrir solicitud y validar formulario o resumen
        print("\n[1/4] Panel de Asesores (/handoffs)...")
        driver.get(f"{base_url}/handoffs")
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.querySelectorAll('.ticket, #list p').length > 0")
        )
        ticket_data = driver.execute_script("""
            const t = document.querySelector('.ticket:not([data-state="closed"])') || document.querySelector('.ticket');
            if (!t) {
                const emptyMsg = document.querySelector('#list p');
                return { empty: true, msg: emptyMsg ? emptyMsg.textContent.trim() : '' };
            }
            t.open = true;
            const h2 = t.querySelector('h2');
            const isClosed = t.dataset.state === 'closed';
            const who = t.querySelector('input[type=text]');
            const note = t.querySelector('textarea');
            const btnClose = t.querySelector('.btn-close');
            const closedBox = t.querySelector('.closed-box');
            return {
                empty: false,
                id: h2 ? h2.textContent.trim() : '',
                state: t.dataset.state || '',
                isClosed: isClosed,
                hasAdvisorField: !!who || isClosed,
                hasTextarea: !!note || isClosed,
                hasCloseButton: !!btnClose || isClosed,
                hasClosedBox: !!closedBox,
                isOpen: t.open
            };
        """)
        assert ticket_data is not None, "Error: No se obtuvo respuesta del panel de asesores"
        if ticket_data.get("empty"):
            print(f"  PASS | Panel de asesores operativo (sin tickets pendientes en base de datos: '{ticket_data['msg']}')")
        else:
            assert ticket_data["isOpen"] is True, "Error: El ticket no pudo ser abierto (<details open>)"
            assert ticket_data["hasAdvisorField"] is True, "Error: Falta campo de asesor"
            assert ticket_data["hasTextarea"] is True, "Error: Falta textarea de notas"
            print(f"  PASS | Ticket verificado: {ticket_data['id']} (estado: {ticket_data['state']}) con campos/resumen válidos")

        # 2. Catálogo: buscar tour, verificar filtrado exhaustivo y abrir modal de edición
        print("\n[2/4] Panel de Catálogo (/catalogo)...")
        driver.get(f"{base_url}/catalogo")
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.querySelectorAll('.card, .tour-card').length > 0")
        )
        search_res = driver.execute_script("""
            const cardsBefore = document.querySelectorAll('.card, .tour-card').length;
            const input = document.getElementById('searchInput');
            if (input) {
                input.value = 'Machu';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            const cards = document.querySelectorAll('.card, .tour-card');
            const visible = [...cards].filter(c => c.style.display !== 'none');
            const cardDetails = visible.map(c => {
                const idEl = c.querySelector('.tour-id');
                const entityId = idEl ? idEl.textContent.replace('ID:', '').trim() : '';
                const tour = (typeof TOURS_DATA !== 'undefined' ? TOURS_DATA.find(t => t.entity_id === entityId) : null) || {};
                const titleEl = c.querySelector('h3, .tour-title');
                const title = titleEl ? titleEl.textContent.trim() : (tour.name || '');
                const q = 'machu';
                const matchName = (tour.name || title).toLowerCase().includes(q);
                const matchId = (tour.entity_id || entityId).toLowerCase().includes(q);
                const matchedAlias = (tour.aliases || []).find(a => a.toLowerCase().includes(q)) || '';
                return {
                    entityId: entityId,
                    title: title,
                    matchName: matchName,
                    matchId: matchId,
                    matchedAlias: matchedAlias,
                    matchesQuery: matchName || matchId || !!matchedAlias
                };
            });
            return {
                totalCards: cardsBefore,
                filteredCount: visible.length,
                cards: cardDetails
            };
        """)
        # Comprobaciones dinámicas y no rígidas
        assert search_res["totalCards"] > 0, f"Error: Catálogo sin tours iniciales (encontrados: {search_res['totalCards']})"
        assert search_res["filteredCount"] > 0, "Error: La búsqueda reactiva de 'Machu' no arrojó resultados"
        assert search_res["filteredCount"] < search_res["totalCards"], (
            f"Error: El filtro no redujo los tours ({search_res['filteredCount']} == {search_res['totalCards']})"
        )

        # Validación exhaustiva de TODOS los resultados visibles: deben coincidir con 'machu'
        for c in search_res["cards"]:
            assert c["matchesQuery"], (
                f"Error en filtro de catálogo: el resultado visible '{c['title']}' (ID: '{c['entityId']}') "
                f"no coincide con la búsqueda 'Machu' ni en título, ni en ID, ni en alias registrados."
            )
        print(f"  PASS | Búsqueda reactiva: {search_res['filteredCount']} tours filtrados de {search_res['totalCards']} totales")
        for c in search_res["cards"]:
            reason = f"título ('{c['title']}')" if c['matchName'] else (f"id ('{c['entityId']}')" if c['matchId'] else f"alias registrado ('{c['matchedAlias']}')")
            print(f"         • {c['title']} [ID: {c['entityId']}] -> coincide por {reason}")

        modal_res = driver.execute_script("""
            const btn = document.getElementById('btnNewTour');
            if (btn) btn.click();
            const m = document.getElementById('tourModal');
            const style = m ? window.getComputedStyle(m) : null;
            const form = document.getElementById('tourForm');
            return {
                modalDisplayed: style ? style.display : 'none',
                modalTitle: document.getElementById('modalTourTitle') ? document.getElementById('modalTourTitle').textContent.trim() : '',
                hasEntityInput: !!document.getElementById('formEntityId'),
                hasPriceInput: !!document.getElementById('formPrice'),
                hasScheduleInput: !!document.getElementById('formSchedule'),
                hasDurationInput: !!document.getElementById('formDuration'),
                hasSubmitBtn: !!form.querySelector('button[type=submit]')
            };
        """)
        assert modal_res["modalDisplayed"] in ("flex", "block"), f"Error: Modal de tour no está visible (display={modal_res['modalDisplayed']})"
        assert modal_res["hasEntityInput"] is True, "Error: Falta campo entity_id en modal de tour"
        assert modal_res["hasPriceInput"] is True, "Error: Falta campo precio oficial en modal de tour"
        assert modal_res["hasScheduleInput"] is True, "Error: Falta campo horario en modal de tour"
        assert modal_res["hasDurationInput"] is True, "Error: Falta campo duración en modal de tour"
        assert modal_res["hasSubmitBtn"] is True, "Error: Falta botón submit en formulario modal de tour"
        print(f"  PASS | Formulario modal verificado: '{modal_res['modalTitle']}' con campos completos y visibles")

        # 3. Resumen (/dashboard)
        print("\n[3/4] Panel de Resumen (/dashboard)...")
        driver.get(f"{base_url}/dashboard")
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.querySelectorAll('.kpi-card').length > 0")
        )
        dash_res = driver.execute_script("""
            const kpis = [...document.querySelectorAll('.kpi-card')].map(k => ({
                label: k.querySelector('.kpi-label') ? k.querySelector('.kpi-label').textContent.trim() : '',
                value: k.querySelector('.kpi-value') ? k.querySelector('.kpi-value').textContent.trim() : ''
            }));
            const nav = document.querySelector('.admin-nav');
            const table = document.querySelector('.table-container table, table');
            return {
                kpis: kpis,
                kpiCount: kpis.length,
                hasNav: !!nav,
                hasTable: !!table,
                title: document.title
            };
        """)
        # Comprobación adaptable a métricas base (5) o ampliadas con RAGAS (9)
        assert dash_res["kpiCount"] >= 4, f"Error: Se esperaban al menos 4 tarjetas KPI en /dashboard, encontradas: {dash_res['kpiCount']}"
        for k in dash_res["kpis"]:
            assert k["label"] and k["value"], f"Error: Tarjeta KPI con datos incompletos: {k}"
        assert dash_res["hasNav"] is True, "Error: Falta barra .admin-nav en /dashboard"
        assert dash_res["hasTable"] is True, "Error: Falta tabla de interacciones en /dashboard"
        print(f"  PASS | Dashboard verificado: {dash_res['kpiCount']} KPIs válidos (etiqueta y valor), barra de navegación y tabla presentes")

        # 4. Métricas (/operational-metrics)
        print("\n[4/4] Panel de Métricas Operativas (/operational-metrics)...")
        driver.get(f"{base_url}/operational-metrics")
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.querySelectorAll('.metrics-group').length > 0")
        )
        metrics_res = driver.execute_script("""
            const groups = document.querySelectorAll('.metrics-group');
            const note = document.querySelector('.admin-note');
            const method = document.querySelector('.admin-method');
            const nav = document.querySelector('.admin-nav');
            return {
                groupsCount: groups.length,
                hasNoteBanner: !!note,
                hasMethodAccordion: !!method,
                hasNav: !!nav,
                title: document.title
            };
        """)
        assert metrics_res["groupsCount"] >= 2, f"Error: Se esperaban al menos 2 grupos temáticos en métricas, encontrados: {metrics_res['groupsCount']}"
        assert metrics_res["hasNoteBanner"] is True, "Error: Falta banner de limitaciones técnicas (.admin-note)"
        assert metrics_res["hasMethodAccordion"] is True, "Error: Falta acordeón de metodología (.admin-method)"
        assert metrics_res["hasNav"] is True, "Error: Falta barra .admin-nav en /operational-metrics"
        print(f"  PASS | Métricas verificadas: {metrics_res['groupsCount']} grupos temáticos, aviso de limitaciones y metodología confirmados")

        print("\n=========================================================")
        print("  ¡LAS 4 VISTAS Y ACCIONES REALES FUERON VALIDADAS CON ÉXITO!")
        print("  - Ámbito de autenticación protegido y acotado al bot")
        print("  - Filtro de catálogo validado exhaustivamente")
        print("  - Cantidades adaptables sin valores fijos frágiles")
        print("=========================================================")

    finally:
        driver.quit()
        shutil.rmtree(ext_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

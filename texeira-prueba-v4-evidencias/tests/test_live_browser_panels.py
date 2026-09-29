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
    Si ocurre cualquier fallo durante la escritura de archivos, se garantiza la limpieza
    del directorio temporal antes de propagar la excepción.
    """
    ext_dir = tempfile.mkdtemp(prefix="edge_scoped_auth_")
    try:
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
    except Exception:
        shutil.rmtree(ext_dir, ignore_errors=True)
        raise



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

    ext_dir = None
    driver = None

    try:
        # 1. Seguridad: aislar cabecera de autenticación al origen del bot
        # Protegido por finally: si Edge falla al iniciar, ext_dir se elimina inmediatamente.
        ext_dir = _create_scoped_auth_extension(base_url, auth_b64)

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--load-extension={ext_dir}")
        options.add_argument(f"--disable-extensions-except={ext_dir}")

        driver = webdriver.Edge(options=options)
        driver.set_window_size(1280, 800)

        print("=========================================================")
        print("VERIFICACION RIGUROSA EN VIVO: PANELES CLOUD RUN")
        print("Autenticación acotada al dominio del bot (Declarative Net Request)")
        print("=========================================================")

        # 1. Handoffs: abrir solicitud y validar formulario o resumen con distinción de error
        print("\n[1/4] Panel de Asesores (/handoffs)...")
        driver.get(f"{base_url}/handoffs")
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.querySelectorAll('.ticket, #list p, #feedback.error').length > 0")
        )
        ticket_res = driver.execute_script("""
            const errEl = document.querySelector('#list p.error, #feedback.error');
            const emptyEl = document.querySelector('#list > p:not(.error)');
            const allTickets = [...document.querySelectorAll('.ticket')];
            const activeTicket = allTickets.find(t => t.dataset.state !== 'closed');
            const closedTicket = allTickets.find(t => t.dataset.state === 'closed');

            let activeData = null;
            if (activeTicket) {
                activeTicket.open = true;
                const h2 = activeTicket.querySelector('h2');
                const who = activeTicket.querySelector('input[type=text]');
                const note = activeTicket.querySelector('textarea');
                const btnClose = activeTicket.querySelector('.btn-close');
                activeData = {
                    id: h2 ? h2.textContent.trim() : '',
                    state: activeTicket.dataset.state || '',
                    isOpen: activeTicket.open,
                    hasAdvisorField: !!who,
                    hasTextarea: !!note,
                    hasCloseButton: !!btnClose
                };
            }

            let closedData = null;
            if (closedTicket) {
                closedTicket.open = true;
                const h2 = closedTicket.querySelector('h2');
                const closedBox = closedTicket.querySelector('.closed-box');
                closedData = {
                    id: h2 ? h2.textContent.trim() : '',
                    state: closedTicket.dataset.state || '',
                    isOpen: closedTicket.open,
                    hasClosedBox: !!closedBox
                };
            }

            return {
                hasLoadError: !!errEl,
                loadErrorMessage: errEl ? errEl.textContent.trim() : '',
                isEmpty: !!emptyEl && emptyEl.textContent.includes('No hay solicitudes registradas'),
                emptyMessage: emptyEl ? emptyEl.textContent.trim() : '',
                totalTickets: allTickets.length,
                activeTicket: activeData,
                closedTicket: closedData
            };
        """)
        assert ticket_res is not None, "Error: No se obtuvo respuesta del panel de asesores"
        # Distinguir explícitamente un error de carga de un estado vacío
        assert not ticket_res["hasLoadError"], (
            f"Error de carga en panel de asesores: '{ticket_res['loadErrorMessage']}'"
        )

        if ticket_res["isEmpty"]:
            assert ticket_res["totalTickets"] == 0, (
                f"Inconsistencia en /handoffs: mensaje de lista vacía pero se encontraron {ticket_res['totalTickets']} tickets"
            )
            assert "No hay solicitudes registradas" in ticket_res["emptyMessage"], (
                f"Mensaje de lista vacía inesperado: '{ticket_res['emptyMessage']}'"
            )
            print(f"  PASS | Panel de asesores operativo (estado vacío legítimo confirmado: '{ticket_res['emptyMessage']}')")
        else:
            assert ticket_res["totalTickets"] > 0, (
                "Error en /handoffs: la lista no tiene tickets ni muestra el mensaje formal de estado vacío"
            )

            # Comprobar aserciones de ticket activo
            if ticket_res["activeTicket"]:
                act = ticket_res["activeTicket"]
                assert act["isOpen"] is True, f"Error: Ticket activo {act['id']} no pudo abrirse (<details open>)"
                assert act["hasAdvisorField"] is True, f"Error: Falta campo de asesor en ticket activo {act['id']}"
                assert act["hasTextarea"] is True, f"Error: Falta textarea de notas en ticket activo {act['id']}"
                assert act["hasCloseButton"] is True, f"Error: Falta botón de cerrar (.btn-close) en formulario de ticket activo {act['id']}"
                print(f"  PASS | Ticket activo verificado: {act['id']} (estado: {act['state']}) con asesor, textarea y botón de cerrar comprobados")

            # Comprobar aserciones de ticket cerrado
            if ticket_res["closedTicket"]:
                cls = ticket_res["closedTicket"]
                assert cls["isOpen"] is True, f"Error: Ticket cerrado {cls['id']} no pudo abrirse (<details open>)"
                assert cls["hasClosedBox"] is True, f"Error: Falta caja informativa (.closed-box) en ticket cerrado {cls['id']}"
                print(f"  PASS | Ticket cerrado verificado: {cls['id']} (estado: {cls['state']}) con resumen de atención (.closed-box) comprobado")

            assert ticket_res["activeTicket"] or ticket_res["closedTicket"], (
                "Error: No se pudo extraer información ni de ticket activo ni de ticket cerrado"
            )

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

        # 3. Resumen (/dashboard): comprobación de las 5 métricas base por su identidad
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
        # Validación de identidad: las 5 métricas base deben estar obligatoriamente presentes
        REQUIRED_BASE_KPIS = [
            ("total interacciones", "Total Interacciones"),
            ("latencia promedio", "Latencia Promedio"),
            ("resolución autónoma", "Resolución Autónoma"),
            ("escalamiento humano", "Escalamiento Humano"),
            ("fuera de horario", "Fuera de Horario"),
        ]
        found_kpi_labels = [k["label"].lower() for k in dash_res["kpis"]]
        for needle, display_name in REQUIRED_BASE_KPIS:
            assert any(needle in lbl for lbl in found_kpi_labels), (
                f"Error: Falta la métrica base obligatoria '{display_name}' en /dashboard. "
                f"Métricas encontradas: {[k['label'] for k in dash_res['kpis']]}"
            )

        # Validación estructural de cada tarjeta (permitiendo tarjetas adicionales como RAGAS)
        for k in dash_res["kpis"]:
            assert k["label"] and k["value"], f"Error: Tarjeta KPI con datos incompletos: {k}"
        assert dash_res["hasNav"] is True, "Error: Falta barra .admin-nav en /dashboard"
        assert dash_res["hasTable"] is True, "Error: Falta tabla de interacciones en /dashboard"
        print(f"  PASS | Dashboard verificado: {dash_res['kpiCount']} KPIs detectados (las 5 métricas base identificadas y validadas)")

        # 4. Métricas (/operational-metrics): comprobación de las 3 secciones por su identidad
        print("\n[4/4] Panel de Métricas Operativas (/operational-metrics)...")
        driver.get(f"{base_url}/operational-metrics")
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.querySelectorAll('.metrics-group').length > 0")
        )
        metrics_res = driver.execute_script("""
            const groups = [...document.querySelectorAll('.metrics-group')].map(g => {
                const h2 = g.querySelector('h2');
                const tbody = g.querySelector('tbody');
                return {
                    title: h2 ? h2.textContent.trim() : '',
                    tableId: tbody ? tbody.id : ''
                };
            });
            const note = document.querySelector('.admin-note');
            const method = document.querySelector('.admin-method');
            const nav = document.querySelector('.admin-nav');
            return {
                groups: groups,
                groupsCount: groups.length,
                hasNoteBanner: !!note,
                hasMethodAccordion: !!method,
                hasNav: !!nav,
                title: document.title
            };
        """)
        # Validación de identidad: las 3 secciones temáticas deben estar presentes
        REQUIRED_SECTIONS = [
            ("rows-traffic", "mensajería y envíos", "📨 Mensajería y Envíos WhatsApp"),
            ("rows-latency", "tiempos de respuesta", "⏱️ Tiempos de Respuesta (Latencia)"),
            ("rows-human", "atención humana", "🛎️ Solicitudes de Atención Humana"),
        ]
        for table_id, title_frag, display_name in REQUIRED_SECTIONS:
            matched = any(
                (g["tableId"] == table_id or title_frag in g["title"].lower())
                for g in metrics_res["groups"]
            )
            assert matched, (
                f"Error: Falta la sección obligatoria '{display_name}' (ID: '{table_id}') en /operational-metrics. "
                f"Secciones presentes: {[g['title'] for g in metrics_res['groups']]}"
            )

        assert metrics_res["hasNoteBanner"] is True, "Error: Falta banner de limitaciones técnicas (.admin-note)"
        assert metrics_res["hasMethodAccordion"] is True, "Error: Falta acordeón de metodología (.admin-method)"
        assert metrics_res["hasNav"] is True, "Error: Falta barra .admin-nav en /operational-metrics"
        print(f"  PASS | Métricas verificadas: {metrics_res['groupsCount']} grupos temáticos (las 3 secciones base identificadas y confirmadas)")

        print("\n=========================================================")
        print("  ¡LAS 4 VISTAS Y ACCIONES REALES FUERON VALIDADAS CON ÉXITO!")
        print("  - Ciclo de vida de extensión y credenciales protegido por finally")
        print("  - Atención al cliente: distinción de error y aserciones de botones y cajas")
        print("  - 5 métricas base y 3 secciones temáticas verificadas por identidad")
        print("=========================================================")

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        if ext_dir is not None:
            shutil.rmtree(ext_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

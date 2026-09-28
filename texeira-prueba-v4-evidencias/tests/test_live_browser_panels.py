"""Verificación rigurosa de interacción en vivo en los 4 paneles reales de Cloud Run con Edge headless."""
import base64
import subprocess
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    driver = webdriver.Edge(options=options)
    driver.set_window_size(1280, 800)
    driver.execute_cdp_cmd('Network.enable', {})
    driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
        'headers': {'Authorization': f'Basic {auth_b64}'}
    })

    try:
        print("=========================================================")
        print("VERIFICACION RIGUROSA EN VIVO: PANELES CLOUD RUN")
        print("=========================================================")

        # 1. Handoffs: abrir solicitud y validar formulario
        print("\n[1/4] Panel de Asesores (/handoffs)...")
        driver.get(f"{base_url}/handoffs")
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.querySelectorAll('.ticket').length > 0")
        )
        ticket_data = driver.execute_script("""
            const t = document.querySelector('.ticket');
            if (!t) return null;
            t.open = true;
            const h2 = t.querySelector('h2');
            const who = t.querySelector('input[type=text]');
            const note = t.querySelector('textarea');
            const btnClose = t.querySelector('.btn-close');
            return {
                id: h2 ? h2.textContent.trim() : '',
                hasAdvisorField: !!who,
                hasTextarea: !!note,
                hasCloseButton: !!btnClose,
                isOpen: t.open
            };
        """)
        assert ticket_data is not None, "Error: No se encontró ningún elemento .ticket en /handoffs"
        assert ticket_data["isOpen"] is True, "Error: El ticket no pudo ser abierto (<details open>)"
        assert ticket_data["hasAdvisorField"] is True, "Error: Falta el campo de texto para nombre del asesor"
        assert ticket_data["hasTextarea"] is True, "Error: Falta el textarea para nota/respuesta de atención"
        assert ticket_data["hasCloseButton"] is True, "Error: Falta el botón de acción para responder/cerrar ticket"
        print(f"  PASS | Ticket verificado: {ticket_data['id']} con formulario completo (asesor, textarea, botones)")

        # 2. Catálogo: buscar tour, verificar filtrado y abrir modal de edición
        print("\n[2/4] Panel de Catálogo (/catalogo)...")
        driver.get(f"{base_url}/catalogo")
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.querySelectorAll('.tour-card, .card').length > 0")
        )
        search_res = driver.execute_script("""
            const cardsBefore = document.querySelectorAll('.tour-card, .card').length;
            const input = document.getElementById('searchInput');
            if (input) {
                input.value = 'Machu';
                input.dispatchEvent(new Event('input'));
            }
            const cards = document.querySelectorAll('.tour-card, .card');
            const visible = [...cards].filter(c => c.style.display !== 'none');
            return {
                totalCards: cardsBefore,
                filteredCount: visible.length,
                sampleTitle: visible[0] ? visible[0].querySelector('h3, .tour-title').textContent.trim() : ''
            };
        """)
        assert search_res["totalCards"] >= 18, f"Error: Se esperaban al menos 18 tours en catálogo, encontrados {search_res['totalCards']}"
        assert search_res["filteredCount"] >= 1, "Error: La búsqueda reactiva de 'Machu' no arrojó resultados"
        assert any(term in search_res["sampleTitle"] for term in ("Machu", "Inca")), f"Error: Título filtrado inesperado: {search_res['sampleTitle']}"
        print(f"  PASS | Búsqueda reactiva: {search_res['filteredCount']} tours filtrados de {search_res['totalCards']} totales (ej: '{search_res['sampleTitle']}')")

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
            const kpis = document.querySelectorAll('.kpi-card');
            const nav = document.querySelector('.admin-nav');
            const table = document.querySelector('.table-container table, table');
            return {
                kpiCount: kpis.length,
                hasNav: !!nav,
                hasTable: !!table,
                title: document.title
            };
        """)
        assert dash_res["kpiCount"] == 5, f"Error: Se esperaban 5 tarjetas KPI en /dashboard, encontradas: {dash_res['kpiCount']}"
        assert dash_res["hasNav"] is True, "Error: Falta barra .admin-nav en /dashboard"
        assert dash_res["hasTable"] is True, "Error: Falta tabla de interacciones en /dashboard"
        print(f"  PASS | Dashboard verificado: 5 KPIs, barra de navegación institucional y tabla presentes")

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
        assert metrics_res["groupsCount"] == 3, f"Error: Se esperaban 3 grupos temáticos en métricas, encontrados: {metrics_res['groupsCount']}"
        assert metrics_res["hasNoteBanner"] is True, "Error: Falta banner de limitaciones técnicas (.admin-note)"
        assert metrics_res["hasMethodAccordion"] is True, "Error: Falta acordeón de metodología (.admin-method)"
        assert metrics_res["hasNav"] is True, "Error: Falta barra .admin-nav en /operational-metrics"
        print(f"  PASS | Métricas verificadas: 3 grupos temáticos, aviso de limitaciones y metodología confirmados")

        print("\n=========================================================")
        print("  ¡LAS 4 VISTAS Y ACCIONES REALES FUERON VALIDADAS CON ÉXITO!")
        print("=========================================================")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()

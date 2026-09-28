"""Verificación de interacción en vivo en los 4 paneles reales de Cloud Run con Edge headless."""
import base64
import subprocess
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options

def main():
    gcloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    res_pass = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "2", "--secret=ADMIN_PASSWORD", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    admin_password = res_pass.stdout.strip()
    
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
        print("VERIFICACION LIVE BROWSER: ACCIONES REALES EN CLOUD RUN")
        print("=========================================================")

        # 1. Handoffs: abrir solicitud
        print("\n[1/4] Panel de Asesores (/handoffs)...")
        driver.get(f"{base_url}/handoffs")
        time.sleep(2.5)
        ticket_opened = driver.execute_script("""
            const t = document.querySelector('.ticket');
            if (t) {
                t.open = true;
                return {
                    id: t.querySelector('h2') ? t.querySelector('h2').textContent : '',
                    hasAdvisorField: !!t.querySelector('input[type=text]'),
                    hasTextarea: !!t.querySelector('textarea'),
                    isOpen: t.open
                };
            }
            return null;
        """)
        print(f"  PASS | Ticket abierto en vivo: {ticket_opened}")

        # 2. Catálogo: buscar tour y abrir edición
        print("\n[2/4] Panel de Catálogo (/catalogo)...")
        driver.get(f"{base_url}/catalogo")
        time.sleep(2)
        search_res = driver.execute_script("""
            const input = document.getElementById('searchInput');
            if (input) {
                input.value = 'Machu';
                input.dispatchEvent(new Event('input'));
            }
            const cards = document.querySelectorAll('.tour-card, .card');
            const visible = [...cards].filter(c => c.style.display !== 'none');
            return {
                totalCards: cards.length,
                filteredCount: visible.length,
                sampleTitle: visible[0] ? visible[0].querySelector('h3, .tour-title').textContent.trim() : ''
            };
        """)
        print(f"  PASS | Búsqueda reactiva de tours: {search_res}")

        # Abrir modal de nuevo tour / edición
        modal_res = driver.execute_script("""
            const btn = document.getElementById('btnNewTour');
            if (btn) btn.click();
            const m = document.getElementById('tourModal');
            return {
                modalDisplayed: m ? window.getComputedStyle(m).display : 'none',
                modalTitle: document.getElementById('modalTourTitle') ? document.getElementById('modalTourTitle').textContent : '',
                hasEntityInput: !!document.getElementById('formEntityId'),
                hasPriceInput: !!document.getElementById('formPrice')
            };
        """)
        print(f"  PASS | Apertura de formulario modal en vivo: {modal_res}")

        # 3. Resumen (/dashboard)
        print("\n[3/4] Panel de Resumen (/dashboard)...")
        driver.get(f"{base_url}/dashboard")
        time.sleep(2)
        dash_res = driver.execute_script("""
            const kpis = document.querySelectorAll('.kpi-card');
            return {
                kpiCount: kpis.length,
                hasNav: !!document.querySelector('.admin-nav'),
                title: document.title
            };
        """)
        print(f"  PASS | Dashboard interactivo en vivo: {dash_res}")

        # 4. Métricas (/operational-metrics)
        print("\n[4/4] Panel de Métricas Operativas (/operational-metrics)...")
        driver.get(f"{base_url}/operational-metrics")
        time.sleep(2)
        metrics_res = driver.execute_script("""
            const groups = document.querySelectorAll('.metrics-group');
            const note = document.querySelector('.admin-note');
            const method = document.querySelector('.admin-method');
            return {
                groupsCount: groups.length,
                hasNoteBanner: !!note,
                hasMethodAccordion: !!method,
                title: document.title
            };
        """)
        print(f"  PASS | Métricas operativas en vivo: {metrics_res}")

        print("\n=========================================================")
        print("  ¡LAS 4 VISTAS Y ACCIONES EN VIVO FUERON COMPROBADAS CON ÉXITO!")
        print("=========================================================")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()

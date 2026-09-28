"""
Captura y auditoría responsiva visual de las cuatro vistas administrativas.
Verifica viewports efectivos de 320px, 390px, 600px y 1440px sin recortes ni artificios.
"""
import base64
import json
import os
import sys
import time
from pathlib import Path
from PIL import Image
import io

from selenium import webdriver
from selenium.webdriver.edge.options import Options

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

VIEWPORTS = [
    {"name": "mobile_320", "width": 320, "height": 640, "mobile": True},
    {"name": "mobile_390", "width": 390, "height": 844, "mobile": True},
    {"name": "tablet_600", "width": 600, "height": 960, "mobile": True},
    {"name": "desktop_1440", "width": 1440, "height": 900, "mobile": False},
]

PAGES = [
    {"path": "/handoffs", "label": "handoffs", "has_modal": False},
    {"path": "/handoffs?open=1", "label": "handoffs_open", "has_modal": False},
    {"path": "/catalogo", "label": "catalogo", "has_modal": False},
    {"path": "/catalogo?open=1", "label": "catalogo_open", "has_modal": True},
    {"path": "/dashboard", "label": "dashboard", "has_modal": False},
    {"path": "/operational-metrics", "label": "metrics", "has_modal": False},
]

DIAGNOSTIC_JS = """
return (() => {
    const docEl = document.documentElement;
    const body = document.body;
    const winWidth = window.innerWidth;
    const clientWidth = docEl.clientWidth;
    const scrollWidth = docEl.scrollWidth;
    const bodyScrollWidth = body.scrollWidth;

    // Detect any elements exceeding clientWidth
    const overflowing = [];
    const all = document.querySelectorAll('*');
    for (const el of all) {
        const r = el.getBoundingClientRect();
        // check elements with positive bounding width that exceed right bound
        if (r.width > 0 && r.right > winWidth + 1.5) {
            overflowing.push({
                tag: el.tagName.toLowerCase(),
                id: el.id || '',
                className: (el.className || '').toString().slice(0, 40),
                rect: { left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width) }
            });
            if (overflowing.length >= 10) break;
        }
    }

    // Measure key navigation and form elements if present
    const nav = document.querySelector('.admin-nav');
    const header = document.querySelector('header, .header');
    const modal = document.querySelector('.modal');
    const ticket = document.querySelector('.ticket[open]');
    const search = document.querySelector('.search-box, .admin-toolbar input');

    const measure = (el) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {
            left: Math.round(r.left),
            right: Math.round(r.right),
            width: Math.round(r.width),
            height: Math.round(r.height),
            top: Math.round(r.top)
        };
    };

    return {
        innerWidth: winWidth,
        clientWidth: clientWidth,
        scrollWidth: scrollWidth,
        bodyScrollWidth: bodyScrollWidth,
        hasOverflow: scrollWidth > clientWidth,
        overflowingElements: overflowing,
        nav: measure(nav),
        header: measure(header),
        modal: measure(modal),
        ticket: measure(ticket),
        search: measure(search)
    };
})()
"""

def run_responsive_audit():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    print("Iniciando WebDriver Edge headless...")
    driver = webdriver.Edge(options=options)
    
    audit_results = {}
    
    try:
        for vp in VIEWPORTS:
            vp_name = vp["name"]
            w = vp["width"]
            h = vp["height"]
            is_mob = vp["mobile"]
            audit_results[vp_name] = {}
            print(f"\n==========================================")
            print(f"Viewport: {vp_name} ({w}x{h}, mobile={is_mob})")
            print(f"==========================================")
            
            # Set top-level window large enough so Win32 min-window doesn't clip CDP
            driver.set_window_size(max(w, 1024), max(h, 900))
            
            # Force CDP device metrics override
            driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'width': w,
                'height': h,
                'deviceScaleFactor': 1,
                'mobile': is_mob
            })
            
            for page in PAGES:
                path = page["path"]
                label = page["label"]
                url = f"http://127.0.0.1:8035{path}"
                
                driver.get(url)
                time.sleep(0.7)  # allow dynamic templates / setTimeouts to execute
                
                # If page has modal or open form, ensure it's displayed
                if label == "catalogo_open":
                    driver.execute_script("if(window.openModal) openModal('tourModal');")
                    time.sleep(0.3)
                elif label == "handoffs_open":
                    driver.execute_script("const t=document.querySelector('.ticket'); if(t) t.open=true;")
                    time.sleep(0.3)
                
                # Run layout diagnostics
                diag = driver.execute_script(DIAGNOSTIC_JS)
                
                # Take screenshot
                # For modal open, take viewport screenshot so the modal overlay is captured faithfully
                # For standard pages, take full page capture
                if page["has_modal"]:
                    screenshot_cdp = driver.execute_cdp_cmd('Page.captureScreenshot', {
                        'captureBeyondViewport': False,
                        'fromSurface': True
                    })
                else:
                    screenshot_cdp = driver.execute_cdp_cmd('Page.captureScreenshot', {
                        'captureBeyondViewport': True,
                        'fromSurface': True
                    })
                
                png_bytes = base64.b64decode(screenshot_cdp['data'])
                img = Image.open(io.BytesIO(png_bytes))
                
                filename = f"view-{label}-{vp_name}.png"
                filepath = LOGS / filename
                filepath.write_bytes(png_bytes)
                
                diag["screenshot_file"] = str(filename)
                diag["screenshot_size"] = img.size
                audit_results[vp_name][label] = diag
                
                status_str = "OK (sin overflow)" if not diag["hasOverflow"] else f"ALERTA (overflow: {diag['scrollWidth']} > {diag['clientWidth']})"
                print(f"[{vp_name}] {label:15} | innerWidth={diag['innerWidth']} | clientW={diag['clientWidth']} | scrollW={diag['scrollWidth']} | imgSize={img.size} | {status_str}")
                
                if diag["overflowingElements"]:
                    print(f"    -> Elementos desbordantes ({len(diag['overflowingElements'])}):")
                    for el in diag["overflowingElements"]:
                        print(f"       <{el['tag']} class='{el['className']}'> rect: {el['rect']}")
                        
                if diag["modal"]:
                    print(f"    -> Modal bounds: {diag['modal']}")
                if diag["ticket"]:
                    print(f"    -> Ticket abierto bounds: {diag['ticket']}")
                    
        # Write json summary
        json_report = LOGS / "responsive_audit_20260928.json"
        json_report.write_text(json.dumps(audit_results, indent=2), encoding="utf-8")
        print(f"\nAuditoría completa guardada en {json_report}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    run_responsive_audit()

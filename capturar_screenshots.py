"""
Captura screenshots de todas las pantallas del sistema PrestaFácil
usando Playwright (headless Chromium).
"""
import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://financiera.up.railway.app"
USERNAME = "coco"
PASSWORD = "123"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")


def capturar_todas_las_pantallas():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---------- MOBILE (iPhone 12) ----------
        mobile_ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
        )
        mob = mobile_ctx.new_page()
        mob.set_default_timeout(30000)

        # ---------- DESKTOP ----------
        desk_ctx = browser.new_context(
            viewport={"width": 1366, "height": 900},
            device_scale_factor=1,
        )
        desk = desk_ctx.new_page()
        desk.set_default_timeout(30000)

        # ========== LOGIN ==========
        print("[1/14] Login...")
        mob.goto(f"{BASE_URL}/login/")
        mob.wait_for_load_state("networkidle")
        time.sleep(2)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "01_login_mobile.png"))

        # Login en mobile
        mob.fill('#username', USERNAME)
        mob.fill('#password', PASSWORD)
        mob.click('button[type="submit"]')
        mob.wait_for_load_state("networkidle")
        time.sleep(2)

        # Login en desktop
        desk.goto(f"{BASE_URL}/login/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "01_login_desktop.png"))
        desk.fill('#username', USERNAME)
        desk.fill('#password', PASSWORD)
        desk.click('button[type="submit"]')
        desk.wait_for_load_state("networkidle")
        time.sleep(2)

        # ========== DASHBOARD ==========
        print("[2/14] Dashboard...")
        mob.goto(f"{BASE_URL}/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "02_dashboard_mobile.png"), full_page=True)

        desk.goto(f"{BASE_URL}/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "02_dashboard_desktop.png"), full_page=True)

        # ========== CLIENTES - LISTA ==========
        print("[3/14] Clientes lista...")
        mob.goto(f"{BASE_URL}/clientes/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "03_clientes_lista_mobile.png"), full_page=True)

        desk.goto(f"{BASE_URL}/clientes/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "03_clientes_lista_desktop.png"), full_page=True)

        # ========== CLIENTES - NUEVO ==========
        print("[4/14] Cliente nuevo formulario...")
        mob.goto(f"{BASE_URL}/clientes/nuevo/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "04_cliente_nuevo_mobile.png"), full_page=True)

        # ========== CLIENTES - DETALLE (primer cliente) ==========
        print("[5/14] Cliente detalle...")
        mob.goto(f"{BASE_URL}/clientes/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        # Intentar clic en primer cliente
        try:
            first_link = mob.query_selector('a[href*="/clientes/"][href$="/"]')
            if first_link:
                href = first_link.get_attribute("href")
                if href and "/clientes/" in href and "/nuevo" not in href:
                    mob.goto(f"{BASE_URL}{href}")
                    mob.wait_for_load_state("networkidle")
                    time.sleep(1)
                    mob.screenshot(path=os.path.join(OUTPUT_DIR, "05_cliente_detalle_mobile.png"), full_page=True)
        except Exception as e:
            print(f"   Skipping cliente detalle: {e}")

        # ========== PRESTAMOS - LISTA ==========
        print("[6/14] Prestamos lista...")
        mob.goto(f"{BASE_URL}/prestamos/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "06_prestamos_lista_mobile.png"), full_page=True)

        desk.goto(f"{BASE_URL}/prestamos/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "06_prestamos_lista_desktop.png"), full_page=True)

        # ========== PRESTAMOS - NUEVO ==========
        print("[7/14] Prestamo nuevo formulario...")
        mob.goto(f"{BASE_URL}/prestamos/nuevo/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "07_prestamo_nuevo_mobile.png"), full_page=True)

        # ========== PRESTAMOS - DETALLE (primer prestamo) ==========
        print("[8/14] Prestamo detalle...")
        try:
            mob.goto(f"{BASE_URL}/prestamos/")
            mob.wait_for_load_state("networkidle")
            first_prest = mob.query_selector('a[href*="/prestamos/"][href$="/"]')
            if first_prest:
                href = first_prest.get_attribute("href")
                if href and "/prestamos/" in href and "/nuevo" not in href:
                    mob.goto(f"{BASE_URL}{href}")
                    mob.wait_for_load_state("networkidle")
                    time.sleep(1)
                    mob.screenshot(path=os.path.join(OUTPUT_DIR, "08_prestamo_detalle_mobile.png"), full_page=True)

                    desk.goto(f"{BASE_URL}{href}")
                    desk.wait_for_load_state("networkidle")
                    time.sleep(1)
                    desk.screenshot(path=os.path.join(OUTPUT_DIR, "08_prestamo_detalle_desktop.png"), full_page=True)
        except Exception as e:
            print(f"   Skipping prestamo detalle: {e}")

        # ========== COBROS ==========
        print("[9/14] Cobros del dia...")
        mob.goto(f"{BASE_URL}/cobros/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "09_cobros_mobile.png"), full_page=True)

        desk.goto(f"{BASE_URL}/cobros/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "09_cobros_desktop.png"), full_page=True)

        # ========== CIERRE DE CAJA ==========
        print("[10/14] Cierre de caja...")
        mob.goto(f"{BASE_URL}/cierre-caja/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "10_cierre_caja_mobile.png"), full_page=True)

        desk.goto(f"{BASE_URL}/cierre-caja/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "10_cierre_caja_desktop.png"), full_page=True)

        # ========== PLANILLA IMPRESION ==========
        print("[11/14] Planilla impresion...")
        mob.goto(f"{BASE_URL}/planilla/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "11_planilla_mobile.png"), full_page=True)

        desk.goto(f"{BASE_URL}/planilla/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "11_planilla_desktop.png"), full_page=True)

        # ========== REPORTES ==========
        print("[12/14] Reportes...")
        mob.goto(f"{BASE_URL}/reportes/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "12_reportes_mobile.png"), full_page=True)

        desk.goto(f"{BASE_URL}/reportes/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "12_reportes_desktop.png"), full_page=True)

        # ========== NOTIFICACIONES ==========
        print("[13/14] Notificaciones...")
        mob.goto(f"{BASE_URL}/notificaciones/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "13_notificaciones_mobile.png"), full_page=True)

        # ========== USUARIOS (admin) ==========
        print("[14/14] Usuarios...")
        mob.goto(f"{BASE_URL}/usuarios/")
        mob.wait_for_load_state("networkidle")
        time.sleep(1)
        mob.screenshot(path=os.path.join(OUTPUT_DIR, "14_usuarios_mobile.png"), full_page=True)

        desk.goto(f"{BASE_URL}/usuarios/")
        desk.wait_for_load_state("networkidle")
        time.sleep(1)
        desk.screenshot(path=os.path.join(OUTPUT_DIR, "14_usuarios_desktop.png"), full_page=True)

        # Cleanup
        mobile_ctx.close()
        desk_ctx.close()
        browser.close()

    # Resumen
    archivos = sorted(os.listdir(OUTPUT_DIR))
    print(f"\n{'='*60}")
    print(f"  {len(archivos)} screenshots capturados en: {OUTPUT_DIR}")
    for a in archivos:
        size = os.path.getsize(os.path.join(OUTPUT_DIR, a)) / 1024
        print(f"    {a}  ({size:.0f} KB)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    capturar_todas_las_pantallas()

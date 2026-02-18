"""Capturar screenshots faltantes: detalle cliente y detalle préstamo"""
import asyncio
import re
from playwright.async_api import async_playwright

BASE = "https://financiera.up.railway.app"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Mobile context
        mobile = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
        )
        mob = await mobile.new_page()

        # Desktop context  
        desktop = await browser.new_context(
            viewport={"width": 1366, "height": 900},
            device_scale_factor=1,
        )
        desk = await desktop.new_page()

        # Login both
        for page, label in [(mob, "mobile"), (desk, "desktop")]:
            await page.goto(f"{BASE}/login/")
            await page.fill("#username", "coco")
            await page.fill("#password", "123")
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            print(f"{label} logged in: {page.url}")

        # --- Client detail ---
        await mob.goto(f"{BASE}/clientes/")
        await mob.wait_for_load_state("networkidle")
        all_hrefs = await mob.eval_on_selector_all("a", "els => els.map(e => e.href)")
        client_urls = [h for h in all_hrefs if re.search(r"/clientes/\d+/$", h)]
        print(f"Client detail URLs found: {client_urls[:5]}")

        if client_urls:
            url = client_urls[0]
            print(f"-> Navigating to {url}")
            await mob.goto(url)
            await mob.wait_for_load_state("networkidle")
            await mob.screenshot(path="screenshots/05_cliente_detalle_mobile.png", full_page=True)
            print("  Captured: 05_cliente_detalle_mobile.png")

        # --- Loan detail ---
        await mob.goto(f"{BASE}/prestamos/")
        await mob.wait_for_load_state("networkidle")
        all_hrefs = await mob.eval_on_selector_all("a", "els => els.map(e => e.href)")
        loan_urls = [h for h in all_hrefs if re.search(r"/prestamos/\d+/$", h)]
        print(f"Loan detail URLs found: {loan_urls[:5]}")

        if loan_urls:
            url = loan_urls[0]
            print(f"-> Navigating to {url}")

            await mob.goto(url)
            await mob.wait_for_load_state("networkidle")
            await mob.screenshot(path="screenshots/08_prestamo_detalle_mobile.png", full_page=True)
            print("  Captured: 08_prestamo_detalle_mobile.png")

            await desk.goto(url)
            await desk.wait_for_load_state("networkidle")
            await desk.screenshot(path="screenshots/08_prestamo_detalle_desktop.png", full_page=True)
            print("  Captured: 08_prestamo_detalle_desktop.png")

        await browser.close()
        print("Done!")

asyncio.run(main())

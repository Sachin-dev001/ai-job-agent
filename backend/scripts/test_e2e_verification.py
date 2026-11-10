import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def verify():
    url = "http://127.0.0.1:8000"
    print(f"Testing e2e against {url}...", flush=True)

    console_errors = []

    async with async_playwright() as p:
        # Launch using installed Chrome channel
        browser = await p.chromium.launch(headless=True, channel="chrome")
        
        # Test 1: Desktop Viewport
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("Navigating to homepage...", flush=True)
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(1000)
        title = await page.title()
        print(f"Page loaded: title='{title}'", flush=True)

        # Check for horizontal overflow
        scroll_w = await page.evaluate("() => document.documentElement.scrollWidth")
        inner_w = await page.evaluate("() => window.innerWidth")
        print(f"Desktop 1280px overflow check: scrollWidth={scroll_w}, innerWidth={inner_w} (Diff: {scroll_w - inner_w})", flush=True)
        assert scroll_w <= inner_w, "Desktop has horizontal scroll overflow!"

        # Test Cloud Config Modal open, close with ESC
        print("Testing Cloud Config modal open and ESC close...", flush=True)
        await page.click("#backendStatusPill")
        await page.wait_for_timeout(400)
        is_visible = await page.is_visible("#cloudConfigModal:not(.hidden)")
        print(f"Cloud config modal visible: {is_visible}", flush=True)
        assert is_visible, "Cloud config modal did not open"

        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
        is_hidden = await page.evaluate("() => document.getElementById('cloudConfigModal').classList.contains('hidden')")
        print(f"Cloud config modal hidden after ESC: {is_hidden}", flush=True)
        assert is_hidden, "Cloud config modal did not close on ESC"

        # Test Platform Selector Modal open and backdrop click
        print("Testing Platform Selector modal open and backdrop click close...", flush=True)
        await page.evaluate("() => openPlatformSelector('Data Analyst')")
        await page.wait_for_timeout(400)
        plat_visible = await page.is_visible("#platformSelectorModal:not(.hidden)")
        print(f"Platform modal visible: {plat_visible}", flush=True)
        assert plat_visible, "Platform modal did not open"

        # Click backdrop (top-left outside modal card)
        await page.click("#platformSelectorModal", position={"x": 10, "y": 10})
        await page.wait_for_timeout(400)
        plat_hidden = await page.evaluate("() => document.getElementById('platformSelectorModal').classList.contains('hidden')")
        print(f"Platform modal hidden after backdrop click: {plat_hidden}", flush=True)
        assert plat_hidden, "Platform modal did not close on backdrop click"

        # Test Memory Vault Modal open and close with ESC
        print("Testing Memory Vault modal open and ESC close...", flush=True)
        await page.evaluate("() => toggleVaultModal(true)")
        await page.wait_for_timeout(400)
        vault_visible = await page.is_visible("#memoryVaultModal:not(.hidden)")
        print(f"Vault modal visible: {vault_visible}", flush=True)
        assert vault_visible, "Vault modal did not open"

        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
        vault_hidden = await page.evaluate("() => document.getElementById('memoryVaultModal').classList.contains('hidden')")
        print(f"Vault modal hidden after ESC: {vault_hidden}", flush=True)
        assert vault_hidden, "Vault modal did not close on ESC"

        # Test Mobile Viewport (iPhone 14 - 390px)
        print("\nTesting mobile viewport 390px (iPhone 14)...", flush=True)
        mobile_page = await browser.new_page(viewport={"width": 390, "height": 844})
        await mobile_page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await mobile_page.wait_for_timeout(1000)

        m_scroll_w = await mobile_page.evaluate("() => document.documentElement.scrollWidth")
        m_inner_w = await mobile_page.evaluate("() => window.innerWidth")
        print(f"Mobile 390px overflow check: scrollWidth={m_scroll_w}, innerWidth={m_inner_w} (Diff: {m_scroll_w - m_inner_w})", flush=True)
        assert m_scroll_w <= m_inner_w, "Mobile viewport has horizontal scroll overflow!"

        # Test mobile hamburger drawer toggle
        print("Testing mobile hamburger drawer...", flush=True)
        await mobile_page.click("button[aria-label='Toggle Mobile Navigation']")
        await mobile_page.wait_for_timeout(400)
        drawer_visible = await mobile_page.is_visible("#mobileNavMenu:not(.hidden)")
        print(f"Mobile drawer open: {drawer_visible}", flush=True)
        assert drawer_visible, "Mobile drawer did not open"

        await mobile_page.keyboard.press("Escape")
        await mobile_page.wait_for_timeout(400)
        drawer_hidden = await mobile_page.evaluate("() => document.getElementById('mobileNavMenu').classList.contains('hidden')")
        print(f"Mobile drawer closed on ESC: {drawer_hidden}", flush=True)
        assert drawer_hidden, "Mobile drawer did not close on ESC"

        await browser.close()

    print("\nConsole errors during test:", flush=True)
    if console_errors:
        for err in console_errors:
            print("  ERROR:", err, flush=True)
    else:
        print("  Zero console errors detected!", flush=True)

    print("\nALL E2E CHECKS PASSED!", flush=True)

if __name__ == "__main__":
    asyncio.run(verify())

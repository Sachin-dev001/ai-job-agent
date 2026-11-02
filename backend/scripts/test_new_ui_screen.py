import asyncio
import os
from playwright.async_api import async_playwright

PROOF_DIR = r"D:\ai-job-agent\backend\proofs"

async def test_new_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chrome")
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navigating to http://localhost:8000...")
        await page.goto("http://localhost:8000", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # 1. Screenshot Cover Page / Hero
        await page.screenshot(path=os.path.join(PROOF_DIR, "cover_page_hero.png"))
        print("Captured cover_page_hero.png")

        # 2. Trigger resume analysis
        analyze_btn = page.locator("#analyzeBtn")
        if await analyze_btn.is_visible():
            await analyze_btn.click()
            await page.wait_for_timeout(3000)

        # 3. Switch to Wellfound
        await page.click("#tabWellfound")
        await page.wait_for_timeout(1500)

        # 4. Scroll to console and screenshot
        console_el = page.locator("#console")
        if await console_el.is_visible():
            await console_el.scroll_into_view_if_needed()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=os.path.join(PROOF_DIR, "console_workspace.png"))
            print("Captured console_workspace.png")

        # 5. Open Memory Vault modal
        vault_btn = page.locator("#openVaultBtn")
        if await vault_btn.is_visible():
            await vault_btn.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=os.path.join(PROOF_DIR, "new_ui_vault_modal.png"))
            print("Captured new_ui_vault_modal.png")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_new_ui())

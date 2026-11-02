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

        # Trigger resume analysis
        analyze_btn = page.locator("#analyzeBtn")
        if await analyze_btn.is_visible():
            await analyze_btn.click()
            await page.wait_for_timeout(3000)

        # Switch to Wellfound
        await page.click("#tabWellfound")
        await page.wait_for_timeout(1500)

        # Screenshot Wellfound view
        await page.screenshot(path=os.path.join(PROOF_DIR, "new_ui_wellfound_view.png"))
        print("Captured new_ui_wellfound_view.png")

        # Open Memory Vault modal
        vault_btn = page.locator("button:has-text('Memory Vault')").first
        if await vault_btn.is_visible():
            await vault_btn.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=os.path.join(PROOF_DIR, "new_ui_vault_modal.png"))
            print("Captured new_ui_vault_modal.png")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_new_ui())

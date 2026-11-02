import asyncio
import os
from playwright.async_api import async_playwright

PROOF_DIR = r"D:\ai-job-agent\backend\proofs"

async def test_make_features():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chrome")
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navigating to http://localhost:8000...")
        await page.goto("http://localhost:8000", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # 1. Screenshot top navbar and hero (verifying Antigravity is removed and AutoApply is present)
        await page.screenshot(path=os.path.join(PROOF_DIR, "hero_autoapply_no_antigravity.png"))
        print("Captured hero_autoapply_no_antigravity.png")

        # 2. Scroll to Scenario Section and click Run Simulation
        scenario_sec = page.locator("#scenarioSection")
        await scenario_sec.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)

        sim_btn = page.locator("button:has-text('Run Simulation')").first
        if await sim_btn.is_visible():
            await sim_btn.click()
            await page.wait_for_timeout(2500) # wait while simulation runs across nodes

        await page.screenshot(path=os.path.join(PROOF_DIR, "make_scenario_canvas_simulating.png"))
        print("Captured make_scenario_canvas_simulating.png")

        # 3. Scroll to Integrations Ribbon & hover over an app bubble (Telegram)
        integrations_sec = page.locator("#integrationsRibbon")
        await integrations_sec.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)

        # Hover over an integration bubble with force=True (since it has floating animation)
        bubble = page.locator("#integrationsRibbon .group").nth(3)
        if await bubble.is_visible():
            await bubble.hover(force=True)
            await page.wait_for_timeout(500)

        await page.screenshot(path=os.path.join(PROOF_DIR, "make_integrations_ribbon.png"))
        print("Captured make_integrations_ribbon.png")

        # 4. Scroll to Video Showcase & ROI section
        roi_sec = page.locator("section:has-text('Builder · Build, test, debug and run in one visual environment.')").first
        if await roi_sec.is_visible():
            await roi_sec.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            await page.screenshot(path=os.path.join(PROOF_DIR, "make_video_showcase_roi.png"))
            print("Captured make_video_showcase_roi.png")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_make_features())

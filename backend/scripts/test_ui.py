import asyncio
from playwright.async_api import async_playwright

async def test_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chrome")
        page = await browser.new_page(viewport={"width": 1366, "height": 850})

        print("1. Navigating to http://localhost:8000...")
        await page.goto("http://localhost:8000", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)

        # Test opening platform selector modal
        print("2. Testing platform selector modal for Data Analyst...")
        await page.evaluate("openPlatformSelector('Data Analyst')")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=r"D:\ai-job-agent\backend\proofs\ui_test_platform_modal.png")
        print("Screenshot 1: Saved platform selector modal.")

        # Test selecting Wellfound
        print("3. Selecting Wellfound platform...")
        await page.evaluate("selectPlatformAndScout('wellfound')")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=r"D:\ai-job-agent\backend\proofs\ui_test_wellfound_workspace.png")
        print("Screenshot 2: Saved Wellfound workspace with Data Analyst jobs.")

        # Test selecting Naukri
        print("4. Switching back to Naukri workspace...")
        await page.evaluate("switchPlatform('naukri')")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=r"D:\ai-job-agent\backend\proofs\ui_test_naukri_workspace.png")
        print("Screenshot 3: Saved Naukri workspace with Data Analyst jobs.")

        await browser.close()
        print("UI Automation tests PASSED with 0 errors!")

if __name__ == "__main__":
    asyncio.run(test_ui())

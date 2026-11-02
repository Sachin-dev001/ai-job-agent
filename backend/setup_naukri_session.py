import asyncio
import os
from playwright.async_api import async_playwright

async def launch_auth_browser():
    user_data_dir = r"D:\ai-job-agent\backend\browser_profile"
    os.makedirs(user_data_dir, exist_ok=True)

    print("[*] Launching Chrome authentication window...")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ],
            no_viewport=True
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.naukri.com/nlogin/login")

        print("[*] Chrome window open. Please log in.")
        # Wait until user finishes login and closes the Chrome window
        try:
            while len(context.pages) > 0:
                await asyncio.sleep(1)
        except Exception:
            pass

        print("[*] Browser session captured successfully!")

if __name__ == "__main__":
    asyncio.run(launch_auth_browser())

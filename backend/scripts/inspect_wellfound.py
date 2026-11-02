import asyncio
import json
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

COOKIE_FILE = r"D:\ai-job-agent\backend\cookies\wellfound_cookies.json"
PROOF_DIR = r"D:\ai-job-agent\backend\proofs"
os.makedirs(PROOF_DIR, exist_ok=True)

EMAIL = os.getenv("WELLFOUND_EMAIL", "sachin.sharma.coder@gmail.com")
PASSWORD = os.getenv("WELLFOUND_PASSWORD", "")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        print("[Wellfound] Navigating to https://wellfound.com/login...")
        await page.goto("https://wellfound.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Inspect inputs
        inputs = await page.locator("input").all()
        for idx, inp in enumerate(inputs):
            itype = await inp.get_attribute("type")
            iname = await inp.get_attribute("name")
            iid = await inp.get_attribute("id")
            ipl = await inp.get_attribute("placeholder")
            print(f"[{idx}] Input: type={itype}, name={iname}, id={iid}, placeholder={ipl}")

        # Look for email and password fields
        email_input = page.locator("input[type='email'], input[name='email'], input#user_email, input[placeholder*='email' i]").first
        password_input = page.locator("input[type='password'], input[name='password'], input#user_password").first

        if await email_input.is_visible() and await password_input.is_visible():
            print("[Wellfound] Found email and password inputs! Filling credentials...")
            await email_input.fill(EMAIL)
            await page.wait_for_timeout(500)
            await password_input.fill(PASSWORD)
            await page.wait_for_timeout(500)

            # Look for submit button
            submit_btn = page.locator("input[type='submit'], button[type='submit'], button:has-text('Log in'), button:has-text('Sign In')").first
            if await submit_btn.is_visible():
                btn_txt = await submit_btn.text_content() or await submit_btn.get_attribute("value")
                print(f"[Wellfound] Clicking submit button: '{btn_txt}'...")
                await submit_btn.click()
                await page.wait_for_timeout(5000)
            else:
                print("[Wellfound] Submit button not found, pressing Enter on password field...")
                await password_input.press("Enter")
                await page.wait_for_timeout(5000)

            # Check post-login URL and state
            curr_url = page.url
            curr_title = await page.title()
            print(f"[Wellfound] Post-login URL: {curr_url}")
            print(f"[Wellfound] Post-login Title: {curr_title}")

            await page.screenshot(path=os.path.join(PROOF_DIR, "wellfound_post_login.png"))

            # Save cookies
            cookies = await context.cookies()
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            print(f"[Wellfound] Saved {len(cookies)} cookies to {COOKIE_FILE}")

            # Check if login succeeded (URL changed away from /login or contains jobs/overview/etc)
            if "login" not in curr_url.lower():
                print("[Wellfound] SUCCESS! Successfully logged in to Wellfound!")
            else:
                print("[Wellfound] Still on login page. Check screenshot wellfound_post_login.png for any captcha/MFA/error.")

        else:
            print("[Wellfound] Email or password field not visible directly. Taking screenshot...")
            await page.screenshot(path=os.path.join(PROOF_DIR, "wellfound_login_failed.png"))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

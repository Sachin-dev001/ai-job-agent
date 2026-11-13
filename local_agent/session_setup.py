import asyncio
import sys
from local_agent.browser_manager import LocalBrowserManager

async def run_session_setup():
    print("\n" + "=" * 65)
    print(" 🚀 PERSONAL LOCAL JOB AGENT - BROWSER SESSION SETUP")
    print("=" * 65)
    print("This will open a dedicated Google Chrome window.")
    print("1. Log into your Naukri.com account.")
    print("2. Log into your Wellfound.com account.")
    print("3. Your login session will be permanently saved to your disk.")
    print("=" * 65 + "\n")

    # Launch headed browser so user can type credentials or use Google Login
    async with LocalBrowserManager(headless=False) as bm:
        page = await bm.get_page()
        
        print("[*] Navigating to Naukri login page...")
        try:
            await page.goto("https://www.naukri.com/nlogin/login", timeout=30000)
        except Exception as e:
            print(f"[!] Warning opening Naukri: {e}")

        # Open second tab for Wellfound
        page2 = await bm.new_stealth_page()
        print("[*] Navigating to Wellfound login page...")
        try:
            await page2.goto("https://wellfound.com/login", timeout=30000)
        except Exception as e:
            print(f"[!] Warning opening Wellfound: {e}")

        print("\n" + "👉 " * 15)
        print("ACTION REQUIRED:")
        print("Please log into Naukri and Wellfound in the opened Chrome window.")
        print("Once you are logged in on both tabs, come back here and press ENTER.")
        print("👉 " * 15 + "\n")

        # Wait for user input or window close
        try:
            input("[Press ENTER when you have finished logging in] > ")
        except (KeyboardInterrupt, EOFError):
            pass

        # Check authentication status
        cookies = await bm.context.cookies()
        naukri_cookies = [c['name'] for c in cookies if 'naukri' in c.get('domain', '')]
        wellfound_cookies = [c['name'] for c in cookies if 'wellfound' in c.get('domain', '') or 'angel' in c.get('domain', '')]

        print("\n" + "=" * 65)
        print(" SESSION AUDIT RESULTS:")
        print(f" - Naukri Cookies Saved:    {len(naukri_cookies)} ({'✅ Logged In' if len(naukri_cookies) > 5 else '⚠️ Verify Login'})")
        print(f" - Wellfound Cookies Saved: {len(wellfound_cookies)} ({'✅ Logged In' if len(wellfound_cookies) > 2 else '⚠️ Verify Login'})")
        print("=" * 65)
        print("🎉 Browser session saved permanently! You are ready to auto-apply.\n")

if __name__ == "__main__":
    asyncio.run(run_session_setup())

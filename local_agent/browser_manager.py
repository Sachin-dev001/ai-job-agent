import os
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_stealth import Stealth
from local_agent.config import BROWSER_PROFILE_DIR, HEADLESS

class LocalBrowserManager:
    def __init__(self, headless: bool = HEADLESS):
        self.headless = headless
        self.playwright = None
        self.context: BrowserContext = None
        self.stealth = Stealth()

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
        ]
        if self.headless:
            args.append("--headless=new")
        else:
            args.append("--start-maximized")
        
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

        # Prefer installed Google Chrome channel to ensure authentic consumer TLS and OS signature
        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_PROFILE_DIR),
                channel="chrome",
                headless=self.headless,
                args=args,
                user_agent=user_agent,
                viewport={"width": 1366, "height": 768} if self.headless else None,
                no_viewport=not self.headless
            )
        except Exception as e:
            print(f"[BrowserManager] Installed Chrome channel notice ({e}), launching bundled Chromium...")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_PROFILE_DIR),
                headless=self.headless,
                args=args,
                user_agent=user_agent,
                viewport={"width": 1366, "height": 768}
            )

        await self.context.add_init_script("delete Object.getPrototypeOf(navigator).webdriver; window.navigator.chrome = { runtime: {} };")

        # Auto-load saved session cookies into context for seamless authenticated actions
        cookie_files = [
            Path(__file__).resolve().parent.parent / "backend" / "cookies" / "fresh_naukri_cookies.json",
            Path(__file__).resolve().parent.parent / "backend" / "cookies" / "naukri_cookies.json",
            Path(__file__).resolve().parent.parent / "backend" / "cookies" / "wellfound_cookies.json",
        ]
        all_cookies = []
        for cf in cookie_files:
            if cf.exists():
                try:
                    import json
                    with open(cf, "r", encoding="utf-8") as f:
                        raw_c = json.load(f)
                    if isinstance(raw_c, list):
                        for c in raw_c:
                            domain = c.get("domain", "")
                            if domain and not domain.startswith("."):
                                domain = "." + domain
                            pc = {
                                "name": c.get("name"),
                                "value": c.get("value"),
                                "domain": domain,
                                "path": c.get("path", "/"),
                                "httpOnly": c.get("httpOnly", False),
                                "secure": c.get("secure", False),
                            }
                            if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
                                pc["sameSite"] = c["sameSite"]
                            all_cookies.append(pc)
                except Exception:
                    pass
        if all_cookies:
            try:
                await self.context.add_cookies(all_cookies)
                print(f"[BrowserManager] Auto-loaded {len(all_cookies)} authenticated session cookies.")
            except Exception as ce:
                print(f"[BrowserManager] Notice loading cookies: {ce}")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass

    async def get_page(self) -> Page:
        page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        try:
            await self.stealth.apply_stealth_async(page)
        except Exception:
            pass
        return page

    async def new_stealth_page(self) -> Page:
        page = await self.context.new_page()
        try:
            await self.stealth.apply_stealth_async(page)
        except Exception:
            pass
        return page

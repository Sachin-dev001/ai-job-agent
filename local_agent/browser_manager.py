import os
import asyncio
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
            "--start-maximized"
        ]
        
        # Prefer installed Google Chrome channel to ensure authentic consumer TLS and OS signature
        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_PROFILE_DIR),
                channel="chrome",
                headless=self.headless,
                args=args,
                no_viewport=True
            )
        except Exception as e:
            print(f"[BrowserManager] Installed Chrome channel notice ({e}), launching bundled Chromium...")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_PROFILE_DIR),
                headless=self.headless,
                args=args,
                viewport={"width": 1366, "height": 768}
            )

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

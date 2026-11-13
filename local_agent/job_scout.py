import asyncio
import urllib.parse
from typing import List, Dict
from playwright.async_api import Page

class LocalJobScout:
    def __init__(self, page: Page):
        self.page = page

    async def scout_naukri(self, keyword: str = "Python Developer", location: str = "Bengaluru", limit: int = 5) -> List[Dict]:
        encoded_kw = urllib.parse.quote(keyword.lower().replace(" ", "-"))
        search_url = f"https://www.naukri.com/{encoded_kw}-jobs"
        if location:
            search_url += f"-in-{location.lower()}"

        print(f"\n[Job Scout] 🔍 Searching Naukri for '{keyword}'...")
        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"[Job Scout] Navigation warning: {e}")

        jobs = []
        try:
            # Locate job tuples
            tuples = await self.page.locator(".srp-jobtuple-wrapper, article.jobTuple, div[data-job-id]").all()
            for t in tuples[:limit]:
                try:
                    title_el = t.locator("a.title, .title").first
                    title = await title_el.text_content() if await title_el.count() > 0 else "Software Engineer"
                    href = await title_el.get_attribute("href") if await title_el.count() > 0 else ""

                    comp_el = t.locator("a.comp-name, .comp-name").first
                    comp = await comp_el.text_content() if await comp_el.count() > 0 else "Hiring Company"

                    if href and ("naukri.com" in href or href.startswith("/")):
                        full_url = href if href.startswith("http") else f"https://www.naukri.com{href}"
                        jobs.append({
                            "platform": "naukri",
                            "title": title.strip(),
                            "company": comp.strip(),
                            "url": full_url
                        })
                except Exception:
                    pass
        except Exception as e:
            print(f"[Job Scout] Error extracting Naukri jobs: {e}")

        print(f"[Job Scout] Found {len(jobs)} matching jobs on Naukri.")
        return jobs

    async def scout_wellfound(self, keyword: str = "AI Engineer", limit: int = 5) -> List[Dict]:
        search_url = "https://wellfound.com/jobs"
        print(f"\n[Job Scout] 🔍 Searching Wellfound for '{keyword}'...")
        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"[Job Scout] Navigation warning: {e}")

        jobs = []
        try:
            links = await self.page.locator("a[href*='/jobs/']").all()
            seen_urls = set()
            for a in links:
                try:
                    href = await a.get_attribute("href")
                    if href and href not in seen_urls:
                        seen_urls.add(href)
                        title = await a.text_content()
                        full_url = href if href.startswith("http") else f"https://wellfound.com{href}"
                        jobs.append({
                            "platform": "wellfound",
                            "title": (title or "Startup Engineer").strip(),
                            "company": "Startup",
                            "url": full_url
                        })
                        if len(jobs) >= limit: break
                except Exception:
                    pass
        except Exception as e:
            print(f"[Job Scout] Error extracting Wellfound jobs: {e}")

        print(f"[Job Scout] Found {len(jobs)} jobs on Wellfound.")
        return jobs

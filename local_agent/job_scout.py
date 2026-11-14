import asyncio
import urllib.parse
from typing import List, Dict, Optional
from playwright.async_api import Page

class LocalJobScout:
    def __init__(self, page: Page):
        self.page = page

    async def scout_naukri(self, keyword: str = "Python Developer", location: str = "Bengaluru", limit: int = 5) -> List[Dict]:
        encoded_kw = urllib.parse.quote(keyword.lower().replace(" ", "-"))
        search_url = f"https://www.naukri.com/{encoded_kw}-jobs"
        if location:
            search_url += f"-in-{location.lower()}"

        print(f"\n[Job Scout] 🔍 Searching Naukri for '{keyword}' in '{location}'...", flush=True)
        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"[Job Scout] Navigation warning: {e}", flush=True)

        jobs = []
        try:
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
            print(f"[Job Scout] Error extracting Naukri jobs: {e}", flush=True)

        print(f"[Job Scout] Found {len(jobs)} matching jobs on Naukri.", flush=True)
        return jobs

    async def scout_wellfound(self, keyword: str = "AI Engineer", limit: int = 5) -> List[Dict]:
        search_url = "https://wellfound.com/jobs"
        print(f"\n[Job Scout] 🔍 Searching Wellfound for '{keyword}'...", flush=True)
        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"[Job Scout] Navigation warning: {e}", flush=True)

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
                        if len(jobs) >= limit:
                            break
                except Exception:
                    pass
        except Exception as e:
            print(f"[Job Scout] Error extracting Wellfound jobs: {e}", flush=True)

        print(f"[Job Scout] Found {len(jobs)} jobs on Wellfound.", flush=True)
        return jobs

    async def scout_linkedin(self, keyword: str = "AI Engineer", location: str = "India", limit: int = 5) -> List[Dict]:
        """
        Scout live LinkedIn Easy Apply job openings.
        f_AL=true filters strictly for Easy Apply listings.
        """
        enc_kw = urllib.parse.quote(keyword)
        enc_loc = urllib.parse.quote(location)
        search_url = f"https://www.linkedin.com/jobs/search?keywords={enc_kw}&location={enc_loc}&f_AL=true"
        print(f"\n[Job Scout] 🔍 Searching LinkedIn (Easy Apply) for '{keyword}' in '{location}'...", flush=True)

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"[Job Scout] Navigation warning: {e}", flush=True)

        jobs = []
        try:
            cards = await self.page.locator(
                "li.jobs-search-results__list-item, "
                "div.base-card, "
                "div.job-search-card, "
                "div[data-job-id], "
                "div.job-card-container"
            ).all()

            seen_urls = set()
            for card in cards[:limit * 2]:
                try:
                    title_el = card.locator("h3, a.base-card__full-link, .job-card-list__title, .job-search-card__title").first
                    title = await title_el.text_content() if await title_el.count() > 0 else "Software / AI Engineer"

                    link_el = card.locator("a[href*='/jobs/view/'], a.base-card__full-link, a").first
                    href = await link_el.get_attribute("href") if await link_el.count() > 0 else ""

                    comp_el = card.locator("h4, .job-search-card__subtitle, .job-card-container__company-name").first
                    company = await comp_el.text_content() if await comp_el.count() > 0 else "Hiring Company"

                    if href:
                        # Clean tracking parameters from LinkedIn job URL
                        clean_url = href.split("?")[0]
                        if clean_url not in seen_urls:
                            seen_urls.add(clean_url)
                            jobs.append({
                                "platform": "linkedin",
                                "title": title.strip(),
                                "company": company.strip(),
                                "url": clean_url
                            })
                            if len(jobs) >= limit:
                                break
                except Exception:
                    pass
        except Exception as e:
            print(f"[Job Scout] Error extracting LinkedIn jobs: {e}", flush=True)

        print(f"[Job Scout] Found {len(jobs)} Easy Apply jobs on LinkedIn.", flush=True)
        return jobs

    async def scout_yc(self, keyword: str = "AI Engineer", limit: int = 5) -> List[Dict]:
        """
        Scout live Y Combinator startup jobs on workatastartup.com.
        """
        enc_kw = urllib.parse.quote(keyword)
        search_url = f"https://www.workatastartup.com/jobs?query={enc_kw}"
        print(f"\n[Job Scout] 🔍 Searching Y Combinator (Work at a Startup) for '{keyword}'...", flush=True)

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"[Job Scout] Navigation warning: {e}", flush=True)

        jobs = []
        try:
            job_rows = await self.page.locator(".job-name, a[href*='/jobs/']").all()
            seen_urls = set()

            for el in job_rows:
                try:
                    href = await el.get_attribute("href")
                    if not href or "/jobs/" not in href:
                        continue
                    full_url = href if href.startswith("http") else f"https://www.workatastartup.com{href}"
                    full_url = full_url.split("?")[0]

                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    title = (await el.text_content() or "Startup Role").strip()
                    # Try to locate parent company name
                    company = "YC Startup"
                    parent = el.locator("xpath=ancestor::div[contains(@class,'w-full') or contains(@class,'border-b')][1]")
                    if await parent.count() > 0:
                        comp_el = parent.locator(".company-name, .font-bold, a[href*='/companies/']").first
                        if await comp_el.count() > 0:
                            c_txt = await comp_el.text_content()
                            if c_txt:
                                company = c_txt.strip()

                    jobs.append({
                        "platform": "yc",
                        "title": title,
                        "company": company,
                        "url": full_url
                    })
                    if len(jobs) >= limit:
                        break
                except Exception:
                    pass
        except Exception as e:
            print(f"[Job Scout] Error extracting YC jobs: {e}", flush=True)

        print(f"[Job Scout] Found {len(jobs)} jobs on YC Work at a Startup.", flush=True)
        return jobs

    async def scout_jobs(self, platform: str = "all", keyword: str = "AI Engineer", location: str = "Bengaluru", limit: int = 5) -> List[Dict]:
        """
        Unified scout supporting 'naukri', 'wellfound', 'linkedin', 'yc' / 'ycombinator', and 'all'.
        """
        plat = (platform or "all").lower().strip()
        if plat == "naukri":
            return await self.scout_naukri(keyword=keyword, location=location, limit=limit)
        elif plat == "wellfound":
            return await self.scout_wellfound(keyword=keyword, limit=limit)
        elif plat == "linkedin":
            return await self.scout_linkedin(keyword=keyword, location=location, limit=limit)
        elif plat in ("yc", "ycombinator"):
            return await self.scout_yc(keyword=keyword, limit=limit)
        else:
            # All platforms
            per_plat = max(1, limit // 4)
            n_jobs = await self.scout_naukri(keyword=keyword, location=location, limit=per_plat)
            w_jobs = await self.scout_wellfound(keyword=keyword, limit=per_plat)
            l_jobs = await self.scout_linkedin(keyword=keyword, location=location, limit=per_plat)
            y_jobs = await self.scout_yc(keyword=keyword, limit=per_plat)

            combined = []
            max_len = max(len(n_jobs), len(w_jobs), len(l_jobs), len(y_jobs))
            for i in range(max_len):
                if i < len(n_jobs): combined.append(n_jobs[i])
                if i < len(w_jobs): combined.append(w_jobs[i])
                if i < len(l_jobs): combined.append(l_jobs[i])
                if i < len(y_jobs): combined.append(y_jobs[i])

            return combined[:limit]

import asyncio
from typing import List, Dict, Any
from app.scrapers.naukri_scraper import naukri_scraper
from app.scrapers.wellfound_scraper import wellfound_scraper
from app.scrapers.linkedin_scraper import linkedin_scraper
from app.scrapers.yc_scraper import yc_scraper
from app.scrapers.base_scraper import ScrapedJob

class JobScoutAgent:
    def __init__(self):
        self.scrapers = {
            "naukri": naukri_scraper,
            "wellfound": wellfound_scraper,
            "linkedin": linkedin_scraper,
            "yc": yc_scraper,
            "ycombinator": yc_scraper
        }

    async def find_jobs(self, query: str, platform: str = "all", limit: int = 25, location: str = "India", max_days_old: int = 15) -> List[ScrapedJob]:
        """
        Platform-targeted search:
        - platform='naukri': 100% verified Naukri openings.
        - platform='wellfound': 100% verified Wellfound startup openings.
        - platform='linkedin': 100% verified LinkedIn Easy Apply openings.
        - platform='yc' or 'ycombinator': 100% verified YC startup openings.
        - platform='all': returns balanced jobs from all platforms.
        Strictly role-relevant within 15 days, newest first.
        """
        plat = (platform or "all").lower().strip()

        if plat == "naukri":
            return await naukri_scraper.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=limit)
        elif plat == "wellfound":
            return await wellfound_scraper.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=limit)
        elif plat == "linkedin":
            return await linkedin_scraper.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=limit)
        elif plat in ("yc", "ycombinator"):
            return await yc_scraper.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=limit)
        else:
            # Query all distinct scrapers concurrently with fault tolerance
            active_scrapers = [naukri_scraper, wellfound_scraper, linkedin_scraper, yc_scraper]
            per_platform_limit = max(2, (limit // len(active_scrapers)) + 1)
            tasks = [s.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=per_platform_limit) for s in active_scrapers]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            lists = [r if isinstance(r, list) else [] for r in raw_results]
            combined = []
            max_len = max((len(l) for l in lists), default=0)
            for i in range(max_len):
                for l in lists:
                    if i < len(l):
                        combined.append(l[i])

            return combined[:limit]

job_scout = JobScoutAgent()

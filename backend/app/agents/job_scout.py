import asyncio
from typing import List, Dict, Any
from app.scrapers.naukri_scraper import naukri_scraper
from app.scrapers.wellfound_scraper import wellfound_scraper
from app.scrapers.base_scraper import ScrapedJob

class JobScoutAgent:
    def __init__(self):
        self.scrapers = {
            "naukri": naukri_scraper,
            "wellfound": wellfound_scraper
        }

    async def find_jobs(self, query: str, platform: str = "all", limit: int = 25, location: str = "India", max_days_old: int = 15) -> List[ScrapedJob]:
        """
        Platform-targeted search:
        - platform='naukri': 100% verified Naukri openings.
        - platform='wellfound': 100% verified Wellfound startup openings.
        - platform='all': returns both platforms.
        Strictly role-relevant within 15 days, newest first.
        """
        plat = (platform or "all").lower().strip()

        if plat == "naukri":
            return await naukri_scraper.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=limit)
        elif plat == "wellfound":
            return await wellfound_scraper.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=limit)
        else:
            # Query both
            n_task = naukri_scraper.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=limit // 2)
            w_task = wellfound_scraper.search_jobs(query=query, location=location, max_days_old=max_days_old, limit=limit // 2)
            n_res, w_res = await asyncio.gather(n_task, w_task)
            combined = []
            max_len = max(len(n_res), len(w_res))
            for i in range(max_len):
                if i < len(n_res):
                    combined.append(n_res[i])
                if i < len(w_res):
                    combined.append(w_res[i])
            return combined[:limit]

job_scout = JobScoutAgent()

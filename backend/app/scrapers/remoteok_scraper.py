import time
import httpx
import re
from typing import List
from app.scrapers.base_scraper import BaseJobScraper, ScrapedJob

class RemoteOKScraper(BaseJobScraper):
    def __init__(self):
        super().__init__(platform_name="RemoteOK / Startups")
        self.api_url = "https://remoteok.com/api"

    async def search_jobs(self, query: str, location: str = "Remote", max_days_old: int = 14, limit: int = 15) -> List[ScrapedJob]:
        results: List[ScrapedJob] = []
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                res = await client.get(self.api_url)
                if res.status_code == 200:
                    data = res.json()
                    job_items = [item for item in data if isinstance(item, dict) and "position" in item]

                    # Tokenize search query keywords (e.g. "AI Engineer" -> "ai", "engineer")
                    raw_keywords = [k.strip().lower() for k in re.split(r"[\s,/]+", query) if len(k.strip()) >= 2]
                    
                    matched = []
                    for job in job_items:
                        pos = job.get("position", "").lower()
                        tags = " ".join(job.get("tags", [])).lower()
                        desc = job.get("description", "").lower()
                        blob = f"{pos} {tags} {desc}"

                        # Strict Title/Role Matching to avoid unrelated jobs (e.g. recruiters, ops)
                        is_match = False
                        if "analyst" in raw_keywords:
                            if "analyst" in pos:
                                is_match = True
                        elif "ml" in raw_keywords or "learning" in raw_keywords:
                            if "ml" in pos.split() or "machine learning" in pos or "mlops" in pos:
                                is_match = True
                        elif "ai" in raw_keywords:
                            if "ai" in pos.split() or "applied ai" in pos or "llm" in pos:
                                is_match = True
                        elif any(kw in pos for kw in raw_keywords):
                            is_match = True

                        if is_match:
                            matched.append(job)

                    now_ts = int(time.time())
                    for item in matched[:limit]:
                        job_ts = int(item.get("epoch") or 0)
                        age_sec = now_ts - job_ts if job_ts > 0 else 86400
                        days = age_sec // 86400
                        hours = (age_sec % 86400) // 3600
                        time_str = f"{days}d ago" if days > 0 else (f"{hours}h ago" if hours > 0 else "Just now")

                        results.append(
                            ScrapedJob(
                                title=item.get("position", "Software Engineer").replace("&amp;", "&"),
                                company=item.get("company", "Tech Startup"),
                                location=item.get("location") or "Remote",
                                job_url=item.get("url", f"https://remoteok.com/l/{item.get('id')}"),
                                description_snippet=(item.get("description") or "")[:200].replace("<p>", "").replace("</p>", ""),
                                platform=self.platform_name,
                                posted_time_ago=time_str,
                                posted_timestamp=job_ts,
                                easy_apply_available=True
                            )
                        )
        except Exception as e:
            print(f"[RemoteOKScraper Error]: {e}")

        return results

remoteok_scraper = RemoteOKScraper()

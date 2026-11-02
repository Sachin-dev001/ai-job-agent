import httpx
import re
from bs4 import BeautifulSoup
from typing import List
from app.scrapers.base_scraper import BaseJobScraper, ScrapedJob

class YCNewsScraper(BaseJobScraper):
    """
    Scrapes Y Combinator's official startup hiring board (news.ycombinator.com/jobs).
    Direct founder postings from active YC backed startups.
    """
    def __init__(self):
        super().__init__(platform_name="Y Combinator Startups")
        self.url = "https://news.ycombinator.com/jobs"

    async def search_jobs(self, query: str, location: str = "Remote", max_days_old: int = 14, limit: int = 15) -> List[ScrapedJob]:
        results: List[ScrapedJob] = []
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                res = await client.get(self.url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    rows = soup.select("tr.athing")

                    keywords = [k.strip().lower() for k in re.split(r"[\s,/]+", query) if len(k.strip()) >= 2]

                    for row in rows:
                        title_cell = row.select_one("td.title span.titleline a")
                        subtext = row.find_next_sibling("tr")
                        time_cell = subtext.select_one("span.age") if subtext else None

                        if title_cell:
                            raw_text = title_cell.text.strip()
                            link = title_cell.get("href", "")
                            time_str = time_cell.text.strip() if time_cell else "Recently"

                            # Parse YC title format: "Company (YC Batch) Is Hiring Role..."
                            company = "YC Startup"
                            title = raw_text
                            if "is hiring" in raw_text.lower():
                                match = re.split(r"is hiring", raw_text, flags=re.IGNORECASE)
                                company = match[0].strip()
                                title = match[1].strip().lstrip(":")

                            results.append(
                                ScrapedJob(
                                    title=title,
                                    company=company,
                                    location="Remote / Hybrid",
                                    job_url=f"https://news.ycombinator.com/{link}" if link.startswith("item") else link,
                                    description_snippet="YC Founder hiring post",
                                    platform=self.platform_name,
                                    posted_time_ago=time_str,
                                    easy_apply_available=True
                                )
                            )

                        if len(results) >= limit:
                            break
        except Exception as e:
            print(f"[YCNewsScraper Error]: {e}")

        return results

yc_news_scraper = YCNewsScraper()

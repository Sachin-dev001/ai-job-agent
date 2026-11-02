import httpx
from typing import List
from bs4 import BeautifulSoup
from app.scrapers.base_scraper import BaseJobScraper, ScrapedJob

class YCJobsScraper(BaseJobScraper):
    def __init__(self):
        super().__init__(platform_name="YC Jobs")
        self.base_url = "https://www.workatastartup.com"

    async def search_jobs(self, query: str, location: str = "Remote", max_days_old: int = 7, limit: int = 10) -> List[ScrapedJob]:
        results: List[ScrapedJob] = []
        search_url = f"{self.base_url}/jobs?query={query.replace(' ', '+')}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                response = await client.get(search_url)
                if response.status_code != 200:
                    return results

                soup = BeautifulSoup(response.text, "html.parser")
                job_elements = soup.select(".job-name, .w-full.border-b")

                for el in job_elements[:limit]:
                    title_elem = el.select_one("a.job-name") or el.select_one("a")
                    company_elem = el.select_one(".company-name") or el.select_one(".font-bold")
                    
                    if title_elem and company_elem:
                        href = title_elem.get("href", "")
                        full_url = f"{self.base_url}{href}" if href.startswith("/") else href
                        results.append(
                            ScrapedJob(
                                title=title_elem.text.strip(),
                                company=company_elem.text.strip(),
                                location=location,
                                job_url=full_url,
                                description_snippet="YC Backed Startup opportunity",
                                platform=self.platform_name,
                                posted_time_ago="Recently",
                                easy_apply_available=True
                            )
                        )
        except Exception as e:
            print(f"[YCJobsScraper] Error scraping: {e}")

        return results

yc_jobs_scraper = YCJobsScraper()

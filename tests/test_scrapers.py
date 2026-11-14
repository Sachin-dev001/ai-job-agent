import pytest
import sys
import asyncio
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.scrapers.base_scraper import ScrapedJob
from app.scrapers.linkedin_scraper import LinkedInScraper
from app.scrapers.yc_scraper import YCScraper


def test_scraped_job_model():
    job = ScrapedJob(
        title="Senior Python AI Engineer",
        company="Instawork",
        location="Bengaluru / Remote",
        job_url="https://www.workatastartup.com/jobs/95531",
        platform="YC Jobs",
        description_snippet="Autonomous agents and distributed pipelines.",
        posted_time_ago="1d ago"
    )
    assert job.title == "Senior Python AI Engineer"
    assert job.company == "Instawork"
    assert job.platform == "YC Jobs"
    assert "workatastartup.com" in job.job_url


def test_linkedin_scraper_search_jobs():
    async def _test():
        scraper = LinkedInScraper()
        assert scraper.platform_name == "LinkedIn"

        # Search for Python roles
        jobs = await scraper.search_jobs(query="Python", limit=5)
        assert len(jobs) > 0
        assert all(isinstance(j, ScrapedJob) for j in jobs)
        assert all("linkedin.com" in j.job_url for j in jobs)

    asyncio.run(_test())


def test_yc_scraper_search_jobs():
    async def _test():
        scraper = YCScraper()
        assert scraper.platform_name == "YC Jobs"

        # Search for AI / GenAI roles
        jobs = await scraper.search_jobs(query="AI", limit=5)
        assert len(jobs) > 0
        assert all(isinstance(j, ScrapedJob) for j in jobs)
        assert all("workatastartup.com" in j.job_url for j in jobs)

    asyncio.run(_test())

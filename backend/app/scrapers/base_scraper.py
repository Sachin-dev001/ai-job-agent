from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ScrapedJob(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Hiring company name")
    location: str = Field(default="Remote", description="Job location or Remote")
    job_url: str = Field(description="Direct URL to view/apply")
    description_snippet: str = Field(default="", description="Snippet or full JD text")
    platform: str = Field(description="Source platform, e.g. Naukri.com, YC Jobs, RemoteOK")
    posted_time_ago: str = Field(default="Just now", description="Human-readable posting age, e.g. '1 hour ago', '1 day ago'")
    posted_timestamp: Optional[int] = Field(default=None, description="Unix epoch timestamp in seconds")
    easy_apply_available: bool = Field(default=True, description="Whether 1-click or direct apply is possible")

class BaseJobScraper(ABC):
    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    @abstractmethod
    async def search_jobs(self, query: str, location: str = "India", max_days_old: int = 7, limit: int = 15) -> List[ScrapedJob]:
        """
        Searches platform for job postings matching query.
        Filters out stale postings older than max_days_old (default 7 days).
        """
        pass

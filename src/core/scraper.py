from abc import ABC, abstractmethod
from typing import List
from src.core.repository import JobRepository
from src.core.models import Job

class BaseScraper(ABC):
    def __init__(self, repository: JobRepository):
        self.repository = repository

    @abstractmethod
    async def scrape(self, url: str) -> List[Job]:
        """Scrape the given URL and return a list of Jobs"""
        pass

class GreenhouseScraper(BaseScraper):
    async def scrape(self, url: str) -> List[Job]:
        return []

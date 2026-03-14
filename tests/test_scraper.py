import pytest

# We expect an ImportError here until we implement the code in Step 3
from src.core.scraper import BaseScraper, GreenhouseScraper
from src.core.repository import JobRepository

class MockRepo(JobRepository):
    async def save_job(self, job): pass
    async def get_job(self, job_hash): return None
    async def update_status(self, job_hash, status): pass

def test_base_scraper_is_abstract():
    # Should not be able to instantiate an abstract base class
    with pytest.raises(TypeError):
        scraper = BaseScraper()

def test_greenhouse_scraper_accepts_repository():
    repo = MockRepo()
    scraper = GreenhouseScraper(repository=repo)
    assert scraper.repository == repo

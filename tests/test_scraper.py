import pytest
from unittest.mock import AsyncMock, patch
from src.core.scraper import BaseScraper, GreenhouseScraper
from src.core.repository import JobRepository
from src.core.models import Job, JobStatus

class MockRepo(JobRepository):
    def __init__(self):
        self.jobs = {}
        
    async def save_job(self, job): 
        self.jobs[job.id] = job
        
    async def get_job(self, job_hash): 
        return self.jobs.get(job_hash)

    async def update_status(self, job_hash, status): 
        if job_hash in self.jobs:
            self.jobs[job_hash].status = status

def test_base_scraper_is_abstract():
    # Should not be able to instantiate an abstract base class
    with pytest.raises(TypeError):
        scraper = BaseScraper()

def test_greenhouse_scraper_accepts_repository():
    repo = MockRepo()
    scraper = GreenhouseScraper(repository=repo)
    assert scraper.repository == repo

@pytest.mark.asyncio
async def test_greenhouse_scraper_filters_and_deduplicates():
    repo = MockRepo()
    # Pre-seed a job to test deduplication
    existing_job = Job(
        id="123", company="TestCo", role="Software Engineer Intern",
        job_description="Old job", url="https://boards.greenhouse.io/testco/jobs/123",
        required_skills=[], custom_questions=[]
    )
    await repo.save_job(existing_job)
    
    scraper = GreenhouseScraper(repository=repo)
    
    # We will mock the internal fetch method to return two roles (one SWE, one Data Analyst)
    # The SWE role should be saved since it's Fall 2026 relevant, the Analyst should be ignored.
    # We also mock an existing URL to ensure it skips the duplicate.
    
    with patch.object(scraper, '_fetch_job_listings', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {"title": "Software Engineer Intern (Fall 2026)", "url": "https://boards.greenhouse.io/testco/jobs/456", "company": "TestCo"},
            {"title": "Financial Analyst", "url": "https://boards.greenhouse.io/testco/jobs/789", "company": "TestCo"},
            {"title": "Software Engineer Intern", "url": "https://boards.greenhouse.io/testco/jobs/123", "company": "TestCo"} # Duplicate
        ]
        
        with patch.object(scraper, '_fetch_job_details', new_callable=AsyncMock) as mock_details:
            mock_details.return_value = {
                "job_description": "We need Python skills.",
                "required_skills": ["Python", "Playwright"],
                "custom_questions": ["What is your GPA?"]
            }
            
            jobs = await scraper.scrape("https://boards.greenhouse.io/testco")
            
            # Should only scrape the non-duplicate SWE role
            assert len(jobs) == 1
            assert jobs[0].role == "Software Engineer Intern (Fall 2026)"
            assert jobs[0].company == "TestCo"
            assert jobs[0].url == "https://boards.greenhouse.io/testco/jobs/456"
            
            # Verify the mock was called only once for the new SWE job, not for the Analyst or the Duplicate
            mock_details.assert_called_once_with("https://boards.greenhouse.io/testco/jobs/456")


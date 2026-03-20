import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.core.scraper import IntentScraper
from src.core.models import Job

@pytest.fixture
def mock_repository():
    repo = AsyncMock()
    repo.get_job.return_value = None  # Always new job
    return repo

@pytest.mark.asyncio
async def test_intent_scraper_finds_jobs(mock_repository):
    with patch('src.core.scraper.DDGS') as mock_ddgs:
        instance = mock_ddgs.return_value.__enter__.return_value
        instance.text.return_value = [
            {"href": "https://boards.greenhouse.io/twitch/jobs/123", "title": "Software Engineer Intern Twitch"}
        ]
        
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.text = '<html><body><script>var x=1;</script><main>Test Job Description</main></body></html>'
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            scraper = IntentScraper(repository=mock_repository)
            jobs = await scraper.scrape("Software Engineer Intern Vancouver")
            
            assert len(jobs) == 1
            assert jobs[0].id == "123"
            assert jobs[0].role == "Software Engineer Intern Twitch"
            assert "Test Job Description" in jobs[0].job_description
            assert "<script>" not in jobs[0].job_description
            
            mock_repository.save_job.assert_called_once()

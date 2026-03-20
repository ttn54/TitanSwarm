import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.scraper import UniversalScraper
from src.core.models import Job

@pytest.fixture
def mock_repository():
    repo = AsyncMock()
    repo.get_job.return_value = None  # Always new job
    return repo

@pytest.mark.asyncio
async def test_universal_scraper_fetches_jobs(mock_repository):
    with patch('src.core.scraper.scrape_jobs') as mock_scrape_jobs:
        # Mock dataframe returned by jobspy
        mock_df = pd.DataFrame({
            'id': ['li-123'],
            'site': ['linkedin'],
            'title': ['Software Engineer Intern'],
            'company': ['TechCorp'],
            'job_url': ['https://linkedin.com/123'],
            'description': ['Test job description']
        })
        mock_scrape_jobs.return_value = mock_df
        
        scraper = UniversalScraper(repository=mock_repository)
        jobs = await scraper.scrape(role="Software Engineer Intern", location="Vancouver, BC", results_wanted=1)
        
        assert len(jobs) == 1
        assert jobs[0].id == "li-123"
        assert jobs[0].company == "TechCorp"
        assert jobs[0].role == "Software Engineer Intern"
        assert jobs[0].job_description == "Test job description"
        assert jobs[0].url == "https://linkedin.com/123"
        
        mock_repository.save_job.assert_called_once()

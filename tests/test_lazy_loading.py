import pytest
from unittest.mock import patch, AsyncMock
import pandas as pd
from src.scrapers.worker import SourcingEngine
from src.core.models import Job, JobStatus
from src.core.ai import AITailor

@pytest.mark.asyncio
@patch('src.scrapers.worker.scrape_jobs')
async def test_sourcing_engine_disables_linkedin_description_fetch(mock_scrape_jobs):
    repo = AsyncMock()
    engine = SourcingEngine(repository=repo)
    
    mock_scrape_jobs.return_value = pd.DataFrame()
    
    await engine._scrape_df("role", "location", 25)
    
    mock_scrape_jobs.assert_called_once()
    _, kwargs = mock_scrape_jobs.call_args
    assert kwargs.get('linkedin_fetch_description') is False, "Must set linkedin_fetch_description=False for lazy loading"

from src.core.ai import AITailor, _parse_ledger_as_resume
@pytest.mark.asyncio
@patch('src.core.ai.AITailor._call_openai', new_callable=AsyncMock)
async def test_ai_tailor_detects_short_description(mock_call_openai):
    # Mocking openai to just return a dummy
    from src.core.models import TailoredApplication
    mock_call_openai.return_value = TailoredApplication(job_id="1", tailored_bullets=[], q_and_a_responses={}, missing_skills=[], skills_to_highlight={}, tailored_projects=[], tailored_experience=[])
    
    # Mock the internal fetch
    mock_ledger = AsyncMock()
    mock_ledger.ledger_path = "mock.md"
    tailor = AITailor(mock_ledger)
    
    with patch('src.core.ai._parse_ledger_as_resume', return_value="dummy resume"):
        with patch.object(tailor, 'fetch_missing_description', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "Long description fetched JIT for this test."
            
            job = Job(id="1", company="test", role="test", status=JobStatus.DISCOVERED, job_description="short", url="http://link")
            await tailor.tailor_application(job)
            
            mock_fetch.assert_called_once_with("http://link")
            assert job.job_description == "Long description fetched JIT for this test."

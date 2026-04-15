import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from src.scrapers.worker import SourcingEngine
from src.core.models import Job, JobStatus

@pytest.mark.asyncio
@patch("src.scrapers.worker.scrape_jobs")
async def test_sourcing_engine_fetches_and_validates_jobs(mock_scrape_jobs):
    import pandas as pd
    mock_df = pd.DataFrame([{
        "id": "ind-123",
        "title": "Software Engineer Intern",
        "company": "Tech Corp",
        "description": "Must know Python and Go",
        "job_url": "https://indeed.com/job/123",
        "site": "indeed"
    }])
    mock_scrape_jobs.return_value = mock_df

    mock_repo = AsyncMock()
    mock_repo.get_job.return_value = None  # No duplicate: job is new

    engine = SourcingEngine(repository=mock_repo, interval_hours=12)

    count, found_ids = await engine.run_sweep(role="Software Engineer Intern", location="Vancouver, BC", results_wanted=1)

    assert count == 1
    assert found_ids == ["ind-123"]
    assert mock_repo.save_job.call_count == 1

    saved_arg = mock_repo.save_job.call_args[0][0]
    assert isinstance(saved_arg, Job)
    assert saved_arg.company == "Tech Corp"
    assert saved_arg.role == "Software Engineer Intern"
    assert saved_arg.status == JobStatus.DISCOVERED
    assert saved_arg.url == "https://indeed.com/job/123"

@pytest.mark.asyncio
@patch("src.scrapers.worker.scrape_jobs")
async def test_sourcing_engine_extracts_location_and_date(mock_scrape_jobs):
    """run_sweep must persist location and date_posted from the scraped row."""
    import pandas as pd
    mock_df = pd.DataFrame([{
        "id": "li-999",
        "title": "Software Engineer Intern",
        "company": "Shopify",
        "description": "Write Python all day.",
        "job_url": "https://linkedin.com/job/999",
        "site": "linkedin",
        "location": "Vancouver, BC",
        "date_posted": "2026-04-06",
    }])
    mock_scrape_jobs.return_value = mock_df

    mock_repo = AsyncMock()
    mock_repo.get_job.return_value = None

    engine = SourcingEngine(repository=mock_repo, interval_hours=12)
    count, found_ids = await engine.run_sweep(role="Software Engineer Intern", location="Vancouver, BC", results_wanted=1)

    assert count == 1
    saved: Job = mock_repo.save_job.call_args[0][0]
    assert saved.location == "Vancouver, BC"
    assert saved.date_posted == "2026-04-06"


@pytest.mark.asyncio
@patch("src.scrapers.worker.scrape_jobs")
async def test_title_filter_requires_job_type_word(mock_scrape_jobs):
    """Smarter title filter: if search contains 'intern', title must contain 'intern'."""
    import pandas as pd
    # "Data Scientist" does NOT contain "intern" — should be filtered out
    mock_df = pd.DataFrame([{
        "id": "li-888",
        "title": "Data Scientist",
        "company": "Google",
        "description": "ML research.",
        "job_url": "https://linkedin.com/job/888",
        "site": "linkedin",
    }])
    mock_scrape_jobs.return_value = mock_df

    mock_repo = AsyncMock()
    mock_repo.get_job.return_value = None

    engine = SourcingEngine(repository=mock_repo, interval_hours=12)
    count, found_ids = await engine.run_sweep(role="Software Engineer Intern", location="Vancouver, BC", results_wanted=1)

    # "Data Scientist" contains neither "software" nor "engineer" nor "intern"
    # — should be filtered; nothing saved
    assert count == 0
    assert found_ids == []


@pytest.mark.asyncio
@patch("src.scrapers.worker.scrape_jobs")
async def test_sourcing_engine_skips_existing_jobs(mock_scrape_jobs):
    import pandas as pd
    mock_df = pd.DataFrame([{
        "id": "ind-123",
        "title": "Software Engineer Intern",
        "company": "Tech Corp",
        "description": "Must know Python and Go",
        "job_url": "https://indeed.com/job/123",
        "site": "indeed"
    }])
    mock_scrape_jobs.return_value = mock_df

    mock_repo = AsyncMock()
    # Simulate that the job already exists in the database
    mock_repo.get_job.return_value = Job(
        id="ind-123", role="Software Engineer Intern", company="Tech Corp",
        job_description="old", url="https://indeed.com/job/123"
    )

    engine = SourcingEngine(repository=mock_repo, interval_hours=12)

    count, found_ids = await engine.run_sweep(role="Software Engineer", location="Vancouver", results_wanted=1)

    # The repository should NOT save the job if it already exists
    mock_repo.get_job.assert_called_once_with("ind-123", user_id=1)
    assert mock_repo.save_job.call_count == 0
    assert count == 0
    assert found_ids == ["ind-123"]  # Still in found list even if duplicate


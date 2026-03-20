import pytest
from unittest.mock import patch, MagicMock
from src.scrapers.worker import SourcingEngine
from src.core.models import Job, JobStatus

@patch("src.scrapers.worker.scrape_jobs")
def test_sourcing_engine_fetches_and_validates_jobs(mock_scrape_jobs):
    # Arrange
    # Mocking the DataFrame returned by jobspy's scrape_jobs
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

    mock_repo = MagicMock()
    mock_repo.job_exists.return_value = False
    
    engine = SourcingEngine(repository=mock_repo, interval_hours=12)

    # Act
    engine.run_sweep(role="Software Engineer Intern", location="Vancouver, BC", results_wanted=1)

    # Assert
    assert mock_repo.save_job.call_count == 1
    
    saved_arg = mock_repo.save_job.call_args[0][0]
    assert isinstance(saved_arg, Job)
    assert saved_arg.company == "Tech Corp"
    assert saved_arg.role == "Software Engineer Intern"
    assert saved_arg.status == JobStatus.DISCOVERED
    assert saved_arg.url == "https://indeed.com/job/123"

@patch("src.scrapers.worker.scrape_jobs")
def test_sourcing_engine_skips_existing_jobs(mock_scrape_jobs):
    # Arrange
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

    mock_repo = MagicMock()
    # Simulate that the job already exists in the database
    mock_repo.job_exists.return_value = True
    
    engine = SourcingEngine(repository=mock_repo, interval_hours=12)

    # Act
    engine.run_sweep(role="Software Engineer", location="Vancouver", results_wanted=1)

    # Assert
    # The repository should NOT save the job if it already exists
    mock_repo.job_exists.assert_called_once_with("ind-123")
    assert mock_repo.save_job.call_count == 0


import pytest
import asyncio
from src.core.models import Job, JobStatus
from src.infrastructure.postgres_repo import PostgresRepository # This does not exist yet

@pytest.fixture
async def repo():
    # Use SQLite in-memory database for testing the repository logic
    repo = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await repo.init_db() # Should automatically create the schema
    yield repo
    await repo.close() # Clean up

@pytest.mark.asyncio
async def test_save_and_get_job(repo):
    """Test saving a job to the repository and retrieving it."""
    job = Job(
        id="li-999",
        title="Software Engineer Intern",
        company="TechCorp",
        location="San Francisco, CA",
        description="Looking for an intern to build our distributed state machine.",
        job_url="https://linkedin.com/jobs/999",
        status=JobStatus.DISCOVERED
    )
    
    # Save the job
    success = await repo.save_job(job)
    assert success is True, "Repository failed to save the job."
    
    # Retrieve the job
    retrieved_job = await repo.get_job("li-999")
    assert retrieved_job is not None, "Repository failed to retrieve the saved job."
    assert retrieved_job.id == job.id
    assert retrieved_job.title == job.title
    assert retrieved_job.status == job.status

@pytest.mark.asyncio
async def test_get_jobs_by_status(repo):
    """Test retrieving multiple jobs filtered by their status for the Streamlit UI."""
    job1 = Job(
        id="li-1", title="Role 1", company="Corp1", location="SF",
        description="D1", job_url="url1", status=JobStatus.PENDING_REVIEW
    )
    job2 = Job(
        id="li-2", title="Role 2", company="Corp2", location="NY",
        description="D2", job_url="url2", status=JobStatus.DISCOVERED
    )
    job3 = Job(
        id="li-3", title="Role 3", company="Corp3", location="TX",
        description="D3", job_url="url3", status=JobStatus.PENDING_REVIEW
    )
    
    await repo.save_job(job1)
    await repo.save_job(job2)
    await repo.save_job(job3)
    
    pending_jobs = await repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)
    assert len(pending_jobs) == 2, "Repository should have returned exactly 2 pending jobs."
    
    # Ensure only PENDING_REVIEW jobs are returned
    statuses = {j.status for j in pending_jobs}
    assert statuses == {JobStatus.PENDING_REVIEW}

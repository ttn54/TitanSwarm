import pytest
import asyncio
from src.ui.mock_repo import MockUIRepository
from src.core.models import JobStatus

@pytest.mark.asyncio
async def test_mock_ui_repo_initialization_and_filtering():
    repo = MockUIRepository()
    
    # 1. Test it comes pre-loaded with mock data
    pending_jobs = await repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)
    assert len(pending_jobs) > 0, "Repo should initialize with some pending jobs"
    
    # 2. Test status updates
    target_job = pending_jobs[0]
    await repo.update_status(target_job.id, JobStatus.SUBMITTED)
    
    # Verify the move
    new_pending_jobs = await repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)
    submitted_jobs = await repo.get_jobs_by_status(JobStatus.SUBMITTED)
    
    assert len(new_pending_jobs) == len(pending_jobs) - 1
    assert any(job.id == target_job.id for job in submitted_jobs)
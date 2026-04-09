import pytest
import asyncio
from datetime import date, timedelta
from src.ui.mock_repo import MockUIRepository
from src.core.models import Job, JobStatus
from src.ui.app import filter_by_date

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


def _make_job(id: str, date_posted: str = "") -> Job:
    return Job(id=id, company="Acme", role="SWE Intern",
               job_description="x", url="https://example.com",
               date_posted=date_posted)


def test_filter_by_date_any_returns_all():
    jobs = [_make_job("a", "2026-04-01"), _make_job("b", "2026-03-01"), _make_job("c", "")]
    assert filter_by_date(jobs, "Any") == jobs


def test_filter_by_date_7d_includes_recent():
    recent = str(date.today() - timedelta(days=3))
    old = str(date.today() - timedelta(days=20))
    jobs = [_make_job("new", recent), _make_job("old", old)]
    result = filter_by_date(jobs, "Last 7 days")
    assert len(result) == 1
    assert result[0].id == "new"


def test_filter_by_date_unknown_date_included():
    """Jobs with empty date_posted must NOT be excluded by any date filter (Option A)."""
    unknown = _make_job("unk", "")
    result = filter_by_date([unknown], "Last 7 days")
    assert len(result) == 1


def test_filter_by_date_14d():
    within_14 = str(date.today() - timedelta(days=10))
    beyond_14 = str(date.today() - timedelta(days=20))
    jobs = [_make_job("a", within_14), _make_job("b", beyond_14), _make_job("c", "")]
    result = filter_by_date(jobs, "Last 14 days")
    ids = {j.id for j in result}
    assert "a" in ids
    assert "c" in ids  # unknown date included
    assert "b" not in ids
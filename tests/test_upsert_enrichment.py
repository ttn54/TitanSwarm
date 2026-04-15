"""
Tests for Phase G.1 — UPSERT Enrichment Fix

Bug: Jobs scraped before salary columns existed show "No salary posted" forever
     because the dedup guard in run_sweep skips save_job for existing records,
     so the UPSERT never fires and stale NULL salary values are never refreshed.

Fix covers two layers:
  G1-1: PostgresRepository.save_job() MUST NOT overwrite `status` on conflict.
         A job that is SUBMITTED must stay SUBMITTED after a re-scrape.
  G1-2: PostgresRepository.save_job() MUST update enrichment fields (salary,
         description, location) on conflict.
  G1-3: SourcingEngine.run_sweep() MUST always call save_job for every found
         job (new OR existing with a real description), so enrichment is refreshed.
  G1-4: SourcingEngine.run_sweep() MUST NOT increment saved_count for jobs
         that already existed in the DB.
"""
import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch

from src.core.models import Job, JobStatus


# ─── shared helpers ──────────────────────────────────────────────────────────

def _make_job(**kwargs) -> Job:
    base = dict(
        id="ind-abc",
        company="Diligent",
        role="Software Engineering Intern",
        status=JobStatus.DISCOVERED,
        job_description="Work on AI platform.",
        url="https://ca.indeed.com/viewjob?jk=7403de8de21980f2",
    )
    base.update(kwargs)
    return Job(**base)


def _make_df(**row_overrides) -> pd.DataFrame:
    """Minimal valid DataFrame row that passes all worker.py filters."""
    row = {
        "id": "ind-abc",
        "title": "Software Engineering Intern",
        "company": "Diligent",
        "description": "Work on AI platform.",
        "job_url": "https://ca.indeed.com/viewjob?jk=7403de8de21980f2",
        "site": "indeed",
        "location": "Vancouver, BC",
        "date_posted": "2026-03-31",
        "min_amount": 21.0,
        "max_amount": 25.0,
        "currency": "CAD",
        "interval": "hourly",
    }
    row.update(row_overrides)
    return pd.DataFrame([row])


# ═════════════════════════════════════════════════════════════════════════════
# G1-1: UPSERT must preserve status on conflict
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_job_preserves_status_on_conflict():
    """
    If a job already exists with status=SUBMITTED, calling save_job() again
    with status=DISCOVERED must leave the DB row's status unchanged (SUBMITTED).

    Strategy: integration test using real SQLite in-memory repo.
    """
    from src.infrastructure.postgres_repo import PostgresRepository

    repo = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await repo.init_db()

    # 1. Save job as SUBMITTED (simulating a job the user already applied to)
    submitted_job = _make_job(status=JobStatus.SUBMITTED)
    await repo.save_job(submitted_job, user_id=1)

    # 2. Scraper rescans — save same ID but DISCOVERED (the "new scrape" payload)
    rediscovered_job = _make_job(status=JobStatus.DISCOVERED,
                                  salary_min=21.0, salary_max=25.0,
                                  salary_currency="CAD", salary_interval="hourly")
    await repo.save_job(rediscovered_job, user_id=1)

    # 3. Retrieve and assert status is still SUBMITTED
    result = await repo.get_job("ind-abc", user_id=1)
    assert result is not None
    assert result.status == JobStatus.SUBMITTED, (
        f"Expected SUBMITTED after re-scrape, got {result.status}"
    )

    await repo.close()


# ═════════════════════════════════════════════════════════════════════════════
# G1-2: UPSERT must update enrichment fields on conflict
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_job_updates_salary_on_conflict():
    """
    If a job exists with salary_min=NULL, calling save_job() with real salary
    data must update the salary columns in the DB row.
    """
    from src.infrastructure.postgres_repo import PostgresRepository

    repo = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await repo.init_db()

    # 1. Save with no salary (old record, pre-Phase F.1)
    old_job = _make_job(salary_min=None, salary_max=None,
                         salary_currency="", salary_interval="")
    await repo.save_job(old_job, user_id=1)

    # 2. Save again with salary populated (new scrape)
    enriched_job = _make_job(salary_min=21.0, salary_max=25.0,
                               salary_currency="CAD", salary_interval="hourly")
    await repo.save_job(enriched_job, user_id=1)

    # 3. Assert salary was updated
    result = await repo.get_job("ind-abc", user_id=1)
    assert result is not None
    assert result.salary_min == 21.0, f"Expected 21.0, got {result.salary_min}"
    assert result.salary_max == 25.0, f"Expected 25.0, got {result.salary_max}"
    assert result.salary_currency == "CAD"
    assert result.salary_interval == "hourly"

    await repo.close()


# ═════════════════════════════════════════════════════════════════════════════
# G1-3: run_sweep must call save_job for existing jobs (to refresh enrichment)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("src.scrapers.worker.scrape_jobs")
async def test_run_sweep_calls_save_job_for_existing_job(mock_scrape):
    """
    When a job already exists in the DB (get_job returns a job), run_sweep
    must still call save_job so the UPSERT can refresh salary/description.
    """
    from src.scrapers.worker import SourcingEngine

    mock_scrape.return_value = _make_df()

    mock_repo = AsyncMock()
    # Existing job has no salary
    mock_repo.get_job.return_value = _make_job(
        salary_min=None, salary_max=None, salary_currency="", salary_interval=""
    )

    engine = SourcingEngine(repository=mock_repo, interval_hours=12)
    await engine.run_sweep(role="Software Engineering Intern",
                            location="Vancouver, BC", results_wanted=1)

    # save_job MUST have been called despite the job existing
    assert mock_repo.save_job.call_count == 1, (
        "save_job was not called for an existing job — enrichment cannot refresh"
    )

    saved: Job = mock_repo.save_job.call_args[0][0]
    assert saved.salary_min == 21.0
    assert saved.salary_max == 25.0
    assert saved.salary_currency == "CAD"
    assert saved.salary_interval == "hourly"


# ═════════════════════════════════════════════════════════════════════════════
# G1-4: run_sweep must NOT increment saved_count for existing jobs
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("src.scrapers.worker.scrape_jobs")
async def test_run_sweep_does_not_count_existing_job_as_new(mock_scrape):
    """
    saved_count must be 0 when all found jobs already existed in the DB.
    The jobs should still appear in found_ids.
    """
    from src.scrapers.worker import SourcingEngine

    mock_scrape.return_value = _make_df()

    mock_repo = AsyncMock()
    # Job already exists with salary populated
    mock_repo.get_job.return_value = _make_job(
        salary_min=21.0, salary_max=25.0,
        salary_currency="CAD", salary_interval="hourly"
    )

    engine = SourcingEngine(repository=mock_repo, interval_hours=12)
    count, found_ids = await engine.run_sweep(
        role="Software Engineering Intern",
        location="Vancouver, BC", results_wanted=1
    )

    assert count == 0, f"Expected saved_count=0 for existing job, got {count}"
    assert "ind-abc" in found_ids, "Existing job should still appear in found_ids"

"""
Tests for Phase F.1 — Salary Display
  F1-1: format_salary() pure helper
  F1-2: SourcingEngine extracts salary from DataFrame
"""
import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch
from src.core.models import Job, JobStatus


# ═════════════════════════════════════════════════════════════════════════════
# F1-1: format_salary() helper
# ═════════════════════════════════════════════════════════════════════════════

def _make_job(**kwargs) -> Job:
    base = dict(
        id="test-1", company="Acme", role="SWE Intern",
        status=JobStatus.DISCOVERED, job_description="Do things.",
        url="https://example.com",
    )
    base.update(kwargs)
    return Job(**base)


class TestFormatSalary:
    def test_full_range_yearly_usd(self):
        from src.core.models import format_salary
        job = _make_job(salary_min=80000, salary_max=120000,
                        salary_currency="USD", salary_interval="yearly")
        assert format_salary(job) == "$80,000 – $120,000/yr"

    def test_full_range_yearly_cad(self):
        from src.core.models import format_salary
        job = _make_job(salary_min=80000, salary_max=120000,
                        salary_currency="CAD", salary_interval="yearly")
        assert format_salary(job) == "CA$80,000 – CA$120,000/yr"

    def test_max_only(self):
        from src.core.models import format_salary
        job = _make_job(salary_min=None, salary_max=90000,
                        salary_currency="USD", salary_interval="yearly")
        assert format_salary(job) == "Up to $90,000/yr"

    def test_min_only(self):
        from src.core.models import format_salary
        job = _make_job(salary_min=70000, salary_max=None,
                        salary_currency="USD", salary_interval="yearly")
        assert format_salary(job) == "From $70,000/yr"

    def test_hourly_interval(self):
        from src.core.models import format_salary
        job = _make_job(salary_min=25, salary_max=35,
                        salary_currency="USD", salary_interval="hourly")
        assert format_salary(job) == "$25 – $35/hr"

    def test_monthly_interval(self):
        from src.core.models import format_salary
        job = _make_job(salary_min=6000, salary_max=8000,
                        salary_currency="USD", salary_interval="monthly")
        assert format_salary(job) == "$6,000 – $8,000/mo"

    def test_both_none_returns_none(self):
        from src.core.models import format_salary
        job = _make_job(salary_min=None, salary_max=None)
        assert format_salary(job) is None

    def test_unknown_interval_has_no_suffix(self):
        from src.core.models import format_salary
        job = _make_job(salary_min=100000, salary_max=150000,
                        salary_currency="USD", salary_interval="")
        result = format_salary(job)
        assert result == "$100,000 – $150,000"


# ═════════════════════════════════════════════════════════════════════════════
# F1-2: worker.py extracts salary fields from DataFrame
# ═════════════════════════════════════════════════════════════════════════════

class TestWorkerSalaryExtraction:
    @pytest.mark.asyncio
    @patch("src.scrapers.worker.scrape_jobs")
    async def test_run_sweep_saves_salary_fields(self, mock_scrape):
        from src.scrapers.worker import SourcingEngine

        mock_df = pd.DataFrame([{
            "id": "li-sal-1",
            "title": "Software Engineer Intern",
            "company": "Shopify",
            "description": "Build cool things with Python and Go.",
            "job_url": "https://linkedin.com/jobs/sal-1",
            "site": "linkedin",
            "min_amount": 80000.0,
            "max_amount": 120000.0,
            "currency": "CAD",
            "interval": "yearly",
        }])
        mock_scrape.return_value = mock_df

        mock_repo = AsyncMock()
        mock_repo.get_job.return_value = None

        engine = SourcingEngine(repository=mock_repo)
        await engine.run_sweep("Software Engineer Intern", "Vancouver, BC", results_wanted=5)

        saved: Job = mock_repo.save_job.call_args[0][0]
        assert saved.salary_min == 80000.0
        assert saved.salary_max == 120000.0
        assert saved.salary_currency == "CAD"
        assert saved.salary_interval == "yearly"

    @pytest.mark.asyncio
    @patch("src.scrapers.worker.scrape_jobs")
    async def test_run_sweep_handles_nan_salary(self, mock_scrape):
        """NaN salary columns must be stored as None, not raise an error."""
        import numpy as np
        from src.scrapers.worker import SourcingEngine

        mock_df = pd.DataFrame([{
            "id": "li-nosal-1",
            "title": "Software Engineer Intern",
            "company": "Stripe",
            "description": "Work on payments infrastructure using Go and Python.",
            "job_url": "https://linkedin.com/jobs/nosal-1",
            "site": "linkedin",
            "min_amount": float("nan"),
            "max_amount": float("nan"),
            "currency": None,
            "interval": None,
        }])
        mock_scrape.return_value = mock_df

        mock_repo = AsyncMock()
        mock_repo.get_job.return_value = None

        engine = SourcingEngine(repository=mock_repo)
        await engine.run_sweep("Software Engineer Intern", "Vancouver, BC", results_wanted=5)

        saved: Job = mock_repo.save_job.call_args[0][0]
        assert saved.salary_min is None
        assert saved.salary_max is None

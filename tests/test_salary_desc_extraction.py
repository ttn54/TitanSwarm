"""
Tests for Phase G.2 — Salary Description Fallback Extraction

When JobSpy returns no structured salary (common for LinkedIn jobs that embed
salary text inside the job description body), _extract_salary_from_description()
must scan the description and extract (min, max, currency, interval).

G2-1: Amazon-style annual CAD range  "89,700.00 - 149,800.00 CAD annually"
G2-2: Dollar-sign hourly range       "$21 - $25 an hour"
G2-3: Dollar-sign annual range       "$80,000 - $120,000 per year"
G2-4: No salary in description       → (None, None, "", "")
G2-5: Small numbers not mis-matched  "3-5 years experience" → (None, None, "", "")
G2-6: run_sweep uses the fallback    when JobSpy min_amount/max_amount are NaN
"""
import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch

from src.scrapers.worker import _extract_salary_from_description
from src.core.models import Job


# ═════════════════════════════════════════════════════════════════════════════
# G2-1  Amazon annual CAD
# ═════════════════════════════════════════════════════════════════════════════

def test_amazon_annual_cad():
    """'89,700.00 - 149,800.00 CAD annually' embedded in description body."""
    desc = (
        "CAN, BC, Vancouver - 89,700.00 - 149,800.00 CAD annually\n"
        "Company - Amazon Development Centre Canada ULC"
    )
    sal_min, sal_max, currency, interval = _extract_salary_from_description(desc)
    assert sal_min == 89700.0
    assert sal_max == 149800.0
    assert currency == "CAD"
    assert interval == "yearly"


# ═════════════════════════════════════════════════════════════════════════════
# G2-2  Dollar-sign hourly
# ═════════════════════════════════════════════════════════════════════════════

def test_dollar_hourly_range():
    """'$21 - $25 an hour' (Indeed format)."""
    desc = "The pay rate for this position is $21 - $25 an hour."
    sal_min, sal_max, currency, interval = _extract_salary_from_description(desc)
    assert sal_min == 21.0
    assert sal_max == 25.0
    assert currency == "USD"
    assert interval == "hourly"


# ═════════════════════════════════════════════════════════════════════════════
# G2-3  Dollar-sign annual range
# ═════════════════════════════════════════════════════════════════════════════

def test_dollar_annual_range():
    """'$80,000 - $120,000 per year'"""
    desc = "Compensation: $80,000 - $120,000 per year depending on experience."
    sal_min, sal_max, currency, interval = _extract_salary_from_description(desc)
    assert sal_min == 80000.0
    assert sal_max == 120000.0
    assert currency == "USD"
    assert interval == "yearly"


# ═════════════════════════════════════════════════════════════════════════════
# G2-4  No salary in description
# ═════════════════════════════════════════════════════════════════════════════

def test_no_salary_returns_none():
    """Description with no salary numbers → all None/empty."""
    desc = "We are seeking a passionate software engineer to join our AI team."
    sal_min, sal_max, currency, interval = _extract_salary_from_description(desc)
    assert sal_min is None
    assert sal_max is None
    assert currency == ""
    assert interval == ""


# ═════════════════════════════════════════════════════════════════════════════
# G2-5  Small numbers must not be mis-matched
# ═════════════════════════════════════════════════════════════════════════════

def test_small_numbers_not_matched():
    """'3-5 years of experience' must NOT be extracted as a salary."""
    desc = "Requirements: 3-5 years of experience with Python or Java."
    sal_min, sal_max, currency, interval = _extract_salary_from_description(desc)
    assert sal_min is None
    assert sal_max is None


# ═════════════════════════════════════════════════════════════════════════════
# G2-6  run_sweep integration: uses description fallback when NaN salary
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("src.scrapers.worker.scrape_jobs")
async def test_run_sweep_uses_description_fallback(mock_scrape):
    """
    When JobSpy returns NaN min_amount/max_amount but the description contains
    a salary line, run_sweep must extract and save the salary fields.
    """
    from src.scrapers.worker import SourcingEngine
    import numpy as np

    mock_df = pd.DataFrame([{
        "id": "li-4400244584",
        "title": "Software Development Engineer Internship",
        "company": "Amazon",
        "description": (
            "Build things at Amazon.\n"
            "CAN, BC, Vancouver - 89,700.00 - 149,800.00 CAD annually\n"
            "Company - Amazon Development Centre Canada ULC - K03"
        ),
        "job_url": "https://www.linkedin.com/jobs/view/4400244584",
        "site": "linkedin",
        "location": "Vancouver, BC",
        "date_posted": "2026-04-09",
        "min_amount": float("nan"),
        "max_amount": float("nan"),
        "currency": None,
        "interval": None,
    }])
    mock_scrape.return_value = mock_df

    mock_repo = AsyncMock()
    mock_repo.get_job.return_value = None  # new job

    engine = SourcingEngine(repository=mock_repo, interval_hours=12)
    count, found_ids = await engine.run_sweep(
        role="Software Development Engineer Internship",
        location="Vancouver, BC",
        results_wanted=1,
    )

    assert count == 1
    saved: Job = mock_repo.save_job.call_args[0][0]
    assert saved.salary_min == 89700.0, f"Expected 89700.0, got {saved.salary_min}"
    assert saved.salary_max == 149800.0
    assert saved.salary_currency == "CAD"
    assert saved.salary_interval == "yearly"

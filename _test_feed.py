#!/usr/bin/env python3
"""
End-to-end feed test: mocks JobSpy so no network needed.
Tests two scenarios that previously caused an empty feed:
  1. Jobs where LinkedIn returns NO description (was silently dropped — now saved)
  2. Jobs where description IS present (always worked)
"""
import asyncio, os, sys
import pandas as pd
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_feed.db"

from src.infrastructure.postgres_repo import PostgresRepository
from src.scrapers.worker import SourcingEngine
from src.core.models import JobStatus

# ── Fake scrape payload — mimics what JobSpy returns ─────────────────────────
FAKE_JOBS = pd.DataFrame([
    {   # LinkedIn-style: no description (this was being dropped — the bug)
        "id": "li_001",
        "title": "Software Engineer",
        "company": "Google",
        "location": "Mountain View, CA",
        "job_url": "https://linkedin.com/jobs/1",
        "description": "",          # ← empty description
        "date_posted": "2026-05-01",
        "skills": None,
        "site": "linkedin",
        "min_amount": None, "max_amount": None,
        "currency": None, "interval": None,
    },
    {   # Indeed-style: has description (should always work)
        "id": "ind_002",
        "title": "Software Engineer II",
        "company": "Amazon",
        "location": "Seattle, WA",
        "job_url": "https://indeed.com/jobs/2",
        "description": "We are looking for a Software Engineer to join our team.",
        "date_posted": "2026-05-01",
        "skills": ["Python", "AWS"],
        "site": "indeed",
        "min_amount": 130000.0, "max_amount": 180000.0,
        "currency": "USD", "interval": "yearly",
    },
    {   # Another no-description job (common from LinkedIn)
        "id": "li_003",
        "title": "Senior Software Engineer",
        "company": "Meta",
        "location": "Menlo Park, CA",
        "job_url": "https://linkedin.com/jobs/3",
        "description": None,        # ← None description
        "date_posted": "2026-05-01",
        "skills": None,
        "site": "linkedin",
        "min_amount": None, "max_amount": None,
        "currency": None, "interval": None,
    },
])

async def main():
    # Clean slate
    if os.path.exists("test_feed.db"):
        os.remove("test_feed.db")

    repo = PostgresRepository("sqlite+aiosqlite:///test_feed.db")
    await repo.init_db()
    uid = await repo.create_user("feedtest", "password123")
    print(f"Created test user uid={uid}")

    engine = SourcingEngine(repository=repo)

    # Patch _scrape_df so it returns our fake data instead of hitting the internet
    with patch.object(engine, "_scrape_df", return_value=FAKE_JOBS):
        saved, all_ids = await engine.run_sweep(
            "Software Engineer", "United States", results_wanted=15, user_id=uid
        )

    print(f"run_sweep done → new_saved={saved}, total_ids_returned={len(all_ids)}")

    discovered = await repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=uid)
    print(f"Jobs visible in feed for uid={uid}: {len(discovered)}")

    # ASSERTION: all 3 fake jobs must be in the feed (including the 2 with no description)
    if len(discovered) != 3:
        print(f"FAIL: expected 3 jobs in feed, got {len(discovered)}")
        print("  → Jobs with empty description are still being dropped!")
        sys.exit(1)

    for j in discovered:
        has_desc = bool(j.job_description.strip())
        print(f"  ✓ {j.role} @ {j.company} | description={'present' if has_desc else 'empty (shown anyway)'}")

    print("\nPASS: all 3 jobs in feed, including 2 with no description.")

asyncio.run(main())

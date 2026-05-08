# Phase E.3 — Multi-Tenant Sourcing Daemon

**Date:** 2026-04-14  
**Status:** Implemented  

---

## Scope

Upgrade the Sourcing Daemon from a static, single-user background process into an enterprise-grade multi-tenant worker that autonomously scrapes for every registered user based on their saved job preferences.

---

## Problem Statement

The original daemon read scraping targets from environment variables (`SCRAPER_ROLE`, `SCRAPER_LOCATION`) and saved all jobs with the hardcoded `user_id=1`. This meant:

- A second registered user would never receive background-scraped jobs.
- The daemon ignored every user's "Preferred Role" and "Preferred Location" from their profile.
- Env-var targets were a system-level config, not per-user preferences.

---

## Architecture

```
Every SCRAPER_INTERVAL_HOURS:

  repo.get_all_user_targets()
    → [(user_id=1, "SWE Intern",   "Vancouver, BC"),
       (user_id=2, "ML Engineer",  "Toronto, ON"),
       (user_id=3, "Backend SWE",  "Remote"), ...]

  asyncio.gather(
    run_sweep("SWE Intern",  "Vancouver, BC", user_id=1),
    run_sweep("ML Engineer", "Toronto, ON",   user_id=2),
    run_sweep("Backend SWE", "Remote",        user_id=3),
  )

  Each sweep: save_job(job, user_id=user_id)
    → jobs land in the correct user's isolated feed
```

---

## Feature 1: `get_all_user_targets()`

**New abstract method on `JobRepository` ABC:**
```python
async def get_all_user_targets(self) -> list[tuple[int, str, str]]:
    """Returns (user_id, pref_role, pref_location) for every user
    with a non-empty pref_role in their profile."""
```

**Implementation in `PostgresRepository`:**
```python
async def get_all_user_targets(self):
    rows = await session.execute(
        select(UserProfileModel).where(UserProfileModel.pref_role != "")
    )
    return [(row.user_id, row.pref_role, row.pref_location or "") for row in rows]
```

**Skipped users:** Any user who hasn't saved a profile, or whose `pref_role` is blank, is excluded from the sweep. No wasted API calls.

---

## Feature 2: `user_id` threaded through `run_sweep`

**`src/scrapers/worker.py`:**
```python
async def run_sweep(self, role, location, results_wanted=25, user_id: int = 1):
    ...
    existing = await self.repository.get_job(job_id, user_id=user_id)
    ...
    await self.repository.save_job(job, user_id=user_id)
```

Backward compatible: calling `run_sweep(role, location)` without `user_id` defaults to `user_id=1`.

---

## Feature 3: Dynamic DB targets in `daemon.py`

```python
while True:
    db_targets = await repo.get_all_user_targets()
    if db_targets:
        targets = db_targets          # use live user preferences
    else:
        targets = _fallback_triples   # fall back to env-var config

    total_saved = await _run_concurrent_sweep(engine, targets, results_wanted)
    await asyncio.sleep(interval_hours * 3600)
```

The env-var targets (`SCRAPER_ROLES`, `SCRAPER_LOCATIONS`) remain fully functional as a system-level default — they activate only when no users have saved preferences yet. Env-var pairs are converted to `(user_id=1, role, loc)` triples for format consistency.

---

## `_run_concurrent_sweep` signature change

**Before:** `targets: list[tuple[str, str]]` — (role, location) pairs  
**After:** `targets: list[tuple[int, str, str]]` — (user_id, role, location) triples

Each `_safe_sweep` coroutine now unpacks all three fields and passes `user_id` to `run_sweep`.

---

## Failure Isolation

Each user's sweep runs in its own coroutine inside `asyncio.gather`. If one sweep raises an exception (e.g., LinkedIn rate-limits user 2), the exception is caught, logged as `ERROR`, and user 2 contributes 0 to the total — but users 1, 3, 4... are unaffected.

---

## New Files

- `tests/test_multitenant_daemon.py` — 10 tests

## Modified Files

- `src/core/repository.py` — `get_all_user_targets` abstract method added
- `src/infrastructure/postgres_repo.py` — `get_all_user_targets` implementation
- `src/scrapers/worker.py` — `user_id` param on `run_sweep`; `_scrape_df` helper
- `src/scrapers/daemon.py` — dynamic DB targets; 3-tuple unpacking; `SCRAPER_RESULTS_WANTED` default 25→50
- `src/ui/mock_repo.py` — `get_all_user_targets` stub added
- `tests/test_daemon.py` — 2-tuple targets updated to 3-tuples
- `tests/test_repository.py` — `GoodRepo` stub updated with new abstract method
- `tests/test_sourcing_engine.py` — `get_job` assertion updated to include `user_id=1`

---

## Tests: 10 new in `test_multitenant_daemon.py`

**MT1 — `get_all_user_targets`:**
- `test_returns_empty_when_no_users`
- `test_returns_target_for_user_with_profile`
- `test_skips_user_with_empty_pref_role`
- `test_skips_user_with_no_profile`
- `test_multiple_users_all_returned`

**MT2 — `run_sweep` user isolation:**
- `test_save_job_called_with_correct_user_id`
- `test_get_job_called_with_correct_user_id`
- `test_default_user_id_is_1`

**MT3 — Daemon DB targets:**
- `test_daemon_sweep_uses_user_targets_from_db`
- `test_daemon_sweep_handles_per_user_failure_gracefully`

---

## Running the Daemon

```bash
source .venv/bin/activate
python -m src.scrapers.daemon
```

The daemon connects to `titanswarm.db`, reads all user targets, runs concurrent sweeps, then sleeps for `SCRAPER_INTERVAL_HOURS` (default: 12h). Each user will find new jobs in their feed the next time they open the UI.

"""
Tests for multi-tenant Sourcing Daemon.

MT1 — get_all_user_targets returns (user_id, role, location) for every user
      with a non-empty pref_role in their profile.
MT2 — SourcingEngine.run_sweep threads user_id into every save_job/get_job call.
MT3 — Daemon uses DB targets; env-var targets are a fallback only.
"""
import pytest
import pytest_asyncio
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch, call
from src.infrastructure.postgres_repo import PostgresRepository
from src.core.models import UserProfile


# ═════════════════════════════════════════════════════════════════════════════
# MT1: get_all_user_targets
# ═════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def repo():
    r = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await r.init_db()
    yield r
    await r.close()


class TestGetAllUserTargets:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_users(self, repo):
        """Fresh DB with no users → empty list."""
        targets = await repo.get_all_user_targets()
        assert targets == []

    @pytest.mark.asyncio
    async def test_returns_target_for_user_with_profile(self, repo):
        """User with pref_role + pref_location set → one target tuple returned."""
        uid = await repo.create_user("alice", "password123")
        profile = UserProfile(
            name="Alice",
            email="alice@example.com",
            pref_role="Software Engineer Intern",
            pref_location="Vancouver, BC",
        )
        await repo.save_profile(profile, user_id=uid)

        targets = await repo.get_all_user_targets()
        assert len(targets) == 1
        assert targets[0] == (uid, "Software Engineer Intern", "Vancouver, BC")

    @pytest.mark.asyncio
    async def test_skips_user_with_empty_pref_role(self, repo):
        """User with no pref_role (profile incomplete) → excluded from targets."""
        uid = await repo.create_user("bob", "password123")
        profile = UserProfile(
            name="Bob",
            email="bob@example.com",
            pref_role="",
            pref_location="Toronto, ON",
        )
        await repo.save_profile(profile, user_id=uid)

        targets = await repo.get_all_user_targets()
        assert targets == []

    @pytest.mark.asyncio
    async def test_skips_user_with_no_profile(self, repo):
        """User who never saved a profile → excluded (no row to read)."""
        await repo.create_user("charlie", "password123")
        targets = await repo.get_all_user_targets()
        assert targets == []

    @pytest.mark.asyncio
    async def test_multiple_users_all_returned(self, repo):
        """Three users with profiles → three target tuples, one per user."""
        users = [
            ("u1", "SWE Intern", "Vancouver, BC"),
            ("u2", "ML Engineer", "Toronto, ON"),
            ("u3", "Backend Engineer", "Remote"),
        ]
        uids = {}
        for username, role, loc in users:
            uid = await repo.create_user(username, "pass")
            uids[username] = uid
            await repo.save_profile(
                UserProfile(name=username, email=f"{username}@x.com", pref_role=role, pref_location=loc),
                user_id=uid,
            )

        targets = await repo.get_all_user_targets()
        assert len(targets) == 3
        # Order not guaranteed — check by user_id
        target_map = {uid: (role, loc) for uid, role, loc in targets}
        assert target_map[uids["u1"]] == ("SWE Intern", "Vancouver, BC")
        assert target_map[uids["u2"]] == ("ML Engineer", "Toronto, ON")
        assert target_map[uids["u3"]] == ("Backend Engineer", "Remote")


# ═════════════════════════════════════════════════════════════════════════════
# MT2: run_sweep threads user_id into repo calls
# ═════════════════════════════════════════════════════════════════════════════

class TestRunSweepUserIsolation:
    @pytest.mark.asyncio
    @patch("src.scrapers.worker.scrape_jobs")
    async def test_save_job_called_with_correct_user_id(self, mock_scrape):
        """When run_sweep is called with user_id=42, save_job must receive user_id=42."""
        from src.scrapers.worker import SourcingEngine

        mock_scrape.return_value = pd.DataFrame([{
            "id": "li-999",
            "title": "Software Engineer Intern",
            "company": "Acme",
            "description": "We need a Python backend engineer with 2+ years experience.",
            "job_url": "https://linkedin.com/jobs/999",
            "site": "linkedin",
            "location": "Vancouver, BC",
            "date_posted": "2026-04-14",
            "skills": None,
        }])

        repo = MagicMock()
        repo.get_job = AsyncMock(return_value=None)
        repo.save_job = AsyncMock(return_value=True)

        engine = SourcingEngine(repository=repo)
        await engine.run_sweep("Software Engineer Intern", "Vancouver, BC",
                                results_wanted=5, user_id=42)

        # save_job must be called with user_id=42
        repo.save_job.assert_called_once()
        _, kwargs = repo.save_job.call_args
        assert kwargs.get("user_id") == 42, f"Expected user_id=42, got {kwargs}"

    @pytest.mark.asyncio
    @patch("src.scrapers.worker.scrape_jobs")
    async def test_get_job_called_with_correct_user_id(self, mock_scrape):
        """Dedup check (get_job) must be scoped to the same user_id as the sweep."""
        from src.scrapers.worker import SourcingEngine

        mock_scrape.return_value = pd.DataFrame([{
            "id": "li-888",
            "title": "Software Engineer Intern",
            "company": "Acme",
            "description": "We need a Python backend engineer with 2+ years experience.",
            "job_url": "https://linkedin.com/jobs/888",
            "site": "linkedin",
            "location": "Vancouver, BC",
            "date_posted": "2026-04-14",
            "skills": None,
        }])

        repo = MagicMock()
        repo.get_job = AsyncMock(return_value=None)
        repo.save_job = AsyncMock(return_value=True)

        engine = SourcingEngine(repository=repo)
        await engine.run_sweep("Software Engineer Intern", "Vancouver, BC",
                                results_wanted=5, user_id=7)

        repo.get_job.assert_called()
        _, kwargs = repo.get_job.call_args
        assert kwargs.get("user_id") == 7, f"Expected user_id=7 in get_job, got {kwargs}"

    @pytest.mark.asyncio
    @patch("src.scrapers.worker.scrape_jobs")
    async def test_default_user_id_is_1(self, mock_scrape):
        """Calling run_sweep without user_id defaults to user_id=1 (backward compat)."""
        from src.scrapers.worker import SourcingEngine

        mock_scrape.return_value = pd.DataFrame([{
            "id": "li-777",
            "title": "Software Engineer Intern",
            "company": "Acme",
            "description": "We need a Python backend engineer with 2+ years experience.",
            "job_url": "https://linkedin.com/jobs/777",
            "site": "linkedin",
            "location": "Vancouver, BC",
            "date_posted": "2026-04-14",
            "skills": None,
        }])

        repo = MagicMock()
        repo.get_job = AsyncMock(return_value=None)
        repo.save_job = AsyncMock(return_value=True)

        engine = SourcingEngine(repository=repo)
        await engine.run_sweep("Software Engineer Intern", "Vancouver, BC", results_wanted=5)

        _, kwargs = repo.save_job.call_args
        assert kwargs.get("user_id") == 1


# ═════════════════════════════════════════════════════════════════════════════
# MT3: Daemon uses DB targets
# ═════════════════════════════════════════════════════════════════════════════

class TestDaemonUsesDBTargets:
    @pytest.mark.asyncio
    async def test_daemon_sweep_uses_user_targets_from_db(self):
        """
        _run_concurrent_sweep must call engine.run_sweep once per (user_id, role, loc)
        tuple with the correct user_id threaded through.
        """
        from src.scrapers.daemon import _run_concurrent_sweep
        from src.scrapers.worker import SourcingEngine

        engine = MagicMock(spec=SourcingEngine)
        engine.run_sweep = AsyncMock(return_value=(3, ["job-1", "job-2", "job-3"]))

        targets = [
            (1, "SWE Intern", "Vancouver, BC"),
            (2, "ML Engineer", "Toronto, ON"),
        ]
        total = await _run_concurrent_sweep(engine, targets, results_wanted=50)

        assert total == 6  # 3 + 3
        assert engine.run_sweep.call_count == 2

        calls_kwargs = [c.kwargs for c in engine.run_sweep.call_args_list]
        user_ids_used = {kw["user_id"] for kw in calls_kwargs}
        assert user_ids_used == {1, 2}

    @pytest.mark.asyncio
    async def test_daemon_sweep_handles_per_user_failure_gracefully(self):
        """One user's sweep failing must not prevent other users' sweeps from running."""
        from src.scrapers.daemon import _run_concurrent_sweep
        from src.scrapers.worker import SourcingEngine

        engine = MagicMock(spec=SourcingEngine)

        async def _side_effect(role, location, results_wanted, user_id):
            if user_id == 2:
                raise RuntimeError("LinkedIn rate limit")
            return (5, [])

        engine.run_sweep = AsyncMock(side_effect=_side_effect)

        targets = [(1, "SWE Intern", "Vancouver, BC"), (2, "ML Engineer", "Toronto, ON")]
        total = await _run_concurrent_sweep(engine, targets, results_wanted=50)

        # User 1 succeeded → 5 jobs. User 2 failed → 0. Total = 5.
        assert total == 5

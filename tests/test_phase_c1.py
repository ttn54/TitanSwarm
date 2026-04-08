"""
Tests for Phase C.1: Fix All Broken UX + Kanban Actions

B1 — Filter chip logic correctly filters jobs
B2+B3 — Profile completion counts website, field exists
B4 — Sidebar stats include interview count
B5+M4 — Kanban buttons exist for each lane
B6 — Job preferences (pref_role, pref_location) persist via UserProfile
"""
import pytest
import pytest_asyncio
from src.core.models import Job, JobStatus, UserProfile
from src.infrastructure.postgres_repo import PostgresRepository


@pytest_asyncio.fixture
async def repo():
    r = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await r.init_db()
    yield r
    await r.close()


# ═════════════════════════════════════════════════════════════════════════════
# B1: Filter chip logic
# ═════════════════════════════════════════════════════════════════════════════
class TestFilterChips:
    """
    The filter chip logic lives in app.py, but the filtering function should be
    extractable and testable. We test the filtering predicate directly.
    """

    def _make_job(self, role: str, desc: str) -> Job:
        return Job(
            id=f"fc-{hash(role+desc)}",
            company="TestCo",
            role=role,
            job_description=desc,
            url="https://example.com/job",
        )

    def test_filter_all_returns_everything(self):
        from src.ui.app import filter_jobs
        jobs = [
            self._make_job("SWE Intern", "Remote internship"),
            self._make_job("Backend Engineer", "Full-time on-site"),
        ]
        assert len(filter_jobs(jobs, "All")) == 2

    def test_filter_remote(self):
        from src.ui.app import filter_jobs
        jobs = [
            self._make_job("SWE Intern", "This is a remote position"),
            self._make_job("Backend Engineer", "On-site in NYC"),
        ]
        result = filter_jobs(jobs, "Remote")
        assert len(result) == 1
        assert result[0].role == "SWE Intern"

    def test_filter_internship(self):
        from src.ui.app import filter_jobs
        jobs = [
            self._make_job("SWE Intern", "Summer program"),
            self._make_job("Internship: ML", "Join our ML team"),
            self._make_job("Senior SWE", "Full-time senior role"),
        ]
        result = filter_jobs(jobs, "Internship")
        assert len(result) == 2

    def test_filter_fulltime(self):
        from src.ui.app import filter_jobs
        jobs = [
            self._make_job("SWE", "This is a full-time position"),
            self._make_job("SWE", "Full time role available"),
            self._make_job("SWE Intern", "Summer internship"),
        ]
        result = filter_jobs(jobs, "Full-time")
        assert len(result) == 2

    def test_filter_coop(self):
        from src.ui.app import filter_jobs
        jobs = [
            self._make_job("SWE Co-op", "8 month co-op at Google"),
            self._make_job("SWE Coop", "Standard coop term"),
            self._make_job("SWE Intern", "Summer internship"),
        ]
        result = filter_jobs(jobs, "Co-op")
        assert len(result) == 2

    def test_filter_none_returns_all(self):
        from src.ui.app import filter_jobs
        jobs = [self._make_job("SWE", "whatever")]
        assert len(filter_jobs(jobs, None)) == 1


# ═════════════════════════════════════════════════════════════════════════════
# B2+B3: Profile completion counts website
# ═════════════════════════════════════════════════════════════════════════════
class TestProfileCompletion:
    def test_full_profile_is_100_percent(self):
        from src.ui.app import profile_completion
        pf = UserProfile(
            name="Zen",
            email="z@sfu.ca",
            github="github.com/ttn54",
            skills=["Python"],
            base_summary="CS student",
            website="zennguyen.me",
        )
        assert profile_completion(pf) == 1.0

    def test_missing_website_is_not_100(self):
        from src.ui.app import profile_completion
        pf = UserProfile(
            name="Zen",
            email="z@sfu.ca",
            github="github.com/ttn54",
            skills=["Python"],
            base_summary="CS student",
            # website missing
        )
        pct = profile_completion(pf)
        assert pct < 1.0
        # 5 out of 6 filled
        assert abs(pct - 5 / 6) < 0.01

    def test_empty_profile_is_zero(self):
        from src.ui.app import profile_completion
        pf = UserProfile()
        assert profile_completion(pf) == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# B6: Job preferences persist via UserProfile
# ═════════════════════════════════════════════════════════════════════════════
class TestPreferencesPersistence:
    @pytest.mark.asyncio
    async def test_pref_role_survives_round_trip(self, repo):
        profile = UserProfile(
            name="Zen",
            pref_role="Machine Learning Engineer",
            pref_location="San Francisco",
        )
        await repo.save_profile(profile)
        loaded = await repo.get_profile()
        assert loaded is not None
        assert loaded.pref_role == "Machine Learning Engineer"
        assert loaded.pref_location == "San Francisco"

    @pytest.mark.asyncio
    async def test_pref_defaults_to_empty(self, repo):
        profile = UserProfile(name="Zen")
        await repo.save_profile(profile)
        loaded = await repo.get_profile()
        assert loaded.pref_role == ""
        assert loaded.pref_location == ""

    @pytest.mark.asyncio
    async def test_pref_update_overwrites(self, repo):
        p1 = UserProfile(name="Zen", pref_role="SWE Intern", pref_location="Vancouver")
        await repo.save_profile(p1)

        p2 = UserProfile(name="Zen", pref_role="Backend Engineer", pref_location="Remote")
        await repo.save_profile(p2)

        loaded = await repo.get_profile()
        assert loaded.pref_role == "Backend Engineer"
        assert loaded.pref_location == "Remote"

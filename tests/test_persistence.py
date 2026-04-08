"""
Tests for Phase B: Persist State to DB
B1 — UserProfile persistence (save + load survives restart)
B2 — required_skills + custom_questions survive DB round-trip
B3 — TailoredResult (AI JSON + PDF bytes) persistence
B4 — INTERVIEW status in enum + badge mapping
"""
import pytest
import pytest_asyncio
import json
from src.core.models import Job, JobStatus, UserProfile, TailoredApplication
from src.infrastructure.postgres_repo import PostgresRepository


@pytest_asyncio.fixture
async def repo():
    r = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await r.init_db()
    yield r
    await r.close()


# ═════════════════════════════════════════════════════════════════════════════
# B1: UserProfile persistence
# ═════════════════════════════════════════════════════════════════════════════
class TestProfilePersistence:
    @pytest.mark.asyncio
    async def test_save_and_get_profile(self, repo):
        profile = UserProfile(
            name="Zen Nguyen",
            email="ttn54@sfu.ca",
            phone="(672) 673-2613",
            github="github.com/ttn54",
            linkedin="linkedin.com/in/zennguyen1305",
            website="zennguyen.me",
        )
        ok = await repo.save_profile(profile)
        assert ok is True

        loaded = await repo.get_profile()
        assert loaded is not None
        assert loaded.name == "Zen Nguyen"
        assert loaded.email == "ttn54@sfu.ca"
        assert loaded.website == "zennguyen.me"
        assert loaded.github == "github.com/ttn54"

    @pytest.mark.asyncio
    async def test_get_profile_returns_none_when_empty(self, repo):
        loaded = await repo.get_profile()
        assert loaded is None

    @pytest.mark.asyncio
    async def test_save_profile_overwrites_existing(self, repo):
        p1 = UserProfile(name="Old Name", email="old@test.com")
        await repo.save_profile(p1)

        p2 = UserProfile(name="New Name", email="new@test.com", website="new.me")
        await repo.save_profile(p2)

        loaded = await repo.get_profile()
        assert loaded.name == "New Name"
        assert loaded.email == "new@test.com"
        assert loaded.website == "new.me"


# ═════════════════════════════════════════════════════════════════════════════
# B2: Job skills + questions survive round-trip
# ═════════════════════════════════════════════════════════════════════════════
class TestJobSkillsPersistence:
    @pytest.mark.asyncio
    async def test_skills_survive_round_trip(self, repo):
        job = Job(
            id="sk-1",
            company="Google",
            role="SWE Intern",
            job_description="Build stuff",
            url="https://google.com/job/1",
            required_skills=["Python", "Go", "Docker"],
            custom_questions=["Why Google?", "Visa status?"],
        )
        await repo.save_job(job)

        loaded = await repo.get_job("sk-1")
        assert loaded is not None
        assert loaded.required_skills == ["Python", "Go", "Docker"]
        assert loaded.custom_questions == ["Why Google?", "Visa status?"]

    @pytest.mark.asyncio
    async def test_empty_skills_round_trip(self, repo):
        job = Job(
            id="sk-2",
            company="Meta",
            role="SWE",
            job_description="Build more stuff",
            url="https://meta.com/job/2",
        )
        await repo.save_job(job)

        loaded = await repo.get_job("sk-2")
        assert loaded.required_skills == []
        assert loaded.custom_questions == []

    @pytest.mark.asyncio
    async def test_skills_in_status_query(self, repo):
        job = Job(
            id="sk-3",
            company="Apple",
            role="iOS",
            job_description="Swift",
            url="https://apple.com/3",
            required_skills=["Swift", "UIKit"],
            status=JobStatus.DISCOVERED,
        )
        await repo.save_job(job)

        jobs = await repo.get_jobs_by_status(JobStatus.DISCOVERED)
        assert len(jobs) == 1
        assert jobs[0].required_skills == ["Swift", "UIKit"]


# ═════════════════════════════════════════════════════════════════════════════
# B3: Tailored result persistence
# ═════════════════════════════════════════════════════════════════════════════
class TestTailoredResultPersistence:
    @pytest.mark.asyncio
    async def test_save_and_get_tailored_result(self, repo):
        ai_json = '{"job_id":"t1","skills_to_highlight":{},"tailored_projects":[],"tailored_experience":[]}'
        pdf_data = b"%PDF-1.4 fake pdf content"

        ok = await repo.save_tailored_result("t1", ai_json, pdf_data)
        assert ok is True

        result = await repo.get_tailored_result("t1")
        assert result is not None
        loaded_json, loaded_pdf, loaded_cl = result
        assert loaded_json == ai_json
        assert loaded_pdf == pdf_data
        assert loaded_cl is None

    @pytest.mark.asyncio
    async def test_get_tailored_result_returns_none_when_missing(self, repo):
        result = await repo.get_tailored_result("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite_tailored_result(self, repo):
        await repo.save_tailored_result("t2", '{"v":1}', b"old")
        await repo.save_tailored_result("t2", '{"v":2}', b"new")

        result = await repo.get_tailored_result("t2")
        loaded_json, loaded_pdf, loaded_cl = result
        assert loaded_json == '{"v":2}'
        assert loaded_pdf == b"new"


# ═════════════════════════════════════════════════════════════════════════════
# B4: INTERVIEW status exists
# ═════════════════════════════════════════════════════════════════════════════
class TestInterviewStatus:
    def test_interview_status_exists(self):
        assert hasattr(JobStatus, "INTERVIEW"), "JobStatus must have an INTERVIEW member"
        assert JobStatus.INTERVIEW.value == "INTERVIEW"

    @pytest.mark.asyncio
    async def test_interview_status_round_trip(self, repo):
        job = Job(
            id="iv-1",
            company="Stripe",
            role="SWE",
            job_description="Payments",
            url="https://stripe.com/1",
            status=JobStatus.DISCOVERED,
        )
        await repo.save_job(job)
        await repo.update_status("iv-1", JobStatus.INTERVIEW)

        loaded = await repo.get_job("iv-1")
        assert loaded.status == JobStatus.INTERVIEW

"""
Tests for Phase C.2: Cover Letter + Match Score + Search/Sort

M2 — Match score computation (cosine similarity scaled 0–100)
M1 — Cover letter persistence (save + load round-trip)
M3 — Search/sort helper functions
"""
import pytest
import pytest_asyncio
import numpy as np
from src.core.models import Job, JobStatus
from src.infrastructure.postgres_repo import PostgresRepository


# ═════════════════════════════════════════════════════════════════════════════
# M2: Match Score
# ═════════════════════════════════════════════════════════════════════════════
class TestMatchScore:
    def test_identical_texts_score_high(self):
        from src.core.matching import compute_match_score
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        score = compute_match_score(
            "Python backend engineer with distributed systems experience",
            "Python backend engineer with distributed systems experience",
            model,
        )
        assert score >= 90

    def test_unrelated_texts_score_low(self):
        from src.core.matching import compute_match_score
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        score = compute_match_score(
            "Professional cake decorator with fondant expertise",
            "Machine learning engineer building transformer architectures in PyTorch",
            model,
        )
        assert score < 50

    def test_score_clamped_0_to_100(self):
        from src.core.matching import compute_match_score
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        score = compute_match_score("a", "b", model)
        assert 0 <= score <= 100

    def test_related_texts_score_moderate(self):
        from src.core.matching import compute_match_score
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        score = compute_match_score(
            "Python developer building web APIs with Flask and PostgreSQL",
            "Backend engineer needed: Node.js, REST APIs, SQL databases",
            model,
        )
        # Related but different tech stack — hybrid intentionally penalises
        # keyword mismatch (Python/Flask ≠ Node.js/SQL), so lower bound is 20.
        assert 20 <= score <= 85

    def test_empty_resume_returns_zero(self):
        from src.core.matching import compute_match_score
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        score = compute_match_score("", "Python engineer", model)
        assert score == 0


# ═════════════════════════════════════════════════════════════════════════════
# M1: Cover Letter Persistence
# ═════════════════════════════════════════════════════════════════════════════
@pytest_asyncio.fixture
async def repo():
    r = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await r.init_db()
    yield r
    await r.close()


class TestCoverLetterPersistence:
    @pytest.mark.asyncio
    async def test_save_and_get_cover_letter(self, repo):
        """Cover letter text survives round-trip through DB."""
        cl_text = "Dear Hiring Manager,\n\nI am excited to apply..."
        ok = await repo.save_tailored_result(
            "job-1", '{"job_id": "job-1"}', b"pdf-bytes",
            cover_letter="Dear Hiring Manager,\n\nI am excited to apply...",
        )
        assert ok is True
        result = await repo.get_tailored_result("job-1")
        assert result is not None
        ai_json, pdf_bytes, cover_letter = result
        assert cover_letter == cl_text

    @pytest.mark.asyncio
    async def test_get_without_cover_letter(self, repo):
        """Jobs tailored without cover letter return None for that field."""
        await repo.save_tailored_result("job-2", '{}', b"pdf")
        result = await repo.get_tailored_result("job-2")
        assert result is not None
        ai_json, pdf_bytes, cover_letter = result
        assert cover_letter is None

    @pytest.mark.asyncio
    async def test_update_adds_cover_letter(self, repo):
        """Upserting with cover letter updates existing row."""
        await repo.save_tailored_result("job-3", '{}', b"pdf")
        await repo.save_tailored_result(
            "job-3", '{}', b"pdf", cover_letter="New CL text"
        )
        result = await repo.get_tailored_result("job-3")
        _, _, cover_letter = result
        assert cover_letter == "New CL text"


# ═════════════════════════════════════════════════════════════════════════════
# M3: Search helper
# ═════════════════════════════════════════════════════════════════════════════
class TestSearchJobs:
    def _make_job(self, company: str, role: str) -> Job:
        return Job(
            id=f"s-{hash(company+role)}",
            company=company,
            role=role,
            job_description="desc",
            url="https://example.com",
        )

    def test_search_by_company(self):
        from src.ui.app import search_jobs
        jobs = [
            self._make_job("Google", "SWE Intern"),
            self._make_job("Meta", "Backend Engineer"),
            self._make_job("Google", "ML Engineer"),
        ]
        result = search_jobs(jobs, "google")
        assert len(result) == 2

    def test_search_by_role(self):
        from src.ui.app import search_jobs
        jobs = [
            self._make_job("Google", "SWE Intern"),
            self._make_job("Meta", "SWE Intern"),
            self._make_job("Apple", "Designer"),
        ]
        result = search_jobs(jobs, "swe")
        assert len(result) == 2

    def test_empty_search_returns_all(self):
        from src.ui.app import search_jobs
        jobs = [self._make_job("Google", "SWE")]
        assert len(search_jobs(jobs, "")) == 1
        assert len(search_jobs(jobs, None)) == 1

    def test_no_match_returns_empty(self):
        from src.ui.app import search_jobs
        jobs = [self._make_job("Google", "SWE")]
        assert len(search_jobs(jobs, "zzzzz")) == 0

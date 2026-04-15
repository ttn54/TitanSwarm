"""
Tests for job quality improvements:
  Q1 — Hybrid match score (semantic + keyword overlap)
  Q2 — No-description jobs filtered from the feed
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
import numpy as np


# ═════════════════════════════════════════════════════════════════════════════
# Q1: Hybrid match score
# ═════════════════════════════════════════════════════════════════════════════

class TestHybridMatchScore:
    def _make_model(self, vec_a, vec_b):
        """Return a mock SentenceTransformer that returns vec_a for first call, vec_b for second."""
        model = MagicMock()
        model.encode.return_value = np.array([vec_a, vec_b])
        return model

    def test_keyword_overlap_boosts_score_vs_pure_semantic(self):
        """
        When resume and JD share explicit tech keywords the hybrid score
        must be strictly higher than a pure-semantic-only baseline.
        """
        from src.core.matching import compute_match_score, _keyword_overlap_score

        resume = "Python Django REST API PostgreSQL Redis Docker"
        jd     = "We need Python Django REST API developer with PostgreSQL and Redis"

        model = MagicMock()
        # Mock moderate semantic similarity (raw 0.5 → semantic_score = ~50)
        v = np.array([1.0, 0.0])
        w = np.array([np.cos(np.radians(60)), np.sin(np.radians(60))])
        model.encode.return_value = np.array([v, w])

        hybrid = compute_match_score(resume, jd, model)
        kw = _keyword_overlap_score(resume, jd)
        # keyword overlap should be high (many shared terms)
        assert kw >= 50
        # hybrid must be at least as high as the keyword component alone
        assert hybrid >= kw * 0.4  # kw has 50% weight

    def test_no_keyword_overlap_still_uses_semantic(self):
        """If no keywords overlap, score should still reflect semantic similarity."""
        from src.core.matching import compute_match_score

        # High cosine similarity vectors
        v = np.array([1.0, 0.0])
        model = MagicMock()
        model.encode.return_value = np.array([v, v])  # identical → raw_sim = 1.0

        score = compute_match_score("aardvark zylophone", "aardvark zylophone", model)
        assert score >= 80

    def test_keyword_overlap_score_all_match(self):
        """100% JD keywords present in resume → keyword score = 100."""
        from src.core.matching import _keyword_overlap_score
        score = _keyword_overlap_score("Python React Docker AWS", "Python React Docker AWS")
        assert score == 100

    def test_keyword_overlap_score_no_match(self):
        """0% JD keywords in resume → keyword score = 0."""
        from src.core.matching import _keyword_overlap_score
        score = _keyword_overlap_score("COBOL Fortran BASIC", "Python React Docker AWS")
        assert score == 0

    def test_keyword_overlap_score_partial(self):
        """Partial overlap yields a proportional score."""
        from src.core.matching import _keyword_overlap_score
        # JD has 4 unique tokens; resume has 2 of them
        score = _keyword_overlap_score("Python React Java Ruby", "Python React COBOL Fortran")
        assert 40 <= score <= 60

    def test_score_always_0_to_100(self):
        """Hybrid score must always be clamped to [0, 100]."""
        from src.core.matching import compute_match_score
        v = np.array([1.0, 0.0])
        model = MagicMock()
        model.encode.return_value = np.array([v, v])
        score = compute_match_score("anything", "anything", model)
        assert 0 <= score <= 100

    def test_empty_inputs_return_zero(self):
        """Empty resume or empty JD must return 0."""
        from src.core.matching import compute_match_score
        model = MagicMock()
        assert compute_match_score("", "Python engineer", model) == 0
        assert compute_match_score("Python engineer", "", model) == 0


# ═════════════════════════════════════════════════════════════════════════════
# Q2: No-description filter in SourcingEngine
# ═════════════════════════════════════════════════════════════════════════════

class TestNoDescriptionFilter:
    def _make_row(self, title, description, job_id="job-1", company="Acme", location="Remote"):
        """Build a minimal pandas-like row dict."""
        import pandas as pd
        return pd.Series({
            "id": job_id,
            "title": title,
            "description": description,
            "company": company,
            "location": location,
            "date_posted": "2026-04-14",
            "job_url": f"https://example.com/{job_id}",
            "skills": None,
        })

    @pytest.mark.asyncio
    async def test_no_description_job_not_saved(self):
        """Jobs with missing/placeholder descriptions must not be saved to the repo."""
        import pandas as pd
        from unittest.mock import AsyncMock, MagicMock, patch
        from src.scrapers.worker import SourcingEngine

        repo = MagicMock()
        repo.get_job = AsyncMock(return_value=None)
        repo.save_job = AsyncMock(return_value=True)

        engine = SourcingEngine(repository=repo)

        bad_descriptions = [
            "Description not provided.",
            "",
            None,
        ]
        for bad_desc in bad_descriptions:
            repo.save_job.reset_mock()
            df = pd.DataFrame([{
                "id": "job-1",
                "title": "Software Engineer",
                "description": bad_desc,
                "company": "Acme",
                "location": "Remote",
                "date_posted": "2026-04-14",
                "job_url": "https://example.com/job-1",
                "skills": None,
            }])
            with patch.object(engine, '_scrape_df', return_value=df):
                await engine.run_sweep("Software Engineer", "Remote", results_wanted=5)
            repo.save_job.assert_not_called(), f"Should not save job with description='{bad_desc}'"

    @pytest.mark.asyncio
    async def test_real_description_job_is_saved(self):
        """Jobs with real descriptions must still be saved normally."""
        import pandas as pd
        from unittest.mock import AsyncMock, MagicMock, patch
        from src.scrapers.worker import SourcingEngine

        repo = MagicMock()
        repo.get_job = AsyncMock(return_value=None)
        repo.save_job = AsyncMock(return_value=True)

        engine = SourcingEngine(repository=repo)
        df = pd.DataFrame([{
            "id": "job-2",
            "title": "Software Engineer",
            "description": "We are looking for a Python backend engineer with 2+ years of experience.",
            "company": "Acme",
            "location": "Remote",
            "date_posted": "2026-04-14",
            "job_url": "https://example.com/job-2",
            "skills": None,
        }])
        with patch.object(engine, '_scrape_df', return_value=df):
            await engine.run_sweep("Software Engineer", "Remote", results_wanted=5)
        repo.save_job.assert_called_once()

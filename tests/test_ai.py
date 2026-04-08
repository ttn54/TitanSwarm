import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from src.core.models import Job, JobStatus, TailoredApplication, TailoredProject
from src.core.ai import AITailor
from src.core.ledger import LedgerManager

@pytest.fixture
def sample_job():
    return Job(
        id="job_999",
        company="Google",
        role="Software Engineer Intern",
        status=JobStatus.DISCOVERED,
        job_description="We are looking for Python and Distributed Systems experience.",
        required_skills=["Python", "Go"],
        custom_questions=["Why do you want to work here?"],
        url="https://google.com/jobs/999"
    )

def test_missing_api_key_raises_error():
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=True):
        mock_ledger = MagicMock(spec=LedgerManager)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            AITailor(ledger_manager=mock_ledger)

@pytest.mark.asyncio
async def test_ai_tailor_returns_structured_output(sample_job):
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake_test_key"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = "data/ledger.md"
        mock_ledger.search_facts.return_value = [
            "Zen wrote TitanSwarm in Python.",
            "Zen built TitanStore with Go."
        ]

        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

        mock_response = TailoredApplication(
            job_id="job_999",
            summary="A driven SWE intern with Python and distributed systems experience.",
            skills_to_highlight=["Python", "Go", "Distributed Systems", "FAISS"],
            tailored_projects=[
                TailoredProject(
                    title="TitanStore",
                    tech="Go, SQL, Docker",
                    date="Jan 2026 – Present",
                    bullets=[
                        "Built distributed KV store in Go using Raft consensus.",
                        "Applied TDD with go test -race for thread safety.",
                    ]
                )
            ],
            q_and_a_responses={"Why do you want to work here?": "I love distributed systems."}
        )

        with patch.object(tailor, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            result = await tailor.tailor_application(sample_job)

            assert isinstance(result, TailoredApplication)
            assert result.job_id == "job_999"
            assert len(result.tailored_projects) == 1
            assert result.tailored_projects[0].title == "TitanStore"
            assert len(result.skills_to_highlight) >= 1
            assert result.summary != ""
            mock_call.assert_called_once()

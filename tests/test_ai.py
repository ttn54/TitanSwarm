import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from src.core.models import Job, JobStatus, TailoredApplication
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
    # Ensure a missing key raises ValueError regardless of provider
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=True):
        mock_ledger = MagicMock(spec=LedgerManager)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            AITailor(ledger_manager=mock_ledger)

@pytest.mark.asyncio
async def test_ai_tailor_returns_structured_output(sample_job):
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake_test_key"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.search_facts.return_value = [
            "Zen wrote TitanSwarm in Python.",
            "Zen built TitanStore with Go."
        ]

        # Patch out Gemini Client construction so no real HTTP call is made
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

        # Mock the unified _call_llm so no real API call is made during test
        mock_response = TailoredApplication(
            job_id="job_999",
            tailored_bullets=["Developed TitanSwarm using Python.", "Built TitanStore distributed DB using Go."],
            q_and_a_responses={"Why do you want to work here?": "I love distributed systems."}
        )
        
        with patch.object(tailor, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            
            result = await tailor.tailor_application(sample_job)
            
            assert isinstance(result, TailoredApplication)
            assert result.job_id == "job_999"
            assert len(result.tailored_bullets) == 2
            assert "Python" in result.tailored_bullets[0]
            
            # Verify the AI was fed the scraped job description and our vault's facts
            mock_ledger.search_facts.assert_called_once()

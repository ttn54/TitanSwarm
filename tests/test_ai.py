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
    # Make sure we don't accidentally have a real key during this test
    with patch.dict(os.environ, clear=True):
        mock_ledger = MagicMock(spec=LedgerManager)
        
        with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is not set"):
            AITailor(ledger_manager=mock_ledger)

@pytest.mark.asyncio
async def test_ai_tailor_returns_structured_output(sample_job):
    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake_test_key"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.search_facts.return_value = [
            "Zen wrote TitanSwarm in Python.",
            "Zen built TitanStore with Go."
        ]
        
        tailor = AITailor(ledger_manager=mock_ledger)
        
        # We need to mock the OpenAI client so we don't make real web requests in our tests
        # We simulate the exact response structure we expect Pydantic to parse
        mock_response = TailoredApplication(
            job_id="job_999",
            tailored_bullets=["Developed TitanSwarm using Python.", "Built TitanStore distributed DB using Go."],
            q_and_a_responses={"Why do you want to work here?": "I love distributed systems."}
        )
        
        with patch.object(tailor, '_call_openai', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            
            result = await tailor.tailor_application(sample_job)
            
            assert isinstance(result, TailoredApplication)
            assert result.job_id == "job_999"
            assert len(result.tailored_bullets) == 2
            assert "Python" in result.tailored_bullets[0]
            
            # Verify the AI was fed the scraped job description and our vault's facts
            mock_ledger.search_facts.assert_called_once()

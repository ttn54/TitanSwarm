import pytest
from pydantic import ValidationError

# We are testing the models before they are implemented
from src.core.models import Job, JobStatus

def test_job_model_creation():
    job = Job(
        id="hash-1234",
        company="TechCorp",
        role="Fall 2026 SWE Co-op",
        job_description="Do things.",
        url="https://example.com/job"
    )
    
    # Defaults should be applied
    assert job.status == JobStatus.DISCOVERED
    assert job.required_skills == []
    assert job.custom_questions == []

def test_job_requires_id():
    with pytest.raises(ValidationError):
        Job(
            company="BadCorp",
            role="SWE",
            job_description="Missing ID",
            url="https://example.com"
        )

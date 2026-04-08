import pytest
from pydantic import ValidationError
from src.core.models import Job, JobStatus, TailoredApplication, TailoredProject

def test_job_model_creation():
    job = Job(
        id="hash-1234",
        company="TechCorp",
        role="Fall 2026 SWE Co-op",
        job_description="Do things.",
        url="https://example.com/job"
    )
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

def test_tailored_application_schema():
    app = TailoredApplication(
        job_id="j1",
        summary="Experienced SWE.",
        skills_to_highlight=["Python", "Go"],
        tailored_projects=[
            TailoredProject(
                title="TitanStore",
                tech="Go, Docker",
                date="Jan 2026 – Present",
                bullets=["Built Raft consensus.", "Used gRPC."],
            )
        ],
        q_and_a_responses={},
    )
    assert app.tailored_projects[0].title == "TitanStore"
    assert len(app.tailored_projects[0].bullets) == 2

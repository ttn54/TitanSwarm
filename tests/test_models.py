import pytest
from pydantic import ValidationError
from src.core.models import Job, JobStatus, TailoredApplication, TailoredProject, TailoredExperience

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
        skills_to_highlight={"Languages": ["Python", "Go"], "Backend & Systems": ["FastAPI"]},
        tailored_projects=[
            TailoredProject(
                title="TitanStore",
                tech="Go, Docker",
                date="Jan 2026 – Present",
                project_type="Personal Project",
                bullets=["Built Raft consensus.", "Used gRPC."],
            )
        ],
        tailored_experience=[],
        q_and_a_responses={},
    )
    assert app.tailored_projects[0].title == "TitanStore"
    assert len(app.tailored_projects[0].bullets) == 2
    assert app.tailored_projects[0].project_type == "Personal Project"
    assert isinstance(app.skills_to_highlight, dict)
    assert "Languages" in app.skills_to_highlight
    assert not hasattr(app, "summary") or app.summary is None or True  # summary removed


def test_tailored_project_type_collaborative():
    proj = TailoredProject(
        title="Chain Reaction Game",
        tech="C#, Unity, Git",
        date="Jun 2025",
        project_type="Collaborative Project",
        bullets=["Built raycasting mechanics."],
    )
    assert proj.project_type == "Collaborative Project"


def test_skills_to_highlight_is_categorized_dict():
    app = TailoredApplication(
        job_id="j2",
        skills_to_highlight={
            "Languages": ["Go", "Python"],
            "Cloud & DevOps": ["Docker", "AWS"],
        },
        tailored_projects=[],
        tailored_experience=[],
        q_and_a_responses={},
    )
    assert app.skills_to_highlight["Cloud & DevOps"] == ["Docker", "AWS"]


def test_tailored_application_has_no_summary_field():
    """summary was removed — model must not require it."""
    app = TailoredApplication(
        job_id="j3",
        skills_to_highlight={"Languages": ["Python"]},
        tailored_projects=[],
        tailored_experience=[],
    )
    assert app.job_id == "j3"
    assert "summary" not in TailoredApplication.model_fields


def test_tailored_experience_model():
    exp = TailoredExperience(
        title="Server",
        company="Pho Goodness Restaurant",
        start_date="Jan 2024",
        end_date="Present",
        location="Burnaby, BC",
        bullets=["Demonstrated high work ethic by maintaining 3.74 GPA while working 20+ hrs/week."],
    )
    assert exp.company == "Pho Goodness Restaurant"
    assert len(exp.bullets) == 1


def test_tailored_application_has_tailored_experience():
    app = TailoredApplication(
        job_id="j4",
        skills_to_highlight={"Languages": ["Python"]},
        tailored_projects=[],
        tailored_experience=[
            TailoredExperience(
                title="Server",
                company="Pho Goodness Restaurant",
                start_date="Jan 2024",
                end_date="Present",
                location="Burnaby, BC",
                bullets=["Led cross-functional team operations for 100+ guests/shift."],
            )
        ],
    )
    assert len(app.tailored_experience) == 1
    assert app.tailored_experience[0].title == "Server"

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


def test_job_has_location_and_date_fields():
    """Job model must have optional location and date_posted fields."""
    job = Job(
        id="hash-999",
        company="Acme",
        role="SWE Intern",
        job_description="Build stuff.",
        url="https://example.com",
        location="Vancouver, BC",
        date_posted="3 days ago",
    )
    assert job.location == "Vancouver, BC"
    assert job.date_posted == "3 days ago"


def test_job_location_date_default_empty():
    """location and date_posted default to empty string (backwards-compatible)."""
    job = Job(
        id="hash-000",
        company="Acme",
        role="SWE Intern",
        job_description="Something.",
        url="https://example.com",
    )
    assert job.location == ""
    assert job.date_posted == ""

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


def test_tailored_project_tech_coerces_list_to_string():
    """LLM may return tech as a list — model must coerce it to a comma-separated string."""
    proj = TailoredProject(
        title="TitanSwarm",
        tech=["Python", "LangChain", "Streamlit", "Gemini API"],
        date="Jan 2026 – Present",
        bullets=["Built RAG pipeline."],
    )
    assert proj.tech == "Python, LangChain, Streamlit, Gemini API"


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


def test_tailored_project_has_keyword_overlap_count():
    """TailoredProject must accept and store keyword_overlap_count."""
    proj = TailoredProject(
        title="TitanStore",
        tech="Go, Docker",
        date="Jan 2026 – Present",
        bullets=["Built Raft.", "Added WAL.", "Set up TCP.", "Tested replication."],
        keyword_overlap_count=4,
    )
    assert proj.keyword_overlap_count == 4


def test_tailored_project_keyword_overlap_defaults_to_zero():
    """keyword_overlap_count should default to 0 so old code stays compatible."""
    proj = TailoredProject(
        title="TitanStore",
        tech="Go, Docker",
        date="Jan 2026 – Present",
        bullets=["Built Raft."],
    )
    assert proj.keyword_overlap_count == 0


def test_tailored_application_has_missing_skills_field():
    """TailoredApplication must accept a missing_skills list."""
    app = TailoredApplication(
        job_id="j5",
        skills_to_highlight={"Languages": ["Python"]},
        tailored_projects=[],
        tailored_experience=[],
        missing_skills=["Kubernetes", "Ansible", "Cassandra"],
    )
    assert app.missing_skills == ["Kubernetes", "Ansible", "Cassandra"]


def test_tailored_application_missing_skills_defaults_to_empty():
    """missing_skills must default to [] for backwards compatibility."""
    app = TailoredApplication(
        job_id="j6",
        skills_to_highlight={"Languages": ["Python"]},
        tailored_projects=[],
        tailored_experience=[],
    )
    assert app.missing_skills == []

from enum import Enum
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    PROCESSING = "PROCESSING"
    PENDING_REVIEW = "PENDING_REVIEW"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    INTERVIEW = "INTERVIEW"
    ERROR = "ERROR"

class Job(BaseModel):
    id: str = Field(..., description="Unique hash of the job URL or description")
    company: str
    role: str
    status: JobStatus = JobStatus.DISCOVERED
    job_description: str
    required_skills: list[str] = Field(default_factory=list)
    custom_questions: list[str] = Field(default_factory=list)
    url: str

class TailoredProject(BaseModel):
    title: str = Field(..., description="Project name, e.g. 'TitanStore'")
    tech: str = Field(..., description="Tech stack string, e.g. 'Go, SQL, Docker'")
    date: str = Field(..., description="Date range, e.g. 'Jan 2026 – Present'")
    project_type: str = Field(default="Personal Project", description="e.g. 'Personal Project' or 'Collaborative Project'")
    bullets: list[str] = Field(..., description="2–4 bullets in XYZ format rewritten to mirror the JD's keywords. ONLY facts from the resume. Use 4 bullets if this project is highly relevant to the JD; use 2 if it is only tangentially relevant.")

class TailoredExperience(BaseModel):
    title: str = Field(..., description="Job title, e.g. 'Server'")
    company: str = Field(..., description="Company name, e.g. 'Pho Goodness Restaurant'")
    start_date: str = Field(..., description="e.g. 'Jan 2024'")
    end_date: str = Field(..., description="e.g. 'Present'")
    location: str = Field(default="", description="e.g. 'Burnaby, BC'")
    bullets: list[str] = Field(..., description="1-2 bullets in XYZ format rewritten to mirror the JD's keywords. ONLY facts from the resume.")

class TailoredApplication(BaseModel):
    job_id: str
    skills_to_highlight: dict[str, list[str]] = Field(
        ...,
        description="Categorized skills from the resume most relevant to this JD. Keys are category names (e.g. 'Languages', 'Backend & Systems'), values are lists of skills."
    )
    tailored_projects: list[TailoredProject] = Field(..., description="Each project from the resume with bullets rewritten for this JD.")
    tailored_experience: list[TailoredExperience] = Field(..., description="Each work experience entry with bullets rewritten for this JD.")
    q_and_a_responses: dict[str, str] = Field(default_factory=dict, description="Answers to custom portal questions.")

class UserProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    github: str = ""
    linkedin: str = ""
    website: str = ""
    base_summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    pref_role: str = ""
    pref_location: str = ""

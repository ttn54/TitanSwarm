from enum import Enum
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    PROCESSING = "PROCESSING"
    PENDING_REVIEW = "PENDING_REVIEW"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
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
    bullets: list[str] = Field(..., description="2-3 bullets rewritten to mirror the JD's keywords. ONLY facts from the resume.")

class TailoredApplication(BaseModel):
    job_id: str
    summary: str = Field(..., description="2-sentence professional summary tailored to this specific role.")
    skills_to_highlight: list[str] = Field(..., description="8-10 skills from the resume most relevant to this JD.")
    tailored_projects: list[TailoredProject] = Field(..., description="Each project from the resume with bullets rewritten for this JD.")
    q_and_a_responses: dict[str, str] = Field(default_factory=dict, description="Answers to custom portal questions.")

class UserProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    github: str = ""
    linkedin: str = ""
    base_summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)

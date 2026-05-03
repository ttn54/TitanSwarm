from enum import Enum
from pydantic import BaseModel, Field, field_validator

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
    location: str = ""
    date_posted: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    salary_interval: str = ""


def format_salary(job: "Job") -> str | None:
    """Return a human-readable salary string, or None if no salary data."""
    if job.salary_min is None and job.salary_max is None:
        return None
    symbol = "CA$" if (job.salary_currency or "").upper() == "CAD" else "$"
    _interval_map = {"yearly": "/yr", "hourly": "/hr", "monthly": "/mo"}
    suffix = _interval_map.get((job.salary_interval or "").lower(), "")
    if job.salary_min is not None and job.salary_max is not None:
        return f"{symbol}{job.salary_min:,.0f} \u2013 {symbol}{job.salary_max:,.0f}{suffix}"
    if job.salary_max is not None:
        return f"Up to {symbol}{job.salary_max:,.0f}{suffix}"
    return f"From {symbol}{job.salary_min:,.0f}{suffix}"

class TailoredProject(BaseModel):
    title: str = Field(..., description="Project name, e.g. 'TitanStore'")
    tech: str = Field(..., description="Tech stack string, e.g. 'Go, SQL, Docker'")
    date: str = Field(..., description="Date range, e.g. 'Jan 2026 – Present'")
    project_type: str = Field(default="Personal Project", description="e.g. 'Personal Project' or 'Collaborative Project'")
    bullets: list[str] = Field(..., description="2–4 bullets in XYZ format rewritten to mirror the JD's keywords. ONLY facts from the resume. Use 4 bullets if this project is highly relevant to the JD; use 2 if it is only tangentially relevant.")
    keyword_overlap_count: int = Field(default=0, description="Number of JD tech keywords that appear in this project's stack or README. Fill this during STEP B scoring. 0 means no overlap — this project must be excluded.")

    @field_validator("tech", mode="before")
    @classmethod
    def coerce_tech_list_to_string(cls, v: object) -> str:
        if isinstance(v, list):
            return ", ".join(str(item) for item in v)
        return v

    @field_validator("date", mode="before")
    @classmethod
    def _coerce_date(cls, v):
        return v if isinstance(v, str) else ""

class TailoredExperience(BaseModel):
    title: str = Field(..., description="Job title, e.g. 'Server'")
    company: str = Field(..., description="Company name, e.g. 'Pho Goodness Restaurant'")
    start_date: str = Field(..., description="e.g. 'Jan 2024'")
    end_date: str = Field(..., description="e.g. 'Present'")
    location: str = Field(default="", description="e.g. 'Burnaby, BC'")
    bullets: list[str] = Field(..., description="1-2 bullets in XYZ format rewritten to mirror the JD's keywords. ONLY facts from the resume.")

    @field_validator("location", mode="before")
    @classmethod
    def _coerce_location(cls, v):
        return v if isinstance(v, str) else ""


class TailoredEducation(BaseModel):
    degree: str = Field(..., description="Exact degree/program text from candidate context.")
    institution: str = Field(..., description="School/institution name from candidate context.")
    start_date: str = Field(..., description="e.g. 'Sep 2022'")
    end_date: str = Field(..., description="e.g. 'Present'")
    location: str = Field(default="", description="e.g. 'Burnaby, BC'")
    bullets: list[str] = Field(default_factory=list, description="Optional education bullets rewritten from source facts only.")

    @field_validator("location", mode="before")
    @classmethod
    def _coerce_location(cls, v):
        return v if isinstance(v, str) else ""

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _coerce_dates(cls, v):
        return v if isinstance(v, str) else ""

class TailoredApplication(BaseModel):
    job_id: str
    skills_to_highlight: dict[str, list[str]] = Field(
        ...,
        description="Categorized skills from the resume most relevant to this JD. Keys are category names (e.g. 'Languages', 'Backend & Systems'), values are lists of skills. ONLY include skills that are explicitly present in the CANDIDATE'S CONTEXT — do NOT add skills from the JD that the candidate has not demonstrated."
    )
    tailored_projects: list[TailoredProject] = Field(..., description="Each project from the resume with bullets rewritten for this JD.")
    tailored_experience: list[TailoredExperience] = Field(..., description="Each work experience entry with bullets rewritten for this JD.")
    tailored_education: list[TailoredEducation] = Field(default_factory=list, description="Each education entry rewritten from source facts only.")
    q_and_a_responses: dict[str, str] = Field(default_factory=dict, description="Answers to custom portal questions.")
    missing_skills: list[str] = Field(default_factory=list, description="Skills or technologies mentioned in the JD that are NOT present anywhere in the candidate's context. These are genuine gaps the candidate should be aware of. Be specific — list individual tools/languages, not categories (e.g. 'Kubernetes', 'Ansible', not 'DevOps skills').")
    work_experience_relevant: bool = Field(default=True, description="True if any work experience entry has a tech/engineering title relevant to the JD; False for unrelated roles like hospitality or retail.")

class UserProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    github: str = ""
    linkedin: str = ""
    website: str = ""
    base_summary: str = ""
    skills: list[str] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    pref_role: str = ""
    pref_location: str = ""

class CoverLetterResult(BaseModel):
    body: str = Field(..., description="The letter body paragraphs only — no header, no date, no signature block.")
    company_address: str | None = Field(
        default=None,
        description="Recipient street address extracted verbatim from the JD, or null if not present.",
    )


class User(BaseModel):
    id: int
    username: str

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

class TailoredApplication(BaseModel):
    job_id: str
    tailored_bullets: list[str] = Field(..., description="3-5 ATS optimized resume bullets based strictly on the user's ledger.")
    q_and_a_responses: dict[str, str] = Field(..., description="Answers to custom portal questions mapping question to answer.")

class UserProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    github: str = ""
    linkedin: str = ""
    base_summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)

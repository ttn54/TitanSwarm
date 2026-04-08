from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from src.core.models import Job, JobStatus, UserProfile

class JobRepository(ABC):
    """
    Abstract Base Class defining the Universal Remote Control for our storage layer.
    Any database we use (PostgreSQL, etc) must implement ALL of these methods.
    """

    # ── Job CRUD ──

    @abstractmethod
    async def save_job(self, job: Job) -> bool:
        """Saves a new job or updates an existing one. Returns True on success."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None:
        """Retrieves a single job by its unique hash ID."""
        pass

    @abstractmethod
    async def update_status(self, job_id: str, status: JobStatus) -> bool:
        """Transitions a job to a new status. Returns True if the job was found and updated."""
        pass

    @abstractmethod
    async def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """Retrieves all jobs matching a given status. Used by the Streamlit UI."""
        pass

    @abstractmethod
    async def count_all(self) -> int:
        """Returns the total count of all jobs in the repository."""
        pass

    # ── UserProfile persistence ──

    @abstractmethod
    async def save_profile(self, profile: UserProfile) -> bool:
        """Saves (upserts) the user profile. Single-user system — one row."""
        pass

    @abstractmethod
    async def get_profile(self) -> Optional[UserProfile]:
        """Returns the saved profile, or None if none exists yet."""
        pass

    # ── Tailored result persistence ──

    @abstractmethod
    async def save_tailored_result(self, job_id: str, ai_json: str, pdf_bytes: bytes, cover_letter: str | None = None) -> bool:
        """Saves AI tailoring output + generated PDF bytes + optional cover letter for a job."""
        pass

    @abstractmethod
    async def get_tailored_result(self, job_id: str) -> Optional[Tuple[str, bytes, str | None]]:
        """Returns (ai_json, pdf_bytes, cover_letter) for a job, or None if not yet tailored."""
        pass

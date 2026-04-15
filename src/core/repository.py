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
    async def save_job(self, job: Job, user_id: int = 1) -> bool:
        """Saves a new job or updates an existing one. Returns True on success."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str, user_id: int = 1) -> Job | None:
        """Retrieves a single job by its unique hash ID, scoped to user."""
        pass

    @abstractmethod
    async def update_status(self, job_id: str, status: JobStatus, user_id: int = 1) -> bool:
        """Transitions a job to a new status. Returns True if the job was found and updated."""
        pass

    @abstractmethod
    async def get_jobs_by_status(self, status: JobStatus, user_id: int = 1) -> List[Job]:
        """Retrieves all jobs matching a given status, scoped to user."""
        pass

    @abstractmethod
    async def count_all(self, user_id: int = 1) -> int:
        """Returns the total count of all jobs for a user."""
        pass

    @abstractmethod
    async def delete_jobs_by_status(self, status: JobStatus, user_id: int = 1) -> int:
        """Deletes all jobs with the given status for a user. Returns the count deleted."""
        pass

    # ── UserProfile persistence ──

    @abstractmethod
    async def save_profile(self, profile: UserProfile, user_id: int = 1) -> bool:
        """Saves (upserts) the user profile for a specific user."""
        pass

    @abstractmethod
    async def get_profile(self, user_id: int = 1) -> Optional[UserProfile]:
        """Returns the saved profile for a user, or None if none exists yet."""
        pass

    # ── Tailored result persistence ──

    @abstractmethod
    async def save_tailored_result(self, job_id: str, ai_json: str, pdf_bytes: bytes, cover_letter: str | None = None, user_id: int = 1) -> bool:
        """Saves AI tailoring output + generated PDF bytes + optional cover letter for a job."""
        pass

    @abstractmethod
    async def get_tailored_result(self, job_id: str, user_id: int = 1) -> Optional[Tuple[str, bytes, str | None]]:
        """Returns (ai_json, pdf_bytes, cover_letter) for a job, or None if not yet tailored."""
        pass

    # ── Multi-tenant daemon support ──

    @abstractmethod
    async def get_all_user_targets(self) -> List[Tuple[int, str, str]]:
        """
        Returns a list of (user_id, pref_role, pref_location) for every user
        who has a non-empty preferred role saved in their profile.
        Used by the Sourcing Daemon to know who to scrape for.
        """
        pass

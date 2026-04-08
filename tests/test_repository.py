import pytest
from src.core.repository import JobRepository
from src.core.models import Job

def test_job_repository_is_abstract():
    """Ensure the JobRepository acts as a strict interface (Abstract Base Class)."""
    # Attempting to instantiate the ABC directly should fail
    with pytest.raises(TypeError):
        JobRepository()

def test_incomplete_repository_implementation():
    """Ensure that any class claiming to be a JobRepository must implement all methods."""
    class BadRepo(JobRepository):
        pass
        
    with pytest.raises(TypeError):
        BadRepo()

def test_valid_repository_implementation():
    """Ensure a correctly implemented subclass can be instantiated."""
    from src.core.models import JobStatus, UserProfile
    from typing import List, Optional, Tuple

    class GoodRepo(JobRepository):
        async def save_job(self, job: Job) -> bool:
            return True

        async def get_job(self, job_id: str) -> Job | None:
            return None

        async def update_status(self, job_id: str, status: JobStatus) -> bool:
            return True

        async def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
            return []

        async def count_all(self) -> int:
            return 0

        async def save_profile(self, profile: UserProfile) -> bool:
            return True

        async def get_profile(self) -> Optional[UserProfile]:
            return None

        async def save_tailored_result(self, job_id: str, ai_json: str, pdf_bytes: bytes, cover_letter: str | None = None) -> bool:
            return True

        async def get_tailored_result(self, job_id: str) -> Optional[Tuple[str, bytes, str | None]]:
            return None

    repo = GoodRepo()
    assert isinstance(repo, JobRepository)
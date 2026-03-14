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
    class GoodRepo(JobRepository):
        async def save_job(self, job: Job) -> bool:
            return True
            
        async def get_job(self, job_id: str) -> Job | None:
            return None
            
    # This should not raise an error
    repo = GoodRepo()
    assert isinstance(repo, JobRepository)
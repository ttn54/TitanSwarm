from abc import ABC, abstractmethod
from src.core.models import Job

class JobRepository(ABC):
    """
    Abstract Base Class defining the Universal Remote Control for our storage layer.
    Any database we use (TitanStore, PostgreSQL, etc) must implement these methods.
    """
    
    @abstractmethod
    async def save_job(self, job: Job) -> bool:
        """Saves a new job or updates an existing one."""
        pass
        
    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None:
        """Retrieves a job by its unique hash ID."""
        pass

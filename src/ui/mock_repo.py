from typing import List, Optional, Tuple
from uuid import uuid4
from src.core.models import Job, JobStatus, UserProfile
from src.core.repository import JobRepository

class MockUIRepository(JobRepository):
    """
    An in-memory repository prepopulated with fake data 
    so we can build and test the Streamlit UI immediately.
    """
    def __init__(self):
        self.jobs = {}
        self._profile: Optional[UserProfile] = None
        self._tailored: dict[str, Tuple[str, bytes]] = {}
        self._seed_data()

    def _seed_data(self):
        # Seed 3 Pending Review Jobs
        for i in range(3):
            job = Job(
                id=str(uuid4()),
                role=f"Software Engineer Intern (Team {i})",
                company="Amazon",
                url=f"https://amazon.jobs/fake-{i}",
                status=JobStatus.PENDING_REVIEW,
                job_description="Standard software engineer internship description"
            )
            self.jobs[job.id] = job
            
        # Seed 1 Already Submitted Job for Metrics
        submitted_job = Job(
            id=str(uuid4()),
            role="Backend Systems Intern",
            company="Cloudflare",
            url="https://cloudflare.com/jobs/fake-99",
            status=JobStatus.SUBMITTED,
            job_description="Standard backend internship description",
        )
        self.jobs[submitted_job.id] = submitted_job

    async def save_job(self, job: Job) -> bool:
        self.jobs[job.id] = job
        return True

    async def get_job(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    async def update_status(self, job_id: str, status: JobStatus):
        if job_id in self.jobs:
            self.jobs[job_id].status = status

    async def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        return [j for j in self.jobs.values() if j.status == status]
    
    async def count_all(self) -> int:
        return len(self.jobs)

    async def save_profile(self, profile: UserProfile) -> bool:
        self._profile = profile
        return True

    async def get_profile(self) -> Optional[UserProfile]:
        return self._profile

    async def save_tailored_result(self, job_id: str, ai_json: str, pdf_bytes: bytes, cover_letter: str | None = None) -> bool:
        self._tailored[job_id] = (ai_json, pdf_bytes, cover_letter)
        return True

    async def get_tailored_result(self, job_id: str) -> Optional[Tuple[str, bytes, str | None]]:
        return self._tailored.get(job_id)
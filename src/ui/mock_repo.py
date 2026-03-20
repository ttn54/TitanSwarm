from typing import List, Optional
from uuid import uuid4
from src.core.models import Job, JobStatus
from src.core.repository import JobRepository

class MockUIRepository(JobRepository):
    """
    An in-memory repository prepopulated with fake data 
    so we can build and test the Streamlit UI immediately.
    """
    def __init__(self):
        self.jobs = {}
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

    async def save_job(self, job: Job):
        self.jobs[job.id] = job

    async def get_job(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    async def update_status(self, job_id: str, status: JobStatus):
        if job_id in self.jobs:
            self.jobs[job_id].status = status

    async def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        return [j for j in self.jobs.values() if j.status == status]
    
    async def count_all(self) -> int:
        return len(self.jobs)
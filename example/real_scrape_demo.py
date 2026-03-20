import asyncio
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.scraper import IntentScraper
from src.core.repository import JobRepository
from src.core.models import Job

# Quick mock repository to print and intercept saves
class FileJobRepository(JobRepository):
    def __init__(self, filename="example/real_scraped_data.json"):
        self.filename = filename
        self.jobs = []
        
    async def save_job(self, job: Job):
        self.jobs.append(job.model_dump())
        with open(self.filename, 'w') as f:
            json.dump(self.jobs, f, indent=2)

    async def get_job(self, job_id: str) -> Job:
        for j in self.jobs:
            if j.get("id") == job_id:
                return Job(**j)
        return None

async def main():
    repo = FileJobRepository()
    scraper = IntentScraper(repository=repo)
    
    print("🚀 Using TitanSwarm IntentScraper...")
    query = "Software Engineer New Grad site:boards.greenhouse.io"
    
    jobs = await scraper.scrape(query)
    
    print(f"\n✅ SUCCESS! Found {len(jobs)} real Software Engineering related jobs.")
    print(f"💾 Saved raw real data to {os.path.abspath(repo.filename)}")
    
    if jobs:
        print("\n--- PREVIEW OF REAL JOB DATA ---")
        job = jobs[0]
        print(f"Company: {job.company}")
        print(f"Role: {job.role}")
        print(f"URL: {job.url}")
        print(f"Description Length: {len(job.job_description)} characters")
        print("--------------------------------")

if __name__ == "__main__":
    asyncio.run(main())

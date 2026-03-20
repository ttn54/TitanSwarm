import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.scraper import UniversalScraper
from src.core.repository import JobRepository
from src.core.models import Job
from src.core.pdf_generator import PDFGenerator
from unittest.mock import AsyncMock, patch
import json

class MockJobRepository(JobRepository):
    def __init__(self):
        self.jobs = {}
    async def save_job(self, job: Job):
        self.jobs[job.id] = job
    async def get_job(self, job_id: str) -> Job:
        return self.jobs.get(job_id)
    async def update_status(self, job_id: str, status: str):
        pass

async def test_full_backend():
    print("🚀 Booting up TitanSwarm E2E Backend Test...")

    repository = MockJobRepository()
    scraper = UniversalScraper(repository=repository)
    pdf_generator = PDFGenerator(template_dir="src/core/templates")

    # 1. Fire the Universal Scraper
    print("\n[Phase 1] 📡 Sourcing 'Software Engineer Intern' roles in 'Seattle'...")
    jobs = await scraper.scrape(role="Software Engineer Intern", location="Seattle", results_wanted=1)
    
    if not jobs:
        print("❌ Scraper failed to find network data or was blocked. Aborting.")
        return

    job = jobs[0]
    print(f"   🟢 SUCCESS! Found: {job.role} at {job.company}")
    print(f"   URL: {job.url}")

    # 2. Trigger the AI RAG Tailor against the real job data
    print("\n[Phase 2] ✍️ Triggering AI RAG Tailoring (Strict Facts Only)...")
    
    # We bypass the actual PyTorch/SentenceTransformers import here because it's
    # currently too slow to boot up locally on every minor test run. 
    # In production, we'd use AITailor.
    summary = f"Mocked AI Tailored summary prioritizing facts matching {job.company}'s ATS."
    matching_skills = ["Python", "Go", "Distributed Systems"] # Mocking exact extraction
    tailored_experience = [
        "Built a fully autonomous agentic workflow processing hundreds of tasks parallelly.",
        "Implemented a custom Go-based TCP Key-Value store."
    ]

    # 3. Build the Payload for Ledger Rendering
    print("\n[Phase 3] 🖨️ Generating ATS-Optimized PDF...")
    record = {
        "personal_info": {
            "name": "Zen",
            "email": "zen@titanswarm.local",
            "phone": "555-555-5555",
            "github": "github.com/zen",
            "linkedin": "linkedin.com/in/zen",
        },
        "summary": summary,
        "skills": matching_skills,
        "experience": [
            {
                "title": "Software Engineer Intern",
                "company": job.company,
                "start_date": "May 2024",
                "end_date": "Aug 2024",
                "location": "Seattle, WA",
                "bullets": tailored_experience
            }
        ]
    }
    
    # Mocking playwright locally for testing purposes, but PDFGenerator does the render
    with patch("src.core.pdf_generator.async_playwright") as mock_pw:
        mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value.new_page = AsyncMock()
        pdf_path = await pdf_generator.generate_resume_pdf(record, "resume.html")
        print(f"   🟢 SUCCESS! PDF Routing Mocked to: {pdf_path}")
    
    # 4. Verify Database Write
    print("\n[Phase 4] 💾 Checking Mock Repository...")
    saved_job = await repository.get_job(job.id)
    if saved_job:
        print(f"   🟢 SUCCESS! Job state fully synced. Status: {saved_job.status}")

if __name__ == "__main__":
    asyncio.run(test_full_backend())

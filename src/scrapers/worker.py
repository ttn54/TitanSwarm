from typing import Any
import pandas as pd
from jobspy import scrape_jobs
from src.core.models import Job, JobStatus

class SourcingEngine:
    def __init__(self, repository: Any, interval_hours: int = 12):
        self.repository = repository
        self.interval_hours = interval_hours

    def run_sweep(self, role: str, location: str, results_wanted: int = 10) -> None:
        """
        Executes a scraping sweep utilizing jobspy,
        converts the raw DataFrame to Pydantic Job models, and persists them via the repository interface.
        """
        jobs_df = scrape_jobs(
            site_name=["indeed", "linkedin", "glassdoor"],
            search_term=role,
            location=location,
            results_wanted=results_wanted
        )

        if jobs_df is None or jobs_df.empty:
            return

        for _, row in jobs_df.iterrows():
            job_id = str(row.get("id"))
            
            # Deduplication Check
            if hasattr(self.repository, "job_exists") and self.repository.job_exists(job_id):
                continue
                
            description = row.get("description", "Description not provided.")
            if pd.isna(description):
                description = "Description not provided."

            job = Job(
                id=job_id,
                company=str(row.get("company")),
                role=str(row.get("title")),
                status=JobStatus.DISCOVERED,
                job_description=str(description),
                url=str(row.get("job_url"))
            )
            
            self.repository.save_job(job)

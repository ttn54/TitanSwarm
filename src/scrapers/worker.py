from typing import Any
import asyncio
import logging
import pandas as pd
from jobspy import scrape_jobs
from src.core.models import Job, JobStatus

logger = logging.getLogger(__name__)

class SourcingEngine:
    def __init__(self, repository: Any, interval_hours: int = 12):
        self.repository = repository
        self.interval_hours = interval_hours

    async def run_sweep(self, role: str, location: str, results_wanted: int = 10) -> int:
        """
        Executes a scraping sweep utilizing jobspy, converts the raw DataFrame
        to Pydantic Job models, deduplicates against the repository, and persists
        new jobs. Returns the count of new jobs saved.
        """
        loop = asyncio.get_event_loop()

        # Run the blocking scrape_jobs call in a thread pool so it doesn't
        # freeze the event loop. LinkedIn is the only reliable free source;
        # Indeed is included as a secondary. Glassdoor requires login cookies.
        def _scrape() -> pd.DataFrame:
            return scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=role,
                location=location,
                results_wanted=results_wanted,
            )

        jobs_df = await loop.run_in_executor(None, _scrape)

        if jobs_df is None or jobs_df.empty:
            logger.info("Scraping sweep returned no results.")
            return 0

        # Post-filter: only keep jobs whose title contains ALL words from the
        # search term. This prevents LinkedIn's algorithm from injecting
        # "Senior Software Engineer" when the user searched "Software Engineer Intern".
        _search_words = [w.lower() for w in role.split() if w]
        def _title_matches(title_val) -> bool:
            if not title_val or (isinstance(title_val, float) and pd.isna(title_val)):
                return False
            t = str(title_val).lower()
            return all(w in t for w in _search_words)

        jobs_df = jobs_df[jobs_df["title"].apply(_title_matches)]
        if jobs_df.empty:
            logger.info("No jobs matched title filter after scraping.")
            return 0

        saved_count = 0
        for _, row in jobs_df.iterrows():
            job_id = str(row.get("id"))
            if job_id == "None":
                logger.warning("Skipping job with null ID from scraper.")
                continue

            # Deduplication: check the repository via the standard interface
            existing = await self.repository.get_job(job_id)
            if existing is not None:
                logger.debug(f"Skipping duplicate job: {job_id}")
                continue

            description = row.get("description", "Description not provided.")
            if pd.isna(description):
                description = "Description not provided."

            # Extract skills list from JobSpy 'skills' column (may be None or a list)
            raw_skills = row.get("skills")
            if raw_skills and not (isinstance(raw_skills, float) and pd.isna(raw_skills)):
                if isinstance(raw_skills, list):
                    required_skills = [str(s) for s in raw_skills if s]
                else:
                    required_skills = [s.strip() for s in str(raw_skills).split(",") if s.strip()]
            else:
                required_skills = []

            company_raw = row.get("company")
            company = str(company_raw) if company_raw and not (isinstance(company_raw, float) and pd.isna(company_raw)) else "Unknown Company"

            job = Job(
                id=job_id,
                company=company,
                role=str(row.get("title")),
                status=JobStatus.DISCOVERED,
                job_description=str(description),
                required_skills=required_skills,
                url=str(row.get("job_url"))
            )

            await self.repository.save_job(job)
            saved_count += 1
            logger.info(f"Saved new job: {job.role} at {job.company}")

        return saved_count

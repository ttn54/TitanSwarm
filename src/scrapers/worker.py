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

    async def run_sweep(self, role: str, location: str, results_wanted: int = 25) -> tuple[int, list[str]]:
        """
        Executes a scraping sweep utilizing jobspy, converts the raw DataFrame
        to Pydantic Job models, deduplicates against the repository, and persists
        new jobs.
        Returns (new_saved_count, all_found_job_ids) so the UI can display
        all results for this sweep regardless of their current status.
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
                linkedin_fetch_description=True,
            )

        jobs_df = await loop.run_in_executor(None, _scrape)

        if jobs_df is None or jobs_df.empty:
            logger.info("Scraping sweep returned no results.")
            return 0, []

        # Post-filter: prevent LinkedIn from injecting irrelevant jobs.
        #
        # Rules (applied in order):
        #   1. Intern-type guard: if user searched "intern/internship/co-op",
        #      title MUST contain an intern-type word. Blocks "Senior SWE" results.
        #   2. Seniority guard: if user searched a seniority word (senior/lead/…),
        #      title MUST contain THAT seniority word.
        #   3. Role-word guard: at least ONE non-qualifier role word (≥4 chars)
        #      must appear in the title. Blocks "Research Intern - AI" for "SWE Intern".
        _INTERN_QUALS = {"intern", "internship", "co-op", "coop"}
        _SENIORITY_QUALS = {"junior", "senior", "lead", "staff", "principal"}

        _search_words = [w.lower() for w in role.split() if w]
        _has_intern = any(w in _INTERN_QUALS for w in _search_words)
        _search_seniority = [w for w in _search_words if w in _SENIORITY_QUALS]
        _role_words = [w for w in _search_words
                       if w not in _INTERN_QUALS and w not in _SENIORITY_QUALS and len(w) >= 4]

        def _title_matches(title_val) -> bool:
            if not title_val or (isinstance(title_val, float) and pd.isna(title_val)):
                return False
            t = str(title_val).lower()
            # Rule 1: intern-type guard
            if _has_intern and not any(q in t for q in _INTERN_QUALS):
                return False
            # Rule 2: seniority guard
            if _search_seniority and not any(s in t for s in _search_seniority):
                return False
            # Rule 3: at least one core role word must appear
            if _role_words and not any(w in t for w in _role_words):
                return False
            return True

        jobs_df = jobs_df[jobs_df["title"].apply(_title_matches)]
        if jobs_df.empty:
            logger.info("No jobs matched title filter after scraping.")
            return 0, []

        saved_count = 0
        all_found_ids: list[str] = []
        for _, row in jobs_df.iterrows():
            job_id = str(row.get("id"))
            if job_id == "None":
                logger.warning("Skipping job with null ID from scraper.")
                continue

            all_found_ids.append(job_id)

            # Deduplication: skip only if the existing record has a real description.
            # If description is missing/placeholder, fall through and overwrite it.
            _BAD_DESC = {"", "Description not provided.", "None", "nan"}
            existing = await self.repository.get_job(job_id)
            if existing is not None and existing.job_description.strip() not in _BAD_DESC:
                logger.debug(f"Skipping duplicate job: {job_id}")
                continue

            description = row.get("description")
            if not description or (isinstance(description, float) and pd.isna(description)) or str(description).strip() in {"None", "nan", ""}:
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

            location_raw = row.get("location")
            job_location = str(location_raw) if location_raw and not (isinstance(location_raw, float) and pd.isna(location_raw)) else ""

            date_raw = row.get("date_posted")
            if date_raw and not (isinstance(date_raw, float) and pd.isna(date_raw)):
                job_date = str(date_raw)
            else:
                job_date = ""

            job = Job(
                id=job_id,
                company=company,
                role=str(row.get("title")),
                status=JobStatus.DISCOVERED,
                job_description=str(description),
                required_skills=required_skills,
                url=str(row.get("job_url")),
                location=job_location,
                date_posted=job_date,
            )

            await self.repository.save_job(job)
            saved_count += 1
            logger.info(f"Saved new job: {job.role} at {job.company}")

        return saved_count, all_found_ids

from abc import ABC, abstractmethod
from typing import List
import asyncio
import logging
import pandas as pd
from jobspy import scrape_jobs
from src.core.repository import JobRepository
from src.core.models import Job

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    def __init__(self, repository: JobRepository):
        self.repository = repository

    @abstractmethod
    async def scrape(self, role: str, location: str, results_wanted: int = 10) -> List[Job]:
        """Scrape jobs based on a role and location and return a list of Jobs"""
        pass

class UniversalScraper(BaseScraper):
    async def scrape(self, role: str, location: str, results_wanted: int = 10) -> List[Job]:
        found_jobs = []
        
        logger.info("Searching Universal Aggregators for: %s in %s", role, location)
        
        # JobSpy is synchronous, in production wrap in run_in_executor
        # We will cast it to list of dicts to process
        try:
            jobs_df = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=role,
                location=location,
                results_wanted=results_wanted,
                country_indeed="usa"
            )
        except Exception as e:
            logger.error("Aggregation search failed: %s", e)
            return found_jobs
            
        if jobs_df is None or jobs_df.empty:
            logger.info("No jobs found from aggregators.")
            return found_jobs

        # Batch dedup: run all existence checks in parallel instead of N sequential queries
        all_ids = [str(row.get('id', '')) for _, row in jobs_df.iterrows()]
        existing_checks = await asyncio.gather(*[self.repository.get_job(jid) for jid in all_ids])
        existing_ids = {jid for jid, ex in zip(all_ids, existing_checks) if ex is not None}

        for index, row in jobs_df.iterrows():
            job_id = str(row.get('id', ''))

            # Deduplication — already checked in batch above
            if job_id in existing_ids:
                continue
                
            try:
                # Handle potential NaN values
                description = row.get('description', '')
                if pd.isna(description):
                    description = ""
                    
                company = row.get('company', 'Unknown')
                if pd.isna(company):
                    company = "Unknown"
                    
                title = row.get('title', 'Unknown Role')
                if pd.isna(title):
                    title = "Unknown Role"
                    
                url = row.get('job_url', '')
                if pd.isna(url):
                    url = ""

                job = Job(
                    id=job_id,
                    company=str(company),
                    role=str(title),
                    url=str(url),
                    job_description=str(description),
                    required_skills=[],
                    custom_questions=[]
                )
                
                await self.repository.save_job(job)
                found_jobs.append(job)
            except Exception as e:
                logger.error("Failed to process job record %s: %s", job_id, e)
                
        return found_jobs

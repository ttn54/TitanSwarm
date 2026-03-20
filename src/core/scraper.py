from abc import ABC, abstractmethod
from typing import List
import asyncio
import pandas as pd
from jobspy import scrape_jobs
from src.core.repository import JobRepository
from src.core.models import Job

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
        
        print(f"🔍 Searching Universal Aggregators for: {role} in {location}")
        
        # JobSpy is synchronous, in production wrap in run_in_executor
        # We will cast it to list of dicts to process
        try:
            jobs_df = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=role,
                location=location,
                results_wanted=results_wanted,
                country_alice="usa" # Will generalize to location broadly
            )
        except Exception as e:
            print(f"Aggregation search failed: {e}")
            return found_jobs
            
        if jobs_df is None or jobs_df.empty:
            print("No jobs found from aggregators.")
            return found_jobs

        for index, row in jobs_df.iterrows():
            job_id = str(row.get('id', ''))
            
            # Deduplication
            existing = await self.repository.get_job(job_id)
            if existing:
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
                print(f"Failed to process job record {job_id}: {e}")
                
        return found_jobs



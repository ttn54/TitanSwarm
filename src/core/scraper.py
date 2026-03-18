from abc import ABC, abstractmethod
from typing import List
from playwright.async_api import async_playwright, Page
from src.core.repository import JobRepository
from src.core.models import Job
import asyncio
import random

class BaseScraper(ABC):
    def __init__(self, repository: JobRepository):
        self.repository = repository

    @abstractmethod
    async def scrape(self, url: str) -> List[Job]:
        """Scrape the given URL and return a list of Jobs"""
        pass

class GreenhouseScraper(BaseScraper):
    async def _fetch_job_listings(self, url: str) -> List[dict]:
        """Fetch basic job listings from a greenhouse URL using Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url, timeout=15000)
                # Greenhouse usually contains jobs in `.opening` class elements
                await page.wait_for_selector('.opening', timeout=10000)
                
                listings = []
                openings = await page.query_selector_all('.opening')
                
                company_name = url.split('/')[-1] if not url.endswith('/') else url.split('/')[-2]
                
                for opening in openings:
                    link_elem = await opening.query_selector('a')
                    if not link_elem:
                        continue
                    
                    title = await link_elem.inner_text()
                    href = await link_elem.get_attribute('href')
                    
                    # Ensure absolute url
                    if href and href.startswith('/'):
                        href = f"https://boards.greenhouse.io{href}"
                        
                    listings.append({
                        "title": title.strip(),
                        "url": href,
                        "company": company_name.capitalize()
                    })
                return listings
            except Exception as e:
                print(f"Error fetching listings from {url}: {e}")
                return []
            finally:
                await browser.close()

    async def _fetch_job_details(self, url: str) -> dict:
        """Fetch specific details (JD, questions) from the job page."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            details = {
                "job_description": "",
                "required_skills": [],
                "custom_questions": []
            }
            
            try:
                await page.goto(url, timeout=15000)
                # Greenhouse JD is usually within `#content`
                await page.wait_for_selector('#content', timeout=10000)
                
                content_elem = await page.query_selector('#content')
                if content_elem:
                    # Very basic extraction: grab all text as JD
                    text_content = await content_elem.inner_text()
                    details["job_description"] = text_content.strip()
                    
                    # For custom questions, look for input labels
                    labels = await page.query_selector_all('label')
                    for label in labels:
                        q_text = await label.inner_text()
                        q_clean = q_text.split('\n')[0].strip() # often greenhouse labels have sub-spans or asterisks
                        if q_clean and len(q_clean) > 5:
                            details["custom_questions"].append(q_clean)
            except Exception as e:
                print(f"Error fetching details from {url}: {e}")
            finally:
                await browser.close()
                
            return details

    async def scrape(self, url: str) -> List[Job]:
        listings = await self._fetch_job_listings(url)
        found_jobs = []

        # Target keywords for Fall 2026 SWE
        target_keywords = ["software", "engineer", "intern", "co-op", "developer"]
        
        for item in listings:
            title_lower = item["title"].lower()
            
            # Simple keyword search and ignore clearly irrelevant roles
            if any(kw in title_lower for kw in target_keywords) and "analyst" not in title_lower:
                job_url = item["url"]
                job_id = job_url.split("/")[-1] if "/" in job_url else job_url
                
                # Deduplication check
                existing = await self.repository.get_job(job_id)
                if existing:
                    continue
                
                # Fetch deeper DOM details
                details = await self._fetch_job_details(job_url)
                
                job = Job(
                    id=job_id,
                    company=item.get("company", "Unknown"),
                    role=item["title"],
                    url=job_url,
                    job_description=details.get("job_description", ""),
                    required_skills=details.get("required_skills", []),
                    custom_questions=details.get("custom_questions", [])
                )
                
                await self.repository.save_job(job)
                found_jobs.append(job)
                
        return found_jobs

from abc import ABC, abstractmethod
from typing import List
import asyncio
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from src.core.repository import JobRepository
from src.core.models import Job

class BaseScraper(ABC):
    def __init__(self, repository: JobRepository):
        self.repository = repository

    @abstractmethod
    async def scrape(self, query: str) -> List[Job]:
        """Scrape jobs based on a query and return a list of Jobs"""
        pass

class IntentScraper(BaseScraper):
    async def scrape(self, intent_query: str) -> List[Job]:
        found_jobs = []
        
        # 1. Broaden the intent just to be sure we are looking at Greenhouse if needed, but the user specifies it.
        # We can add site:boards.greenhouse.io if it's not present.
        if "site:" not in intent_query:
            query = f"{intent_query} site:boards.greenhouse.io"
        else:
            query = intent_query
            
        print(f"🔍 Searching DDG for: {query}")
        
        # DDGS is synchronous. In a rigorous concurrent workflow, run this in executor. 
        # For simplicity, we just run it here.
        results = []
        with DDGS() as ddgs:
            # We want just a few links to avoid spamming
            for r in ddgs.text(query, max_results=10):
                results.append(r)
                
        async with httpx.AsyncClient(timeout=15.0) as client:
            for item in results:
                url = item.get("href")
                if not url or "boards.greenhouse.io" not in url:
                    continue
                    
                job_id = url.split("/")[-1] if "/" in url else url
                
                # Deduplication check
                existing = await self.repository.get_job(job_id)
                if existing:
                    continue
                    
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                        
                    # 2. Extract clean body text
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style", "nav", "footer"]):
                        script.decompose()
                        
                    # Get text
                    body = soup.find('body')
                    if body:
                        text = body.get_text(separator='\n')
                        # collapse whitespace
                        clean_text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
                    else:
                        clean_text = soup.get_text(separator='\n')
                        
                    # Create job
                    company_name = url.split('/')[-3] if len(url.split('/')) > 3 else "Unknown"
                    
                    job = Job(
                        id=job_id,
                        company=company_name.capitalize(),
                        role=item.get("title", "Unknown Role"),
                        url=url,
                        job_description=clean_text,
                        required_skills=[], # We can use RAG to extract this later
                        custom_questions=[]  # Can extract via RAG later
                    )
                    
                    await self.repository.save_job(job)
                    found_jobs.append(job)
                    
                except Exception as e:
                    print(f"Error extracting {url}: {e}")
                    
        return found_jobs


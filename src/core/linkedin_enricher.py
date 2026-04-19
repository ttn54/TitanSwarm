import os
import re
from linkedin_scraper import BrowserManager, PersonScraper

class LinkedInScrapeError(Exception):
    pass

class LinkedInEnricher:
    def __init__(self):
        # We don't necessarily need linkedin credentials in .env if using a saved session.
        self.session_file = os.path.join(os.path.dirname(__file__), "..", "..", "session.json")
        
        # Check if session exists to warn early if wanted, but we'll just let it fail on scrape.
        
    def _extract_username(self, url_or_username: str) -> str:
        if "linkedin.com/in/" in url_or_username:
            match = re.search(r"linkedin\.com/in/([\w-]+)", url_or_username, re.IGNORECASE)
            if match:
                return match.group(1).rstrip("/")
        return url_or_username.strip("/").split("?")[0]

    async def fetch_profile(self, url_or_username: str) -> dict:
        username = self._extract_username(url_or_username)
        if not username:
            raise ValueError("Could not extract a valid LinkedIn username")

        url = f"https://www.linkedin.com/in/{username}/"

        if not os.path.exists(self.session_file):
            raise LinkedInScrapeError(f"Session file not found at {self.session_file}. Please run manual login script first.")

        try:
            async with BrowserManager(headless=True) as browser:
                await browser.load_session(self.session_file)
                
                scraper = PersonScraper(browser.page)
                person = await scraper.scrape(url)
                
                # Convert the dataclass to dict representing experience and education
                experienced_mapped = []
                for exp in person.experiences:
                    experienced_mapped.append({
                        "company": exp.company,
                        "title": exp.title,
                        "start_date": exp.start_date,
                        "end_date": exp.end_date,
                        "description": exp.description,
                        "location": exp.location
                    })
                    
                educations_mapped = []
                for edu in person.educations:
                    educations_mapped.append({
                        "institution": edu.institution,
                        "degree": edu.degree,
                        "start_date": edu.start_date,
                        "end_date": edu.end_date,
                        "location": ""  # library doesn't parse education location
                    })

                return {
                    "experience": experienced_mapped,
                    "education": educations_mapped
                }

        except Exception as e:
            raise LinkedInScrapeError(f"Failed scraping profile with linkedin_scraper: {str(e)}")

# Universal Scraper Design (JobSpy)

## Architecture & Data Flow
Transition from direct ATS or rigid search engines to a generalized multi-site strategy using `jobspy`.
1. `UniversalScraper` takes an intent string combining role and location dynamically (e.g. `scrape(role="Software Engineer Intern", location="Vancouver, BC")`).
2. It interacts with the `jobspy` Python library to scrape LinkedIn, Indeed, and Glassdoor simultaneously, bypassing anti-bot measures.
3. The resulting Pandas DataFrame is parsed into list of `Job` Pydantic models.
4. Descriptions and core details are formatted correctly and saved to the `JobRepository`.

## Data Structures
- `UniversalScraper(BaseScraper)` with a `scrape` method adapted to handle job role and location.

## Resiliency
This entirely outsources the scraping of aggregators to a specialized, maintained tool. The AI Tailor logic remains the same, accepting the `Job` object regardless of the sourcing origin.

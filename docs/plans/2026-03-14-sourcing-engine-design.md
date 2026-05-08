# Phase 2: Sourcing Engine (Scraping) Design

## 1. Architecture and Data Flow
* **Framework:** Python `playwright` (async) for robust headless browser automation.
* **Flow:**
  1. Initialization: A `GreenhouseScraper` inherits from an abstract `BaseScraper`.
  2. Navigation: Navigates to a company's Greenhouse job board (e.g. `https://boards.greenhouse.io/<company>`).
  3. Extraction: Parses the DOM to extract Job Title, Location, and Link.
  4. Filtering: Applies logic to identify roles relevant to "Fall 2026 Software Engineering" (e.g., keywords: "Software", "Engineer", "Intern", "Co-op").
  5. Deduplication: Queries the injected `JobRepository`. If the job URL or hashed ID exists, it skips execution.
  6. Deep Scrape: If the job is new, navigates to the detailed job page to extract the full Job Description (JD) and required portal questions.
  7. Storage: Validates the scraped data using the `Job` Pydantic model and saves it to the database via `JobRepository`.

## 2. Data Structures & Interfaces
* **Interface:** `src/core/scraper.py` will define an abstract base class `BaseScraper`.
* **Contract:** `async def scrape(self, url: str) -> List[Job]:` 
* Ensures a unified interface so we can easily add `LeverScraper` or `WorkdayScraper` in the future. Data will strict-match the existing Pydantic `Job` model.

## 3. Edge Cases & Failure Modes
* **Stale Selectors:** We will rely on structural or ARIA-based Playwright locators rather than brittle CSS utility classes.
* **Rate Limiting & Bot Detection:** Implements random jitter (e.g., `asyncio.sleep(random.uniform(1.0, 3.0))`) between navigations.
* **Timeouts:** All remote page interactions will be wrapped in try/except blocks with explicit timeouts to prevent the worker daemon from crashing.

## 4. Integration with TitanStore (Repository)
* **Strict Decoupling:** The scraper will not know about TCP sockets or the TitanStore explicitly. It will be initialized with an instance of `JobRepository`.
* **Flow:** Calls `repository.get_job()` to check for duplication, and `repository.save_job()` upon successful scrape.
# Sourcing Engine Design (Phase 1)

## 1. Architecture and Data Flow
The Sourcing Engine operates as a completely decoupled background daemon. It runs independently from the Streamlit UI, preventing unresponsiveness caused by heavy network I/O or DOM parsing.

*   **Execution Model:** A standalone Python process (`src/scrapers/worker.py`) that wakes up on a configurable interval (default: 12 hours, set via `SCRAPER_INTERVAL_HOURS` env variable).
*   **Orchestration:** When awake, it accepts an explicit `SearchIntent` (Role, Location, Volume) and utilizes the universal `jobspy` scraper to concurrently query aggregators (LinkedIn, Indeed, Glassdoor).
*   **Data Pipeline:** Raw scraped data -> Pydantic `Job` validation -> Deduplication check -> Persist to `JobRepository` -> Sleep.

## 2. Data Structures and Interfaces
*   **`SearchIntent` (Pydantic):** Defines the parameters of the scrape sweep.
*   **`Job` (Pydantic):** Strict validation of the scraped data. Must contain `id` (hash), `title`, `company`, `location`, `description`, `job_url`, and default `status` to `DISCOVERED`.
*   **`JobRepository` (Abstract Interface):** The abstract base class dictating storage. The scraper uses this interface, completely ignorant of whether the backend is `MockUIRepository` or the `TitanStoreClient`.

## 3. Edge Cases & Failure Modes
*   **Bot Detection / Captchas:** Scrapers will inevitably be blocked. We will implement exponential backoff and rotation settings provided by `jobspy`.
*   **DOM Structure Changes:** If aggregators change their UI, `jobspy` might return missing fields. The Pydantic model will enforce required fields; malformed jobs are logged and discarded, not pushed to the repository.
*   **Memory Leaks:** The background worker will forcefully garbage collect and release memory after each 12-hour sweep.

## 4. Integration with Existing Layers
The scraper depends entirely on the `JobRepository`. It will initialize the repository connector, inject it into the scraper runtime, and push verified `Job` instances using `repository.save_job(job)`. The Streamlit UI will subsequently read these jobs by calling `repository.get_pending_jobs()`.
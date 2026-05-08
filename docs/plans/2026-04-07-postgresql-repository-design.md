# Phase 8: PostgreSQL Repository Design

## 1. Architecture and Data Flow
To enable the Streamlit UI to dynamically filter and display jobs, and to provide enterprise-grade reliability, we are migrating from the custom TitanStore KV store to scalable PostgreSQL. 

* **Execution Model:** The system will connect to PostgreSQL using asynchronous drivers (`asyncpg`) managed by `SQLAlchemy 2.0`.
* **Connection Management:** SQLAlchemy's `AsyncEngine` will provide out-of-the-box connection pooling to handle 100+ concurrent connections from the background scraper daemon safely without port exhaustion.
* **Data Flow:** Scraped jobs are validated into Pydantic models -> Repositories map them to SQLAlchemy ORM models -> Upserted into PostgreSQL -> Streamlit UI queries the Repository for specific statuses.

## 2. Data Structures and Interfaces
* **SQLAlchemy declarative model (`JobModel`):** A direct mapping of the `src.core.models.Job` Pydantic model to a SQL Table (`jobs`).
  * `id`: String (Primary Key)
  * `title`, `company`, `location`, `description`, `job_url`: String
  * `status`: String (Mapped from the `JobStatus` enum)
* **`PostgresRepository` (Implements `JobRepository`):** 
  * `__init__(dsn: str)`: Initializes the async engine and session factory.
  * `async def save_job(job: Job) -> bool`: Executes an SQLite/PostgreSQL compliant UPSERT (Insert or Update on conflict) using the SQLAlchemy core to prevent duplicate key errors.
  * `async def get_job(job_id: str) -> Job | None`: Retrieves a job and parses it back into a Pydantic model.
  * `async def get_jobs_by_status(status: JobStatus) -> list[Job]`: A new method needed by the UI to fetch specific jobs (e.g., `PENDING_REVIEW`).

## 3. Edge Cases & Failure Modes
* **Missing Database/Tables:** System will include a programmatic initialization script (`init_db`) that uses `Base.metadata.create_all` to automatically construct tables if they do not exist.
* **Connection Drops:** Relies on SQLAlchemy's built-in pool pre-ping to verify connections before checking them out of the pool.
* **Test Isolation:** Tests will use an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) to ensure unit tests execute instantly without requiring a live Postgres instance running on the CI server.

# TITANSWARM — Master Architecture & Design Document

**Version:** 2.0 | **Last Updated:** 2026-04-07 | **Lead Engineer:** Zen

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Design Principles](#2-core-design-principles)
3. [System Component Diagram](#3-system-component-diagram)
4. [Technology Stack & Rationale](#4-technology-stack--rationale)
5. [Canonical Data Models](#5-canonical-data-models)
6. [Component Deep-Dives](#6-component-deep-dives)
7. [End-to-End Data Flow](#7-end-to-end-data-flow)
8. [Configuration & Secrets Management](#8-configuration--secrets-management)
9. [Observability Strategy](#9-observability-strategy)
10. [Security & Compliance](#10-security--compliance)
11. [Testing Strategy](#11-testing-strategy)
12. [Deployment Topology](#12-deployment-topology)
13. [Failure Modes & Resilience](#13-failure-modes--resilience)
14. [Development Roadmap](#14-development-roadmap)

---

## 1. Executive Summary

TitanSwarm is an autonomous, agentic job application Co-Pilot targeting Fall 2026 SWE recruitment. It eliminates the manual overhead of job hunting by automating discovery, ATS-optimized resume tailoring, and Q&A generation — while deliberately keeping a **human in the loop** for the final submission step to avoid bot-detection flags and recruiter stigma.

**Core value proposition:** The system handles 99% of the computational work (scraping, RAG synthesis, PDF generation) and delivers a ready-to-submit package to the user. The user's only job is to click "Submit" on the external portal.

**Design target:** Support 100+ concurrent users with clean horizontal scalability at the database and worker layers.

---

## 2. Core Design Principles

| # | Principle | Enforcement |
|---|-----------|-------------|
| 1 | **No Hallucinations** | The RAG engine is strictly sandboxed to `data/ledger.md`. The LLM prompt explicitly forbids inventing experience, tools, or credentials not present in the ledger. `temperature=0.0` is enforced on all synthesis calls. |
| 2 | **Repository Pattern** | All persistence logic is behind the `JobRepository` ABC. No component may import a database driver directly — they receive a `JobRepository` instance via constructor injection. |
| 3 | **Async-First** | All I/O-bound operations (DB reads/writes, LLM API calls, PDF rendering) are `async/await`. No blocking calls on the event loop. |
| 4 | **Strict Type Contracts** | All inter-component data is typed via Pydantic v2 models. Raw dicts and untyped DataFrames are validated at system boundaries before entering any business logic. |
| 5 | **Human-in-the-Loop** | The system never auto-submits to external job portals. All submissions are gated behind a human action in the Dispatch Terminal. |
| 6 | **Fail Loud, Recover Gracefully** | Components log errors at `ERROR` level with full context. The Sourcing Daemon recovers from per-sweep failures without crashing the process. |

---

## 3. System Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TITANSWARM RUNTIME                             │
│                                                                             │
│  ┌──────────────────────────────┐    ┌──────────────────────────────────┐  │
│  │     SOURCING DAEMON          │    │      DISPATCH TERMINAL           │  │
│  │     (src/scrapers/daemon.py) │    │      (src/ui/app.py — Streamlit) │  │
│  │                              │    │                                  │  │
│  │  ┌────────────────────────┐  │    │  ┌─────────────────────────────┐ │  │
│  │  │    SourcingEngine      │  │    │  │  Job Feed                   │ │  │
│  │  │  (worker.py)           │  │    │  │  My Applications (Kanban)   │ │  │
│  │  │                        │  │    │  │  Preferences / Ledger       │ │  │
│  │  │  JobSpy →              │  │    │  └──────────────┬──────────────┘ │  │
│  │  │  LinkedIn/Indeed/      │  │    │                 │ user actions    │  │
│  │  │  Glassdoor             │  │    └─────────────────┼────────────────┘  │
│  │  └──────────┬─────────────┘  │                      │                   │
│  │             │ await          │                      │ await             │
│  └─────────────┼────────────────┘                      │                   │
│                │                                        │                   │
│                ▼                                        ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    JobRepository  (ABC — src/core/repository.py)    │   │
│  │                                                                     │   │
│  │   save_job() │ get_job() │ update_status()                         │   │
│  │   get_jobs_by_status() │ count_all()                               │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                  ┌──────────────┴────────────────┐                         │
│                  │ PostgresRepository             │                         │
│                  │ (src/infrastructure/           │                         │
│                  │  postgres_repo.py)             │                         │
│                  │  SQLAlchemy async + UPSERT     │                         │
│                  └──────────────┬─────────────────┘                        │
│                                 │                                           │
│                                 ▼                                           │
│                  ┌──────────────────────────────┐                          │
│                  │         PostgreSQL            │                          │
│                  │         jobs  table           │                          │
│                  └──────────────────────────────┘                          │
│                                 │                                           │
│          PENDING_REVIEW jobs    │                                           │
│                  ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RAG TAILOR ENGINE                                │   │
│  │                                                                     │   │
│  │   ┌─────────────────────┐        ┌──────────────────────────────┐  │   │
│  │   │   LedgerManager     │        │         AITailor             │  │   │
│  │   │  (src/core/         │  facts │    (src/core/ai.py)          │  │   │
│  │   │   ledger.py)        │───────▶│    OpenAI gpt-4o-mini        │  │   │
│  │   │                     │        │    temperature=0.0           │  │   │
│  │   │  data/ledger.md     │        │    Structured output         │  │   │
│  │   │  → FAISS index      │        │    (TailoredApplication)     │  │   │
│  │   └─────────────────────┘        └──────────────┬───────────────┘  │   │
│  │                                                  │ JSON             │   │
│  └──────────────────────────────────────────────────┼─────────────────┘   │
│                                                      │                     │
│                                                      ▼                     │
│                              ┌──────────────────────────────┐              │
│                              │       PDF Generator          │              │
│                              │   (src/core/pdf_generator.py)│              │
│                              │   Jinja2 + Playwright        │              │
│                              │   → ATS-ready resume.pdf     │              │
│                              └──────────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack & Rationale

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **Language** | Python | 3.12 | Dominant ML/AI ecosystem; async support via `asyncio` |
| **UI Framework** | Streamlit | 1.55 | Fastest path to a production-ready data app without a separate frontend. Replaced React/TypeScript for MVP velocity. |
| **Scraping** | JobSpy | latest | Unified aggregator for LinkedIn, Indeed, Glassdoor with built-in anti-bot evasion. Avoids building per-site scraper adapters. |
| **ORM / DB Driver** | SQLAlchemy 2.0 (async) + asyncpg | 2.0 | Full async support, dialect-agnostic UPSERT, type-safe `mapped_column` syntax. `asyncpg` is the fastest PostgreSQL driver for Python. |
| **Dev / Test DB** | aiosqlite (in-memory SQLite) | latest | Zero-dependency test isolation. Same SQLAlchemy interface, no Docker required. |
| **Production DB** | PostgreSQL | 15+ | ACID guarantees, native JSONB (future), excellent async pooling, horizontally scalable via read replicas. |
| **Data Validation** | Pydantic v2 | 2.x | Runtime type enforcement at every system boundary. Structured output from OpenAI uses Pydantic models directly. |
| **Vector Store** | FAISS (CPU) | 1.13 | Runs fully locally; no network calls during resume synthesis. `IndexFlatL2` for exact nearest-neighbor search over small ledger corpora. |
| **Embeddings** | sentence-transformers `all-MiniLM-L6-v2` | latest | Lightweight, fast, no API cost for indexing the ledger. |
| **LLM** | OpenAI `gpt-4o-mini` | latest | Structured JSON output via `beta.chat.completions.parse`. Best cost/quality ratio for resume tailoring. Swappable via `AITailor` interface. |
| **PDF Rendering** | Jinja2 + Playwright (Chromium) | latest | HTML-to-PDF pipeline gives full CSS control over resume layout. ATS-readable (text-selectable PDF, not image). |

---

## 5. Canonical Data Models

### 5.1 `Job` — Core Domain Entity

```
src/core/models.py :: Job(BaseModel)

┌─────────────────┬──────────────┬────────────────────────────────────────────┐
│ Field           │ Type         │ Description                                │
├─────────────────┼──────────────┼────────────────────────────────────────────┤
│ id              │ str          │ Deterministic hash of job URL (e.g. li-1234)│
│ company         │ str          │ Hiring company name                        │
│ role            │ str          │ Job title (e.g. "Software Engineer Intern")│
│ status          │ JobStatus    │ Current lifecycle state (see §5.2)         │
│ job_description │ str          │ Full raw JD text from scraper              │
│ required_skills │ list[str]    │ Skills extracted from JD for RAG query     │
│ custom_questions│ list[str]    │ Portal-specific application questions       │
│ url             │ str          │ External application URL                   │
└─────────────────┴──────────────┴────────────────────────────────────────────┘
```

### 5.2 `JobStatus` — State Machine

Every `Job` transitions through a strict state machine. Invalid transitions are rejected.

```
                    ┌─────────────────────────────┐
                    │         [Error]              │◀── any state on exception
                    └─────────────────────────────┘

  Scraper saves ──▶ DISCOVERED ──▶ PROCESSING ──▶ PENDING_REVIEW
                                                        │
                                              ┌─────────┴─────────┐
                                              ▼                   ▼
                                         SUBMITTED            REJECTED
                                              │              (user skips)
                                    ┌─────────┴─────────┐
                                    ▼                   ▼
                                INTERVIEW           REJECTED
                              (recruiter           (ghosted)
                               responds)
```

| Transition | Trigger | Actor |
|------------|---------|-------|
| `DISCOVERED → PROCESSING` | RAG Tailor picks up job | Automated |
| `PROCESSING → PENDING_REVIEW` | PDF generation complete | Automated |
| `PENDING_REVIEW → SUBMITTED` | User clicks "Mark Submitted" in UI | Human |
| `PENDING_REVIEW → REJECTED` | User clicks "Skip" in UI | Human |
| `SUBMITTED → INTERVIEW` | User manually updates after callback | Human |
| `SUBMITTED → REJECTED` | User manually updates (ghosted) | Human |
| `ANY → ERROR` | Exception during processing | Automated |

### 5.3 `TailoredApplication`

```
src/core/models.py :: TailoredApplication(BaseModel)

┌──────────────────┬────────────────┬─────────────────────────────────────────┐
│ Field            │ Type           │ Description                             │
├──────────────────┼────────────────┼─────────────────────────────────────────┤
│ job_id           │ str            │ Foreign key to Job.id                   │
│ tailored_bullets │ list[str]      │ 3–5 ATS resume bullets from ledger facts│
│ q_and_a_responses│ dict[str, str] │ Portal question → 150-word answer       │
└──────────────────┴────────────────┴─────────────────────────────────────────┘
```

### 5.4 `UserProfile`

```
src/core/models.py :: UserProfile(BaseModel)

┌──────────────┬──────────────┬────────────────────────────────────────────────┐
│ Field        │ Type         │ Description                                    │
├──────────────┼──────────────┼────────────────────────────────────────────────┤
│ name         │ str          │ Full name                                      │
│ email        │ str          │ Contact email                                  │
│ phone        │ str          │ Contact phone                                  │
│ github       │ str          │ GitHub profile URL                             │
│ linkedin     │ str          │ LinkedIn profile URL                           │
│ base_summary │ str          │ Elevator pitch — injected into every tailoring │
│ skills       │ list[str]    │ Master skills list for ATS scoring             │
│ experience   │ list[dict]   │ Structured work/project history                │
└──────────────┴──────────────┴────────────────────────────────────────────────┘
```

---

## 6. Component Deep-Dives

### 6.1 Sourcing Engine

**Files:** `src/scrapers/worker.py`, `src/scrapers/daemon.py`

**Responsibilities:**
- Concurrently query LinkedIn, Indeed, and Glassdoor via JobSpy
- Deduplicate against the repository using `get_job()` (O(1) primary key lookup)
- Normalize raw Pandas `DataFrame` rows into typed `Job` Pydantic models
- Persist new jobs via `save_job()` (UPSERT — safe to re-run)

**Daemon lifecycle:**
```
asyncio.run(main())
  │
  ├── PostgresRepository(dsn).init_db()   # create tables if not exist
  ├── SourcingEngine(repository, interval)
  │
  └── while True:
        ├── run_sweep(role, location, results_wanted)
        │     ├── jobspy.scrape_jobs(...)       # blocking I/O — runs in thread
        │     ├── for each row:
        │     │     ├── get_job(id)             # dedup check
        │     │     ├── validate → Job model
        │     │     └── save_job(job)           # UPSERT
        │     └── return saved_count
        │
        └── asyncio.sleep(interval_hours * 3600)
```

**Deduplication strategy:** Hash ID is the job's unique identifier from the source board (e.g., `li-1234`). The UPSERT in `PostgresRepository.save_job()` is idempotent — a re-scraped job will update in place without creating a duplicate row.

---

### 6.2 Repository Layer

**Files:** `src/core/repository.py`, `src/infrastructure/postgres_repo.py`, `src/ui/mock_repo.py`

**The `JobRepository` ABC** is the contract every storage backend must implement. No component in the business logic layer may import `postgres_repo` directly — they receive a repository instance via constructor injection.

```
JobRepository (ABC)
├── PostgresRepository     ← production (SQLAlchemy + asyncpg / aiosqlite)
└── MockUIRepository       ← unit tests and UI dev mode
```

**`PostgresRepository` internals:**
- SQLAlchemy `async_sessionmaker` with `expire_on_commit=False`
- Dialect-aware UPSERT: `postgresql.insert(...).on_conflict_do_update(...)` vs. `sqlite.insert(...).on_conflict_do_update(...)`
- `init_db()` must be called once at process startup to auto-create the `jobs` table
- `close()` disposes the engine connection pool on clean shutdown

**Database schema (`jobs` table):**
```sql
CREATE TABLE jobs (
    id              VARCHAR PRIMARY KEY,
    company         VARCHAR NOT NULL,
    role            VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,   -- JobStatus enum value
    job_description VARCHAR NOT NULL,
    url             VARCHAR NOT NULL
);
```

---

### 6.3 RAG Tailor & Ingestion Engine

**Files:** `src/core/ledger.py`, `src/core/ai.py`, `data/ledger.md`

**Two-stage pipeline:**

**Stage A — Ingestion (run once / on update):**
```
data/ledger.md
  │
  ├── Read & chunk by double-newline (paragraph boundaries)
  ├── SentenceTransformer('all-MiniLM-L6-v2').encode(chunks)
  │     → float32 embeddings, dim=384
  └── faiss.IndexFlatL2(384).add(embeddings)
        → in-memory FAISS index
```

**Stage B — Synthesis (per job):**
```
Job.role + Job.required_skills
  │
  ├── LedgerManager.search_facts(query, top_k=4)
  │     → cosine-nearest chunks from ledger
  │
  └── AITailor.tailor_application(job)
        ├── System prompt: STRICT hallucination guard + ledger facts
        ├── User prompt: full Job Description
        ├── gpt-4o-mini, temperature=0.0
        └── Structured output → TailoredApplication (Pydantic)
```

**Hallucination prevention:** The system prompt explicitly states the model is "FORBIDDEN from inventing or hallucinating ANY experience, tools, or jobs." Only facts retrieved from the FAISS index are injected into context. Facts not present in the ledger are omitted, not invented.

---

### 6.4 PDF Generator

**File:** `src/core/pdf_generator.py`, `src/core/templates/resume.html`

**Pipeline:**
```
UserProfile (ledger dict) + TailoredApplication
  │
  ├── Jinja2.render(resume.html)   → rendered HTML string
  │
  └── Playwright (headless Chromium)
        ├── page.set_content(html)
        └── page.pdf(format="Letter", print_background=True)
              → output/resume.pdf
```

**Output characteristics:**
- Letter format (8.5" × 11"), zero margins
- Text-selectable PDF (not image-rendered) — ATS-parseable
- Layout controlled entirely via CSS in `resume.html`

---

### 6.5 Dispatch Terminal (Streamlit UI)

**File:** `src/ui/app.py`

**Three-page architecture:**

| Page | Purpose | Key Actions |
|------|---------|-------------|
| **Job Feed** | Discover and evaluate new jobs | Search by role/location → run sweep → review job cards → ⚡ Auto-Apply or Skip |
| **My Applications** | Track pipeline status | 4-column Kanban (Pending Review / Applied / Interview / Rejected) |
| **Preferences** | Configure profile and job targeting | Profile completion meter, Immutable Facts Ledger editor, work mode / job type prefs |

**Repository connection:** UI connects to `PostgresRepository` using `DATABASE_URL` env var, falling back to `sqlite+aiosqlite:///titanswarm.db` in local dev mode. `asyncio.run()` bridges Streamlit's synchronous event loop to the async repository interface.

---

## 7. End-to-End Data Flow

```
User enters "Software Engineer Intern, Vancouver" in Job Feed
  │
  ▼
SourcingEngine.run_sweep("Software Engineer Intern", "Vancouver", results_wanted=25)
  │
  ├── JobSpy queries LinkedIn + Indeed + Glassdoor concurrently
  ├── Raw DataFrame rows → validated Job(status=DISCOVERED) models
  ├── get_job(id) → None (new) → save_job(job)  [UPSERT]
  └── Returns: 12 new jobs saved
  │
  ▼
UI renders Job Feed cards from get_jobs_by_status(PENDING_REVIEW)
  │
User clicks "⚡ Auto-Apply" on a job card
  │
  ├── AITailor.tailor_application(job)
  │     ├── LedgerManager.search_facts(query) → top 4 ledger chunks
  │     ├── OpenAI API call (gpt-4o-mini, temp=0.0)
  │     └── Returns TailoredApplication (bullets + Q&A)
  │
  ├── PDFGenerator.generate_resume_pdf(ledger, tailored_app)
  │     └── Returns: output/resume_{job_id}.pdf
  │
  └── update_status(job_id, PENDING_REVIEW)   [ready for human review]
  │
  ▼
User downloads PDF → manually submits to external portal
  │
User clicks "Mark as Submitted" in UI
  │
  └── update_status(job_id, SUBMITTED)
```

---

## 8. Configuration & Secrets Management

All configuration is injected via environment variables. No secrets are hardcoded.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite+aiosqlite:///titanswarm.db` | SQLAlchemy async DSN. Set to `postgresql+asyncpg://user:pass@host:5432/titanswarm` in production. |
| `OPENAI_API_KEY` | **Yes** (for RAG) | `None` | OpenAI API key. `AITailor` raises `ValueError` on startup if missing. |
| `SCRAPER_ROLE` | No | `Software Engineer` | Target job title for the Sourcing Daemon. |
| `SCRAPER_LOCATION` | No | `Vancouver, BC` | Target location for the Sourcing Daemon. |
| `SCRAPER_INTERVAL_HOURS` | No | `12` | Hours between Daemon scraping sweeps. |
| `SCRAPER_RESULTS_WANTED` | No | `10` | Maximum jobs to fetch per sweep per site. |

**Local development:** Create a `.env` file at the project root (never commit it). Load with `python-dotenv` or `export` manually before running.

---

## 9. Observability Strategy

### Logging

All components use Python's `logging` module. The standard format is:

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

| Logger Name | Component | Key Events Logged |
|-------------|-----------|-------------------|
| `SourcingDaemon` | `daemon.py` | Sweep start, jobs saved count, errors, shutdown |
| `SourcingEngine` | `worker.py` | Duplicate skips, new job saves, empty sweep warning |
| `root` | All | Uncaught exceptions at ERROR level |

### Log Levels

| Level | Used For |
|-------|---------|
| `DEBUG` | Duplicate job skips (high volume, off by default) |
| `INFO` | Sweep lifecycle events, job counts |
| `WARNING` | Unexpected but recoverable states (e.g. empty DataFrame) |
| `ERROR` | Per-sweep failures caught by Daemon (process continues) |
| `CRITICAL` | Reserved for unrecoverable startup failures |

### Future: Metrics

Planned additions for scaling phase:
- Prometheus counters: `jobs_scraped_total`, `jobs_applied_total`, `ai_calls_total`, `ai_call_latency_seconds`
- Grafana dashboard for real-time pipeline visibility

---

## 10. Security & Compliance

| Concern | Mitigation |
|---------|-----------|
| **Secret exposure** | All API keys and DSNs loaded from env vars. `.env` is `.gitignore`d. |
| **SQL injection** | SQLAlchemy ORM with parameterized queries. No raw SQL string interpolation. |
| **Prompt injection** | LLM input is structured Pydantic output from the scraper, not raw user text. Ledger facts are pre-indexed at ingestion time. |
| **ATS bot detection** | System never auto-submits to external portals. Human-in-the-loop ensures no automated form submission. |
| **Scraping ethics** | JobSpy respects `robots.txt` rate limits. Targets publicly accessible job listing pages only. |
| **Data at rest** | `data/ledger.md` is stored locally. No user PII is sent to external services except the OpenAI API for tailoring. |
| **Dependency hygiene** | All dependencies pinned in `requirements.txt`. Review with `pip audit` before production deploy. |

---

## 11. Testing Strategy

### Test Boundaries

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TEST PYRAMID                                │
│                                                                     │
│                            ▲                                        │
│                           ╱ ╲    E2E (scripts/e2e_backend_mock.py) │
│                          ╱───╲   Manual / against live DB           │
│                         ╱─────╲                                     │
│                        ╱───────╲  Integration Tests                │
│                       ╱  SQLite ╲  (test_postgres_repo.py)         │
│                      ╱  in-memory╲ Real async I/O, no PostgreSQL   │
│                     ╱─────────────╲                                 │
│                    ╱               ╲  Unit Tests  (all other tests) │
│                   ╱  AsyncMock /    ╲ Isolated, no I/O             │
│                  ╱   MockUIRepository╲                              │
│                 ╱─────────────────────╲                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Test Files

| File | Scope | Strategy |
|------|-------|---------|
| `test_models.py` | Pydantic models | Pure unit — no I/O |
| `test_repository.py` | `JobRepository` ABC contract | `GoodRepo` concrete stub — verifies interface completeness |
| `test_postgres_repo.py` | `PostgresRepository` | Integration — `sqlite+aiosqlite:///:memory:` via `pytest_asyncio` fixture |
| `test_sourcing_engine.py` | `SourcingEngine.run_sweep()` | Unit — `AsyncMock` repository, no JobSpy calls |
| `test_ai.py` | `AITailor.tailor_application()` | Unit — mocked `_call_openai()` |
| `test_ledger.py` | `LedgerManager` | Unit — reads `data/ledger.md` directly |
| `test_pdf_generator.py` | `PDFGenerator` | Unit — mocked Playwright |
| `test_mock_ui_repo.py` | `MockUIRepository` | Unit — verifies ABC contract adherence |

### Conventions

- `pytest-asyncio` in **STRICT mode**: all async tests require `@pytest.mark.asyncio`
- Async fixtures use `@pytest_asyncio.fixture`, not `@pytest.fixture`
- `AsyncMock` from `unittest.mock` for async interface mocking
- No test may reach a live external service (network, OpenAI, PostgreSQL)

---

## 12. Deployment Topology

### Local Development (default)
```
DATABASE_URL = sqlite+aiosqlite:///titanswarm.db   (auto-created on first run)
OPENAI_API_KEY = <from .env>

Start UI:      .venv/bin/streamlit run src/ui/app.py --server.port 8501
Start Daemon:  python -m src.scrapers.daemon
```

### Docker Compose (staging)
```yaml
# Planned docker-compose.yml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: titanswarm
      POSTGRES_USER: titan
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  ui:
    build: .
    command: streamlit run src/ui/app.py --server.port 8501 --server.headless true
    environment:
      DATABASE_URL: postgresql+asyncpg://titan:${DB_PASSWORD}@db:5432/titanswarm
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8501:8501"
    depends_on: [db]

  daemon:
    build: .
    command: python -m src.scrapers.daemon
    environment:
      DATABASE_URL: postgresql+asyncpg://titan:${DB_PASSWORD}@db:5432/titanswarm
      SCRAPER_ROLE: "Software Engineer Intern"
      SCRAPER_LOCATION: "Vancouver, BC"
      SCRAPER_INTERVAL_HOURS: "6"
    depends_on: [db]
```

### Production
- PostgreSQL 15 on managed cloud (e.g., Supabase, Railway, AWS RDS)
- UI and Daemon as separate services / containers
- `DATABASE_URL` injected via secrets manager (never plaintext env in CI/CD)
- Connection pooling via `asyncpg` pool size tuned to Postgres `max_connections`

---

## 13. Failure Modes & Resilience

| Component | Failure Mode | Impact | Recovery Strategy |
|-----------|-------------|--------|-------------------|
| **JobSpy** | Returns empty DataFrame (rate-limited / site down) | Zero jobs saved this sweep | Log warning, Daemon sleeps and retries next interval |
| **JobSpy** | Raises exception | Sweep aborts | Daemon catches exception at sweep level, logs ERROR, continues loop |
| **PostgresRepository** | DB unreachable at startup | Process crashes | `init_db()` raises — Daemon exits with clear error message |
| **PostgresRepository** | DB unreachable mid-sweep | `save_job()` raises | Exception propagates to Daemon sweep handler, logged as ERROR |
| **OpenAI API** | Rate limit / network error | Tailoring fails | `AITailor.tailor_application()` raises — UI shows error toast, job stays in `PENDING_REVIEW` |
| **OpenAI API** | Invalid structured output | Pydantic parse fails | Returns `None` — job flagged as `ERROR` |
| **Playwright / PDF** | Chromium unavailable | PDF generation fails | `PDFGenerator` raises — UI shows error, tailored text still available |
| **LedgerManager** | `data/ledger.md` missing | Index build fails | Raises `FileNotFoundError` — `AITailor` catches and uses empty facts, warns in logs |
| **FAISS** | `.search_facts()` before `build_index()` | Raises `RuntimeError` | Caught in `AITailor`, falls back to empty facts list |

---

## 14. Development Roadmap

**Legend:** ✅ Complete · 🔄 Partial / In Progress · ⏳ Planned

| Week | Milestone | Status | Notes |
|------|-----------|--------|-------|
| 1 | Pydantic models (`Job`, `JobStatus`, `TailoredApplication`, `UserProfile`) | ✅ | `src/core/models.py` |
| 1 | `JobRepository` ABC (5 abstract methods) | ✅ | `src/core/repository.py` |
| 1 | `PostgresRepository` with dialect-aware UPSERT | ✅ | `src/infrastructure/postgres_repo.py` |
| 2 | `SourcingEngine.run_sweep()` (async, deduplication) | ✅ | `src/scrapers/worker.py` |
| 2 | `SourcingDaemon` with env-driven config | ✅ | `src/scrapers/daemon.py` |
| 3 | Immutable Facts Ledger (`data/ledger.md`) | ✅ | SFU history, TitanSwarm, TitanStore projects |
| 3 | `LedgerManager` — FAISS ingestion + similarity search | ✅ | `src/core/ledger.py` |
| 4 | `AITailor` — strict RAG prompting, structured output | ✅ | `src/core/ai.py` |
| 5 | `PDFGenerator` — Jinja2 + Playwright HTML-to-PDF | ✅ | `src/core/pdf_generator.py` |
| 6 | Dispatch Terminal — Job Feed, Kanban, Preferences | ✅ | `src/ui/app.py` (aiapply.co pattern) |
| 6 | Wire real `SourcingEngine` to Job Feed discovery | 🔄 | Currently mock data in `_run_discovery()` |
| 6 | Wire real `PDFGenerator` to Auto-Apply button | 🔄 | Currently returns placeholder bytes |
| 7 | Docker Compose — PostgreSQL + UI + Daemon | ⏳ | `docker-compose.yml` |
| 7 | Concurrent Daemon workers (multi-role/location) | ⏳ | `asyncio.gather()` over multiple `run_sweep()` calls |
| 7 | Connection pool tuning for 100+ concurrent users | ⏳ | SQLAlchemy pool config + Postgres `max_connections` |
| 8 | Alembic migrations | ⏳ | Schema version management for production |
| 8 | Prometheus metrics + Grafana dashboard | ⏳ | `jobs_scraped_total`, `ai_call_latency_seconds` |
| 8 | `pip audit` + dependency CVE review | ⏳ | Before any public/cloud deployment |
# TITANSWARM — Master Architecture & Design Document

**Version:** 3.0 | **Last Updated:** 2026-05-09 | **Lead Engineer:** Zen

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Design Principles](#2-core-design-principles)
3. [System Component Diagram](#3-system-component-diagram)
4. [Technology Stack](#4-technology-stack)
5. [Canonical Data Models](#5-canonical-data-models)
6. [Component Deep-Dives](#6-component-deep-dives)
7. [End-to-End Data Flow](#7-end-to-end-data-flow)
8. [Configuration & Secrets Management](#8-configuration--secrets-management)
9. [Security & Compliance](#9-security--compliance)
10. [Observability Strategy](#10-observability-strategy)
11. [Testing Strategy](#11-testing-strategy)
12. [Deployment Topology](#12-deployment-topology)
13. [Failure Modes & Resilience](#13-failure-modes--resilience)
14. [Development Roadmap](#14-development-roadmap)

---

## 1. Executive Summary

TitanSwarm is an autonomous, agentic job application Co-Pilot targeting Fall 2026 SWE recruitment. It automates discovery, ATS-optimized resume tailoring, cover letter generation, and Q&A preparation — while keeping a **human in the loop** for final submission.

**Core value proposition:** The system handles 99% of the computational work (scraping, RAG synthesis, PDF generation) and delivers a ready-to-submit package. The user's only job is to click "Submit" on the external portal.

**Design target:** Multi-tenant architecture supporting concurrent users with per-user data isolation and cookie-based authentication.

---

## 2. Core Design Principles

| # | Principle | Enforcement |
|---|-----------|-------------|
| 1 | **Zero Hallucination** | RAG engine sandboxed to user's personal ledger via FAISS. LLM prompt forbids inventing experience not in context. `temperature=0.2` on all synthesis calls. |
| 2 | **Repository Pattern** | All persistence behind `JobRepository` ABC. No component imports a database driver directly — receives a repository via constructor injection. |
| 3 | **Async-First** | All I/O (DB, LLM API, PDF rendering) uses `async/await`. Blocking calls (JobSpy) are wrapped in `run_in_executor`. |
| 4 | **Strict Type Contracts** | All inter-component data typed via Pydantic v2 models. Raw DataFrames validated at system boundaries. |
| 5 | **Human-in-the-Loop** | System never auto-submits to external portals. All submissions gated behind human action. |
| 6 | **Fail Loud, Recover Gracefully** | Components log at `ERROR` with full context. Daemon recovers from per-sweep failures without crashing. Model cascade provides LLM fallback. |

---

## 3. System Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TITANSWARM RUNTIME                             │
│                                                                             │
│  ┌──────────────────────────────┐    ┌──────────────────────────────────┐  │
│  │     SOURCING DAEMON          │    │      DISPATCH TERMINAL           │  │
│  │     (src/scrapers/)          │    │      (src/ui/ — Streamlit)       │  │
│  │                              │    │                                  │  │
│  │  SourcingEngine              │    │  app.py (router)                 │  │
│  │  JobSpy → LinkedIn / Indeed  │    │  ├── pages/job_feed.py           │  │
│  │  Title filter + dedup        │    │  ├── pages/applications.py       │  │
│  └──────────┬───────────────────┘    │  ├── pages/preferences.py        │  │
│             │ await                  │  ├── auth.py (cookie + rate limit)│  │
│             │                        │  ├── state.py (session init)      │  │
│             │                        │  ├── styles.py (CSS)              │  │
│             │                        │  └── components.py (helpers)      │  │
│             │                        └──────────────┬───────────────────┘  │
│             │                                       │                      │
│             ▼                                       ▼                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    JobRepository  (ABC)                              │   │
│  │   SQLite (dev) ←──────────────────────→ PostgreSQL 15+ (prod)       │   │
│  │   PostgresRepository (SQLAlchemy 2.0 async, dialect-aware UPSERT)   │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                          │
│               ┌─────────────────┴─────────────────┐                       │
│               ▼                                   ▼                       │
│  ┌──────────────────────┐            ┌──────────────────────────┐         │
│  │   RAG Tailor Engine   │            │   PDF Generator           │         │
│  │                       │            │                            │         │
│  │  LedgerManager        │            │  Jinja2 + Playwright       │         │
│  │  FAISS + MiniLM-L6-v2 │───────────→│  (Chromium headless)       │         │
│  │  Gemini 2.5 Flash Lite│            │  ATS-readable PDF output   │         │
│  │  Model cascade fallback│           │  Resume + Cover Letter     │         │
│  └──────────────────────┘            └──────────────────────────┘         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │   Config Layer  (src/core/config.py — Pydantic Settings singleton)  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Language** | Python 3.12 | Dominant ML/AI ecosystem; native async support |
| **UI** | Streamlit 1.55 | Fastest path to production data app without separate frontend |
| **Scraping** | python-jobspy | Unified aggregator for LinkedIn, Indeed with built-in anti-bot evasion |
| **ORM** | SQLAlchemy 2.0 (async) + asyncpg | Dialect-agnostic UPSERT, type-safe mapped_column, fastest Postgres driver |
| **Dev DB** | aiosqlite (SQLite) | Zero-dependency test isolation, same SQLAlchemy interface |
| **Prod DB** | PostgreSQL 15+ | ACID, native JSONB, async pooling, horizontally scalable |
| **Validation** | Pydantic v2 | Runtime type enforcement at every system boundary |
| **Config** | pydantic-settings | Typed, validated env var parsing with fail-fast startup |
| **Vector Store** | FAISS (CPU) | Fully local; no network calls during synthesis |
| **Embeddings** | sentence-transformers `all-MiniLM-L6-v2` | Lightweight, fast, no API cost |
| **LLM** | Gemini 2.5 Flash Lite (primary) | Free tier, structured JSON output. Model cascade fallback for 503s |
| **LLM (alt)** | OpenAI gpt-4o-mini | Optional provider via `AI_PROVIDER=openai` |
| **PDF** | Jinja2 + Playwright (Chromium) | Full CSS control, text-selectable ATS-readable output |
| **Auth** | bcrypt + HMAC-signed cookies | Secure password hashing, stateless session management |
| **CI/CD** | GitHub Actions | Lint + test gate before deploy to DigitalOcean |

---

## 5. Canonical Data Models

All models defined in `src/core/models.py`.

### 5.1 `Job` — Core Domain Entity

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Deterministic hash from source board (e.g. `li-1234`) |
| `company` | `str` | Hiring company name |
| `role` | `str` | Job title |
| `status` | `JobStatus` | Current lifecycle state (see §5.2) |
| `job_description` | `str` | Full raw JD text |
| `required_skills` | `list[str]` | Skills extracted from JD |
| `custom_questions` | `list[str]` | Portal-specific application questions |
| `url` | `str` | External application URL |
| `location` | `str` | Job location |
| `date_posted` | `str` | ISO date string |
| `salary_min/max` | `float \| None` | Salary range |
| `salary_currency` | `str` | Currency code (e.g. `CAD`, `USD`) |
| `salary_interval` | `str` | Pay period (`yearly`, `hourly`, `monthly`) |

### 5.2 `JobStatus` — State Machine

```
  Scraper saves ──▶ DISCOVERED ──────────────▶ PENDING_REVIEW
                                                      │
                                            ┌─────────┴─────────┐
                                            ▼                   ▼
                                       SUBMITTED            REJECTED
                                            │
                                  ┌─────────┴─────────┐
                                  ▼                   ▼
                              INTERVIEW           REJECTED

  Any state ──▶ ERROR  (on unrecoverable exception)
```

### 5.3 `TailoredApplication`

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `str` | Foreign key to Job |
| `skills_to_highlight` | `dict[str, list[str]]` | Categorized skills from resume relevant to JD |
| `tailored_projects` | `list[TailoredProject]` | Projects with bullets rewritten for this JD |
| `tailored_experience` | `list[TailoredExperience]` | Work entries with bullets rewritten for this JD |
| `tailored_education` | `list[TailoredEducation]` | Education entries from source facts |
| `q_and_a_responses` | `dict[str, str]` | Portal question → answer |
| `missing_skills` | `list[str]` | Skills in JD not present in candidate's context |
| `work_experience_relevant` | `bool` | Whether work experience is tech-relevant |

### 5.4 `UserProfile`

| Field | Type | Description |
|-------|------|-------------|
| `name`, `email`, `phone` | `str` | Contact info |
| `github`, `linkedin`, `website` | `str` | Profile URLs |
| `base_summary` | `str` | Professional summary for RAG context |
| `skills` | `list[str]` | Master skills list |
| `education` | `list[dict]` | Structured education history |
| `experience` | `list[dict]` | Structured work history |
| `pref_role`, `pref_location` | `str` | Job targeting preferences |

### 5.5 `CoverLetterResult`

| Field | Type | Description |
|-------|------|-------------|
| `body` | `str` | Letter body paragraphs (no header/signature) |
| `company_address` | `str \| None` | Recipient address from JD, or null |

---

## 6. Component Deep-Dives

### 6.1 Sourcing Engine

**Files:** `src/scrapers/worker.py`, `src/scrapers/daemon.py`

The `SourcingEngine` wraps JobSpy with:
- **Title filtering:** Fuzzy match against target role to avoid irrelevant results
- **Country detection:** Auto-detects Indeed country code from location string
- **Salary extraction:** Parses `min_amount`, `max_amount`, `currency`, `interval` from raw data
- **Batch dedup:** Parallel `get_job()` checks via `asyncio.gather()` before saving
- **Thread isolation:** Blocking JobSpy calls wrapped in `asyncio.get_running_loop().run_in_executor()`

**Daemon lifecycle:**
```
asyncio.run(main())
  ├── PostgresRepository(dsn).init_db()
  ├── SourcingEngine(repository)
  └── while True:
        ├── for each role × location:
        │     └── run_sweep(role, location, results_wanted)
        └── asyncio.sleep(interval_hours * 3600)
```

### 6.2 Repository Layer

**Files:** `src/core/repository.py` (ABC), `src/infrastructure/postgres_repo.py`

```
JobRepository (ABC)
├── PostgresRepository     ← production (SQLAlchemy + asyncpg / aiosqlite)
└── MockUIRepository       ← unit tests (src/ui/mock_repo.py)
```

Key capabilities:
- Dialect-aware UPSERT (PostgreSQL vs SQLite syntax)
- Multi-tenant: all queries filtered by `user_id`
- Ledger persistence (per-user markdown storage)
- Profile persistence (JSON-serialized UserProfile)
- Tailored result persistence (AI JSON + PDF bytes + cover letter)
- Auth: `create_user()`, `verify_user()` with bcrypt hashing

### 6.3 RAG Tailor Engine

**Files:** `src/core/ai.py`, `src/core/ledger.py`

**Stage A — Ingestion:**
```
User's ledger (DB or file)
  ├── Chunk by paragraph boundaries
  ├── SentenceTransformer('all-MiniLM-L6-v2').encode(chunks) → float32[384]
  └── faiss.IndexFlatL2(384).add(embeddings) → in-memory FAISS index
```

**Stage B — Synthesis (per job):**
```
Job.role + Job.job_description
  ├── LedgerManager.search_facts(query, top_k=5) → nearest chunks
  └── AITailor.tailor_application(job)
        ├── System prompt: strict hallucination guard + ledger facts
        ├── Gemini 2.5 Flash Lite (primary) with model cascade fallback
        ├── temperature=0.2, structured JSON output
        └── Pydantic parse → TailoredApplication
```

**Model cascade:** If primary model returns 503/overloaded, automatically tries fallback models in sequence to ensure availability.

**Hallucination guard:** System prompt states model is "FORBIDDEN from inventing ANY experience, tools, or credentials not in the candidate's context." Temperature 0.2 ensures deterministic output.

### 6.4 PDF Generator

**Files:** `src/core/pdf_generator.py`, `src/core/templates/resume.html`

```
UserProfile + TailoredApplication
  ├── Jinja2.render(resume.html) → rendered HTML
  └── Playwright (headless Chromium)
        ├── page.set_content(html)
        └── page.pdf(format="Letter") → ATS-readable PDF
```

Generates both **resume PDFs** and **cover letter PDFs**. Text-selectable output (not image-rendered) ensures ATS parseability.

### 6.5 Match Scoring

**File:** `src/core/matching.py`

Hybrid 0–100 score: 50% semantic cosine similarity (sentence-transformer embeddings) + 50% keyword overlap (JD token fraction in resume). Cached per job-list fingerprint to avoid re-embedding on every UI rerun.

### 6.6 Dispatch Terminal (Modular Streamlit UI)

**Files:** `src/ui/` (modular package)

| Module | Lines | Responsibility |
|--------|-------|---------------|
| `app.py` | 168 | Page config, sidebar, navigation router |
| `auth.py` | 217 | HMAC cookie auth, rate limiter, login/register |
| `state.py` | 145 | Repository init, AI warm-up, cache management |
| `styles.py` | 193 | Global CSS injection |
| `components.py` | 356 | Pure helper functions (badge, avatar, filters) |
| `pages/job_feed.py` | 435 | Discovery, tailoring, download, cover letters |
| `pages/applications.py` | 160 | 4-column Kanban pipeline board |
| `pages/preferences.py` | 445 | Profile, daemon config, GitHub enrichment, resume upload |

### 6.7 Enrichment Modules

| Module | Purpose |
|--------|---------|
| `src/core/github_enricher.py` | Fetches public repos + READMEs via GitHub REST API, writes to ledger |
| `src/core/website_enricher.py` | Scrapes portfolio website, extracts structured data via Gemini |

---

## 7. End-to-End Data Flow

```
User searches "Software Engineer Intern, Vancouver" in Job Feed
  │
  ▼
SourcingEngine.run_sweep("Software Engineer Intern", "Vancouver", 50)
  ├── JobSpy queries LinkedIn + Indeed concurrently (in thread pool)
  ├── Title filter removes irrelevant results
  ├── Raw DataFrame → validated Job(status=DISCOVERED) models
  ├── Batch dedup via asyncio.gather → save new jobs (UPSERT)
  └── Returns: list of all job IDs
  │
  ▼
Job Feed renders cards with match scores (semantic + keyword hybrid)
  │
User clicks "📄 Tailor Resume" on a job card
  │
  ├── AITailor.tailor_application(job)
  │     ├── FAISS search → top-5 ledger chunks as context
  │     ├── Gemini API call (structured JSON output)
  │     └── Returns TailoredApplication (projects, skills, Q&A, gaps)
  │
  ├── PDFGenerator.generate_resume_pdf(user_ledger, tailored_app)
  │     └── Returns: output/{company}_{role}_Resume.pdf
  │
  ├── Persist to DB: AI JSON + PDF bytes
  ├── update_status(job_id, PENDING_REVIEW)
  └── Auto-download PDF to user's browser
  │
  ▼
User reviews PDF → manually submits to external portal
  │
User clicks "✅ Mark as Applied" → update_status(job_id, SUBMITTED)
```

---

## 8. Configuration & Secrets Management

All config is centralized in `src/core/config.py` via Pydantic Settings. Values are read from environment variables or `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `gemini` | LLM backend: `gemini` or `openai` |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `OPENAI_API_KEY` | — | OpenAI key (only if `AI_PROVIDER=openai`) |
| `DATABASE_URL` | `sqlite+aiosqlite:///titanswarm.db` | Async SQLAlchemy DSN |
| `SCRAPER_ROLES` | `Software Engineer Intern` | Pipe-separated target titles |
| `SCRAPER_LOCATIONS` | `Vancouver, BC` | Pipe-separated target locations |
| `SCRAPER_INTERVAL_HOURS` | `12` | Hours between daemon sweeps |
| `SCRAPER_RESULTS_WANTED` | `25` | Jobs per role/location per sweep |
| `SESSION_SECRET` | *(random per-process)* | HMAC secret for session cookies |

**Template:** Copy `.env.example` to `.env` and fill in values. The `.env` file is gitignored.

---

## 9. Security & Compliance

| Concern | Mitigation |
|---------|-----------|
| **Secret exposure** | All keys from env vars. `.env` gitignored. Pydantic Settings validates at startup. |
| **Authentication** | bcrypt password hashing + HMAC-signed session cookies with configurable secret |
| **Rate limiting** | Exponential backoff rate limiter on login attempts (5 attempts / 5-min window) |
| **SQL injection** | SQLAlchemy ORM with parameterized queries. No raw SQL interpolation. |
| **CORS/XSRF** | Streamlit CORS and XSRF protection enabled in production config |
| **Prompt injection** | LLM input is structured data from scraper, not raw user text. Ledger facts pre-indexed. |
| **Bot detection** | System never auto-submits. Human-in-the-loop for all external portal submissions. |
| **Data at rest** | Ledger stored per-user in DB. PII sent only to configured LLM API for tailoring. |
| **CI/CD security** | Server IP stored as GitHub secret. SSH deploy key with limited scope. |

---

## 10. Observability Strategy

All components use Python `logging` module with named loggers:

| Logger | Component | Key Events |
|--------|-----------|-----------|
| `src.scrapers.worker` | SourcingEngine | Sweep start, jobs saved, title filter stats |
| `src.scrapers.daemon` | Daemon | Cycle start, errors, shutdown |
| `src.core.scraper` | BaseScraper | Aggregation search, dedup results |
| `src.core.ai` | AITailor | Model cascade fallback, retry attempts |

**Future:** Prometheus counters (`jobs_scraped_total`, `ai_calls_total`, `ai_call_latency_seconds`) + Grafana dashboard.

---

## 11. Testing Strategy

```
                        ▲
                       ╱ ╲    E2E (manual against live DB)
                      ╱───╲
                     ╱─────╲  Integration (SQLite in-memory, real async I/O)
                    ╱───────╲
                   ╱─────────╲  Unit (AsyncMock, no I/O)
                  ╱───────────╲
```

| File | Scope | Strategy |
|------|-------|---------|
| `test_salary.py` | Salary parsing | Pure unit |
| `test_job_quality.py` | Job filtering/matching | Pure unit |
| `test_browser_manager.py` | BrowserManager | Unit — mocked Playwright |
| `test_pdf_generator.py` | PDFGenerator | Unit — mocked Playwright |

**CI:** GitHub Actions runs `pytest --tb=short -q` on every push/PR to `master`. All tests must pass before deploy.

**Conventions:**
- `pytest-asyncio` strict mode — all async tests require `@pytest.mark.asyncio`
- No test may reach a live external service
- In-memory SQLite for integration tests (same SQLAlchemy interface as production)

---

## 12. Deployment Topology

### Local Development
```bash
streamlit run src/ui/app.py          # UI on :8501
python -m src.scrapers.daemon        # Background scraper
# Uses SQLite by default (no DATABASE_URL needed)
```

### Production (Docker Compose on DigitalOcean)
```
┌──────────────────────────────────────────────────┐
│  DigitalOcean Droplet (4GB RAM / 2 vCPU)         │
│                                                    │
│  ┌─────────────┐  ┌──────────────┐                │
│  │ titanswarm_ui│  │titanswarm_   │                │
│  │ (Streamlit)  │  │daemon        │                │
│  │ :8501        │  │(background)  │                │
│  └──────┬───────┘  └──────┬───────┘                │
│         │                  │                        │
│         └────────┬─────────┘                        │
│                  ▼                                  │
│         Docker volumes:                             │
│         titanswarm_db, titanswarm_data,              │
│         titanswarm_output                            │
│                                                      │
│  ┌──────────────────────────────────┐               │
│  │  Nginx reverse proxy             │               │
│  │  + Let's Encrypt (HTTPS)         │               │
│  │  smartresume.dev → :8501          │               │
│  └──────────────────────────────────┘               │
└──────────────────────────────────────────────────────┘
```

### CI/CD Pipeline
```
Push to master → ci.yml (pytest) → deploy.yml (SSH → git pull → docker compose up)
```

---

## 13. Failure Modes & Resilience

| Component | Failure Mode | Recovery |
|-----------|-------------|----------|
| **JobSpy** | Empty DataFrame / rate-limited | Log warning, daemon sleeps and retries next cycle |
| **JobSpy** | Exception during scrape | Daemon catches at sweep level, logs ERROR, continues |
| **Database** | Unreachable at startup | `init_db()` raises — process exits with clear message |
| **Database** | Unreachable mid-sweep | Exception propagates to sweep handler, logged as ERROR |
| **Gemini API** | 503 / overloaded | Model cascade automatically tries fallback models |
| **Gemini API** | Rate limit | Exponential backoff retry with `tenacity` |
| **Gemini API** | Invalid JSON output | Pydantic parse fails — job stays in current status, error shown in UI |
| **Playwright** | Chromium unavailable | PDFGenerator raises — UI shows error toast, tailored text still usable |
| **FAISS** | Ledger missing / empty | AITailor catches, uses empty facts, warns in logs |
| **Auth** | Brute-force login | Rate limiter imposes exponential backoff after 5 failed attempts |

---

## 14. Development Roadmap

**Legend:** ✅ Complete · 🔄 In Progress · ⏳ Planned

| Milestone | Status |
|-----------|--------|
| Pydantic domain models (Job, TailoredApplication, UserProfile, CoverLetterResult) | ✅ |
| JobRepository ABC + PostgresRepository (dialect-aware UPSERT) | ✅ |
| SourcingEngine with title filter, salary extraction, batch dedup | ✅ |
| SourcingDaemon with multi-role/location concurrent sweeps | ✅ |
| LedgerManager — FAISS ingestion + similarity search | ✅ |
| AITailor — Gemini structured output, model cascade, hallucination guard | ✅ |
| Cover letter generation (CoverLetterResult) | ✅ |
| PDFGenerator — Resume + Cover Letter (Jinja2 + Playwright) | ✅ |
| Hybrid match scoring (semantic + keyword) | ✅ |
| GitHub + website enrichment modules | ✅ |
| Multi-tenant auth (bcrypt + HMAC cookies + rate limiter) | ✅ |
| Modular Streamlit UI (9 modules, page-based routing) | ✅ |
| Centralized config (Pydantic Settings) | ✅ |
| CI pipeline (GitHub Actions + pytest) | ✅ |
| Docker Compose deployment + Nginx HTTPS | ✅ |
| Alembic database migrations | ⏳ |
| Prometheus metrics + Grafana dashboard | ⏳ |
| Redis-backed rate limiter (multi-worker) | ⏳ |
| `pip audit` + dependency CVE review | ⏳ |
<p align="center">
  <strong>⚡ TitanSwarm</strong>
</p>

<p align="center">
  <strong>An applied AI infrastructure case study</strong> — autonomous job-application pipeline,<br>
  built end-to-end: distributed scraping, retrieval-augmented generation, and ATS-optimized PDF rendering<br>
  behind a multi-tenant service boundary.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/LLM-Gemini-orange?logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/DB-SQLite%20%7C%20PostgreSQL-336791?logo=postgresql&logoColor=white" alt="Database">
  <img src="https://img.shields.io/badge/Vector%20Store-FAISS%20(CPU)-8A2BE2" alt="FAISS">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

---

## Why this exists

I built TitanSwarm to solve a concrete operational bottleneck: **automating the internship hunt while carrying a full computing-science course load and a high-volume part-time job.** Manually discovering, screening, tailoring, and formatting applications consumed 15–20 hours a week of low-leverage work — precisely the kind of repetitive pipeline that should be automated end-to-end, with a human approving only the final click.

That constraint — *build real infrastructure on a student's budget and schedule* — shaped every architectural decision in this repository:

- **Cost discipline** — no paid vector database, no paid embedding API, no per-query spend beyond a free-tier LLM. Retrieval runs entirely on-device.
- **Time discipline** — a daemon that works while I sleep, which means the system must be crash-safe and self-healing, not demo-grade.
- **Tenancy discipline** — the bottleneck is shared, so the system is multi-tenant from the ground up, with per-user isolation treated as a *security boundary*, not a feature flag.

The result is production-shaped software: async-first, strictly typed at every boundary, fully tested, and deployable with a single command.

---

## What the system does

1. **Sourcing daemon** — a background worker pulls jobs from LinkedIn, Indeed, Glassdoor, and ZipRecruiter for every registered user, using their saved role and location preferences.
2. **RAG tailoring** — retrieves the most relevant chunks of a user's personal ledger and generates a tailored resume + cover letter, sandboxed against hallucination.
3. **PDF generation** — renders ATS-readable, text-selectable PDFs through headless Chromium.
4. **Dispatch terminal** — a Streamlit UI: job feed, kanban board, preferences, and analytics.

Two guarantees define the product boundary:

- 🔒 **Zero hallucination** — the LLM is restricted to facts present in retrieved ledger context. It cannot invent experience, credentials, or skills not in the user's source data.
- 🚫 **No auto-submission** — the system never submits to external portals. Every application is gated behind a human action, which also avoids bot-detection flags.

---

## Architecture

```
┌──────────────────────────────┐    ┌──────────────────────────────────┐
│     SOURCING DAEMON          │    │      DISPATCH TERMINAL           │
│  (Background job scraper)    │    │      (Streamlit Web UI)          │
│                              │    │                                  │
│  JobSpy → LinkedIn / Indeed  │    │  Job Feed  │  Kanban  │  Prefs   │
│  run_in_executor + gather    │    │  bcrypt + HMAC-signed sessions   │
└──────────────┬───────────────┘    └──────────────┬───────────────────┘
               │                                    │
               ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    JobRepository  (ABC)                              │
│   SQLite (dev) ←─────────────────────────→ PostgreSQL 15+ (prod)    │
│   Dialect-aware UPSERT · composite PK (id, user_id) · retry/backoff │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    ┌──────────────────┐            ┌──────────────────────┐
    │   RAG Tailor     │            │   PDF Generator      │
    │  FAISS + Gemini  │───────────→│  Jinja2 + Playwright │
    │  (zero halluc.)  │            │  (ATS-readable PDF)  │
    └──────────────────┘            └──────────────────────┘
```

**Four integrated layers:**

| Layer | Description | Files |
|-------|-------------|-------|
| **Sourcing Daemon** | Multi-tenant worker scraping LinkedIn & Indeed via JobSpy | `src/scrapers/` |
| **RAG Tailor Engine** | On-device FAISS retrieval + Gemini LLM for resume tailoring | `src/core/ai.py`, `src/core/ledger.py` |
| **PDF Generator** | Jinja2 + Playwright (Chromium) for ATS-readable PDFs | `src/core/pdf_generator.py` |
| **Dispatch Terminal** | Streamlit UI with auth, Job Feed, Kanban board, Preferences | `src/ui/` |

---

## Infrastructure decisions

### 1. Multi-tenant data isolation — fintech-grade boundaries

In a shared service, a tenant boundary is only as strong as its weakest query. A single `WHERE` clause forgotten in one method silently leaks one user's jobs into another's feed — which, in a fintech context, is a compliance event, not a bug. So isolation is enforced structurally, not by convention:

- **Tenant ID is part of the row identity.** `jobs` and `tailored_results` use composite primary keys — `(id, user_id)` and `(job_id, user_id)`. A row cannot exist without an owning tenant, and the same job ID can legally exist for two different users without collision.
- **`user_id` is threaded through the entire repository contract.** Every method on the `JobRepository` ABC — `save_job`, `get_job`, `get_jobs_by_status`, `save_profile`, `save_tailored_result` — takes a tenant scope. The abstract base class *forces* every future storage backend to handle tenancy; it cannot be forgotten in an implementation.
- **Per-user ledgers.** Each user's RAG source material lives in its own `user_ledgers` row, so retrieval can never bleed one person's experience or credentials into another person's resume.
- **Session layer.** Passwords are hashed with bcrypt (per-user salt) and never logged or stored in plaintext. Sessions are HMAC-SHA256-signed cookies verified in constant time via `hmac.compare_digest`, with a 7-day expiry window and an exponential-backoff login rate limiter (2s → 32s cooldown) to blunt credential-stuffing.
- **Lossless migration to tenancy.** Moving a live single-tenant database to composite keys was handled per-dialect: PostgreSQL drops and re-adds primary-key constraints (`DROP CONSTRAINT … CASCADE` → `ADD PRIMARY KEY`), while SQLite requires a full table rebuild (rename → recreate → copy → drop) because it cannot alter primary keys in place.

### 2. Concurrency & the scraping pipeline

The scraper is I/O-bound and adversarial by nature — third-party boards rate-limit, A/B-test their DOM, and fail independently. The pipeline is built so one failure can never take down a sweep:

- **Blocking work off the event loop.** JobSpy's synchronous scrapes run in a thread-pool executor via `asyncio.get_running_loop().run_in_executor()`, keeping the async daemon responsive while network I/O blocks worker threads.
- **Concurrent per-user sweeps.** `asyncio.gather()` runs every `(user, role, location)` sweep in its own coroutine. A LinkedIn 429 for user 2 is caught, logged, and contributes 0 — while users 1, 3, and 4 keep scraping.
- **Graceful board degradation.** If the combined multi-site call fails, the engine retries each board individually and unions the survivors, so one broken board can't zero out an entire sweep.
- **Atomic, dialect-aware dedup.** The same `save_job` call compiles to `INSERT … ON CONFLICT DO UPDATE` on PostgreSQL and `INSERT … ON CONFLICT DO NOTHING` on SQLite — dedup is atomic in both backends with no Python-side race.
- **Self-healing persistence.** Database initialization retries with exponential backoff (2s → 32s over 5 attempts) and `pool_pre_ping` evicts stale pooled connections after server restarts or idle timeouts.

**An honest note on rate limiting:** today, backpressure is delegated to JobSpy's built-in anti-bot evasion plus bounded `gather` concurrency. Fine-grained throttling, rotating headers, and a proper bounded work queue are explicitly on the roadmap (§ Future optimizations) — the current focus of active development.

### 3. Local vector search over a paid external API

The tailoring engine needs semantic retrieval, but the naive approach — an embedding API or a hosted vector database — violates the cost and privacy constraints of this project. Instead:

- **On-device FAISS index** (`IndexFlatL2`, CPU) with embeddings from `sentence-transformers/all-MiniLM-L6-v2` — a small, local model.
- **Zero network calls during synthesis.** Retrieval is a purely local operation; only the final generation step touches the network. No per-query API cost, no data leaves the machine, and latency is bounded by RAM, not by an external vendor's queue.
- **Cache-aware index lifecycle.** The index rebuilds only when the ledger's mtime changes, and query embeddings are memoized in a bounded LRU cache (32 entries) so repeated tailoring passes don't re-encode identical text.

This is a deliberate *system-boundary* decision: retrieval is a local concern, generation is a remote concern, and the seam between them is explicit.

### 4. The repository pattern as a boundary

All persistence flows through the `JobRepository` ABC. No component imports a database driver directly — the scraper, the UI, and the tailor all receive a repository via constructor injection. Storage is fully swappable between SQLite (dev, zero-dependency test isolation) and PostgreSQL (prod) without touching business logic, and the entire test suite runs against in-memory SQLite with mocked external APIs.

### 5. Resilience at the model boundary

LLMs are the least deterministic dependency in the stack, so the boundary is hardened:

- **Model cascade.** If the primary model returns 503 (overloaded), the engine falls through `flash-lite-001 → flash-001 → flash → gemma-3-27b-it`, deduplicating the chain at call time.
- **Deterministic synthesis.** Temperature is pinned to `0.2`, and the prompt is assembled *exclusively* from FAISS-retrieved ledger chunks, with the model explicitly instructed to refuse to invent anything not present in context.
- **Hybrid scoring.** Job/resume match scores blend 50% semantic cosine similarity with 50% keyword overlap, rescaled to 0–100, so ranking isn't gamed by either signal alone.

---

## Engineering challenges

The sections below are the walls I actually hit. They're documented here because they're the parts that can't be produced by prompting an LLM — they required debugging a live system.

### Challenge 1 — A persistent browser against an event loop that keeps dying

**The problem.** Streamlit tears down its asyncio event loop after every user interaction. A persistent Playwright browser (needed for PDF rendering and lazy job-description fetching) therefore couldn't live on the main loop — and launching a fresh Chromium per render was slow and leaked processes on crash.

**The solution.** A `BrowserManager` singleton owns a dedicated daemon thread running its *own* event loop. The main thread marshals work across the thread boundary with `asyncio.run_coroutine_threadsafe()` and `asyncio.wrap_future()`. Crucially, **Playwright objects never cross threads** — only strings and bytes do. `atexit` registers a cleanup hook so a crash or Ctrl+C closes the headless Chromium instead of orphaning it.

### Challenge 2 — Migrating a live schema to multi-tenant without data loss

**The problem.** The system shipped single-tenant with `user_id=1` hardcoded everywhere. Moving to composite primary keys `(id, user_id)` on an existing database had to be lossless, idempotent, and safe against old and new schemas alike.

**The solution.** Per-dialect migration: SQLite gets a full table rebuild under a synchronous connection (rename → recreate with composite PK → copy rows → drop legacy), while PostgreSQL uses `DROP CONSTRAINT … CASCADE` + `ADD PRIMARY KEY`. Column drift is resolved first by diffing `PRAGMA table_info` and adding any missing columns, so a year-old dev DB and a fresh prod DB converge to the same schema on startup.

### Challenge 3 — Scraped data that lies: salary and title edge cases

**The problem.** LinkedIn doesn't expose structured salary data, and boards inject off-target titles — "Research Intern – AI" for a "SWE Intern" search. A naive salary regex would also misread *"3–5 years experience"* as a $3–$5 salary range.

**The solution.** A two-part defense. A salary-regex fallback unescapes markdown, demands explicit currency and interval context ("CAD annually", "an hour"), and rejects sub-10 values so experience ranges can't become salaries. A vectorized pandas title filter — intern guard, seniority guard, and role-word guard — runs at C speed via `str.contains` instead of a Python callback per row, blocking irrelevant results before they reach the feed.

---

## Testing & quality

```bash
pytest --tb=short -q
```

The suite runs against in-memory SQLite with mocked external APIs — **no network calls, no API keys required.** Tests cover the repository contract (including the dialect-aware UPSERT and tenancy scoping), the sourcing engine's title/salary parsing, the RAG pipeline's hallucination guards, the daemon's failure isolation, the browser singleton, and the PDF generator. CI gates every push on the full suite before deployment.

---

## Future optimizations — current focus

The project is a living codebase, and the active work is at the *mechanics* level:

- **Custom data structures for the queue system.** Replace the current `list` + `asyncio.gather()` sweep with a custom-built, bounded priority work queue. This means reasoning explicitly about backpressure, cross-tenant fairness, retry/requeue semantics, and crash-recovery of in-flight work — instead of leaning on a high-level abstraction that hides those decisions.
- **Scraper hot path in Go.** Migrate the scraping engine to a compiled language for genuinely concurrent throughput (goroutines + channel-based fan-out), keeping Python for the ML/LLM orchestration where the ecosystem matters most. This is an active deep-dive into memory models, threading, and the cost of the GIL on I/O-bound fan-out.
- **Formalizing tenancy further.** Move from application-level `user_id` scoping toward row-level security or connection-level tenancy in PostgreSQL as the isolation guarantee hardens.

---

## Running locally

```bash
git clone https://github.com/ttn54/TitanSwarm.git
cd TitanSwarm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
cp .env.example .env        # add GEMINI_API_KEY; SQLite is the default DB

streamlit run src/ui/app.py           # terminal 1 — web UI
python -m src.scrapers.daemon         # terminal 2 — background scraper
```

Configuration is typed and fail-fast via a Pydantic `Settings` singleton (`src/core/config.py`) — invalid env vars crash at startup, not 20 minutes into a scrape. Key variables: `GEMINI_API_KEY`, `DATABASE_URL`, `SCRAPER_ROLES`, `SCRAPER_LOCATIONS`, `SCRAPER_INTERVAL_HOURS`, `SCRAPER_RESULTS_WANTED`, `SESSION_SECRET`. For a full component-by-component breakdown, see [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`docs/plans/`](docs/plans/).

---

## Deployment

One-command deploy via Docker Compose (`titanswarm_ui` + `titanswarm_daemon`), with data persisted in Docker volumes. HTTPS is terminated at Nginx with Let's Encrypt, and every push to `master` runs CI tests before auto-deploying via GitHub Actions. See [`DEPLOY.md`](DEPLOY.md) for the full topology.

---

## License

MIT


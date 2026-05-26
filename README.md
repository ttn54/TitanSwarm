<p align="center">
  <strong>⚡ TitanSwarm</strong>
</p>

<p align="center">
  Autonomous, agentic job application Co-Pilot<br>
  <a href="https://smartresume.dev">smartresume.dev</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-orange?logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/DB-SQLite%20%7C%20PostgreSQL-336791?logo=postgresql&logoColor=white" alt="Database">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

---

## What is TitanSwarm?

TitanSwarm automates the discovery, analysis, and tailoring of job applications — delivering a ready-to-submit resume + cover letter package while keeping a **human in the loop** for the final submission step.

The system handles 99% of the computational work (scraping, RAG-based resume tailoring, ATS-optimized PDF generation) and delivers a ready-to-submit package. Your only job is to click "Submit" on the external portal.

**Core guarantees:**
- 🔒 **Zero hallucination** — The LLM is strictly sandboxed to your personal ledger via RAG. It cannot invent experience, credentials, or skills not in your source data.
- 🚫 **No auto-submission** — The system never submits to external portals. Every application is gated behind a human action, avoiding bot-detection flags.
- 🏗️ **Multi-tenant** — Built for concurrent users with per-user data isolation and cookie-based auth.

---

## Architecture

```
┌──────────────────────────────┐    ┌──────────────────────────────────┐
│     SOURCING DAEMON          │    │      DISPATCH TERMINAL           │
│  (Background job scraper)    │    │      (Streamlit Web UI)          │
│                              │    │                                  │
│  JobSpy → LinkedIn / Indeed  │    │  Job Feed  │  Kanban  │  Prefs   │
└──────────────┬───────────────┘    └──────────────┬───────────────────┘
               │                                    │
               ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    JobRepository  (ABC)                              │
│   SQLite (dev) ←─────────────────────────→ PostgreSQL 15+ (prod)    │
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
| **Sourcing Daemon** | Background worker scraping LinkedIn & Indeed via JobSpy | `src/scrapers/` |
| **RAG Tailor Engine** | FAISS vector search + Gemini LLM for resume tailoring | `src/core/ai.py`, `src/core/ledger.py` |
| **PDF Generator** | Jinja2 + Playwright (Chromium) for ATS-readable PDFs | `src/core/pdf_generator.py` |
| **Dispatch Terminal** | Streamlit web UI with Job Feed, Kanban board, Preferences | `src/ui/app.py` |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12 |
| UI | Streamlit 1.55 |
| Job Scraping | python-jobspy (LinkedIn, Indeed) |
| Database | SQLite (dev) / PostgreSQL 15+ (prod) via SQLAlchemy 2.0 async |
| Vector Store | FAISS (CPU, local — no API calls during synthesis) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| LLM | Gemini 2.5 Flash Lite (primary) with model-cascade fallback |
| PDF Rendering | Jinja2 + Playwright (Chromium) |
| Data Validation | Pydantic v2 |
| Auth | bcrypt + HMAC-signed session cookies |
| Testing | pytest + pytest-asyncio |
| CI/CD | GitHub Actions → DigitalOcean Droplet |

---

## Prerequisites

- Python 3.12+
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/))
- Chromium (installed via Playwright)

---

## Quick Start

**1. Clone and create a virtual environment**

```bash
git clone https://github.com/ttn54/TitanSwarm.git
cd TitanSwarm
python -m venv .venv
source .venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

**3. Configure environment variables**

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
```

If `DATABASE_URL` is not set, the system defaults to a local SQLite database.

**4. Start the application**

```bash
# Start the web UI
streamlit run src/ui/app.py

# In a separate terminal, start the background scraper
python -m src.scrapers.daemon
```

Open [http://localhost:8501](http://localhost:8501) and create an account.

---

## Configuration

All configuration is via environment variables (set in `.env` or injected at runtime):

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `gemini` | LLM backend: `gemini` or `openai` |
| `GEMINI_API_KEY` | — | Google Gemini API key (required if provider=gemini) |
| `DATABASE_URL` | `sqlite+aiosqlite:///titanswarm.db` | Database connection string |
| `SCRAPER_ROLES` | `Software Engineer Intern` | Target job titles (pipe-separated) |
| `SCRAPER_LOCATIONS` | `Vancouver, BC` | Target locations (pipe-separated) |
| `SCRAPER_INTERVAL_HOURS` | `12` | Hours between background scrape cycles |
| `SCRAPER_RESULTS_WANTED` | `25` | Jobs fetched per role/location per sweep |
| `SESSION_SECRET` | *(random per-process)* | HMAC secret for signing session cookies |

---

## Running Tests

```bash
pytest --tb=short -q
```

Tests use in-memory SQLite and mocked external APIs — no network calls, no API keys required.

---

## Project Structure

```
src/
  core/
    ai.py               # RAG tailor engine, hallucination guard, model cascade
    ledger.py            # Personal ledger manager + FAISS index
    models.py            # Pydantic domain models (Job, TailoredApplication, etc.)
    pdf_generator.py     # Jinja2 + Playwright PDF renderer
    repository.py        # JobRepository abstract base class
    matching.py          # Hybrid semantic + keyword match scoring
    github_enricher.py   # GitHub REST API repo/README fetcher
    website_enricher.py  # Portfolio website scraper + Gemini extractor
    env_writer.py        # Safe .env key upsert utility
    scraper.py           # Base scraper abstraction
    templates/
      resume.html        # ATS-optimized resume HTML template
  infrastructure/
    postgres_repo.py     # SQLAlchemy async repository (SQLite + PostgreSQL)
    browser.py           # Singleton Playwright browser pool
  scrapers/
    daemon.py            # Multi-tenant sourcing daemon process
    worker.py            # SourcingEngine (JobSpy wrapper + title filter)
  ui/
    app.py               # Streamlit Dispatch Terminal
    mock_repo.py         # In-memory repository for testing
data/
  ledger.md              # Personal knowledge base (resume + GitHub projects)
tests/                   # Full test suite (pytest-asyncio)
```

---

## Deployment

TitanSwarm ships with Docker Compose for one-command deployment.

### Deploy with Docker

```bash
# 1. Configure environment on the server
scp .env root@your-server-ip:/root/TitanSwarm/.env

# 2. Build and start
docker compose up -d --build
```

This starts two services:

| Service | Description |
|---------|-------------|
| `titanswarm_ui` | Streamlit UI on port 8501 |
| `titanswarm_daemon` | Background job scraper |

Data is persisted via Docker volumes: `titanswarm_db`, `titanswarm_data`, `titanswarm_output`.

### HTTPS (Nginx + Let's Encrypt)

```nginx
server {
    listen 80;
    server_name smartresume.dev www.smartresume.dev;
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

```bash
sudo certbot --nginx -d smartresume.dev -d www.smartresume.dev
```

### Continuous Deployment

Every push to `master` triggers automated deployment via [GitHub Actions](.github/workflows/deploy.yml). Tests run first via the [CI workflow](.github/workflows/ci.yml) — all tests must pass before deploy.

**Setup:**
1. Generate a deploy SSH key: `ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""`
2. Add the public key to the server: `ssh-copy-id -i ~/.ssh/deploy_key.pub root@your-server-ip`
3. Set GitHub repository secrets:
   - `DROPLET_SSH_KEY` — private key content
   - `DROPLET_HOST` — server IP address

---

## Key Design Decisions

**No auto-submission.** The system never submits to external job portals. This avoids bot-detection flags and keeps the user in control.

**Strict RAG, zero hallucination.** The LLM prompt is constructed exclusively from FAISS-retrieved chunks of your personal ledger. The model is explicitly instructed to refuse to invent any fact not present in context. Temperature is set to 0.2 for deterministic output.

**Repository pattern.** All persistence goes through the `JobRepository` ABC. No component imports a database driver directly — storage is fully swappable between SQLite and PostgreSQL without touching business logic.

**Model cascade.** If the primary Gemini model returns 503, the system automatically falls through a cascade of fallback models to ensure availability.

---

## Contributing

1. Fork the repo and create a feature branch
2. Ensure all tests pass: `pytest --tb=short -q`
3. Follow existing patterns (async-first, Pydantic contracts, repository pattern)
4. Submit a pull request to `master`

---

## License

MIT


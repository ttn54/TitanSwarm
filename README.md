# TitanSwarm

**Live:** [https://smartresume.dev](https://smartresume.dev)

An autonomous, agentic job application co-pilot. TitanSwarm automates the discovery, analysis, and tailoring of job applications — delivering a ready-to-submit package to the user while deliberately keeping a human in the loop for the final submission step.

---

## Overview

TitanSwarm operates as a background pipeline with a human-review terminal. The system handles job scraping, resume tailoring via a Retrieval-Augmented Generation (RAG) engine, ATS-optimized PDF generation, and application tracking — all without auto-submitting to external portals.

**Core guarantee:** The LLM is strictly sandboxed to verified facts in the user's personal ledger. It cannot invent experience, credentials, or skills that are not present in the source data.

---

## Architecture

The system is composed of four integrated layers:

**1. Sourcing Daemon** (`src/scrapers/`)  
Background worker that scrapes LinkedIn and Indeed for target roles using JobSpy. Runs on a configurable interval and stores discovered jobs to the database via the `JobRepository` interface.

**2. RAG Tailor Engine** (`src/core/`)  
Ingests the user's base resume and GitHub profile into a local FAISS vector index. When a new job is discovered, the engine retrieves the most relevant facts from the ledger and uses a Gemini LLM (`temperature=0.0`) to synthesize tailored resume bullets, a cover letter summary, and Q&A responses. No hallucination is possible because the prompt is explicitly bounded to the retrieved context.

**3. PDF Generator** (`src/core/pdf_generator.py`)  
Renders the tailored application into an ATS-readable PDF using a Jinja2 HTML template and Playwright (Chromium). Output is text-selectable — not an image — to pass ATS keyword scanning.

**4. Dispatch Terminal** (`src/ui/app.py`)  
A Streamlit web UI with three views:
- **Job Feed** — browse newly discovered roles with match scores
- **My Applications** — Kanban board tracking each job through its lifecycle (`DISCOVERED → PENDING_REVIEW → SUBMITTED → INTERVIEW`)
- **Preferences** — configure target roles, locations, scraper schedule, base resume upload, and GitHub enrichment

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| UI | Streamlit 1.55 |
| Job Scraping | python-jobspy (LinkedIn, Indeed) |
| Database | SQLite (dev) / PostgreSQL 15+ (prod) via SQLAlchemy 2.0 async |
| Vector Store | FAISS (CPU, local — no API calls during synthesis) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| LLM | Gemini 2.5 Flash Lite (primary) with model-cascade fallback |
| PDF Rendering | Jinja2 + Playwright (Chromium) |
| Data Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio |

---

## Prerequisites

- Python 3.12
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/))
- Chromium (installed via Playwright)

---

## Setup

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

Copy the example and fill in your API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/titanswarm
```

If `DATABASE_URL` is not set, the system defaults to a local SQLite database (`titanswarm.db`).

---

## Running the Application

**Start the Dispatch Terminal (UI):**

```bash
streamlit run src/ui/app.py
```

Open [http://localhost:8501](http://localhost:8501).

**Start the Sourcing Daemon (background scraper):**

```bash
python -m src.scrapers.daemon
```

The daemon reads its configuration from environment variables or from the values saved via the Preferences page in the UI.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///titanswarm.db` | Database connection string |
| `SCRAPER_INTERVAL_HOURS` | `12` | Hours between scrape cycles |
| `SCRAPER_RESULTS_WANTED` | `25` | Jobs fetched per role per location per sweep |
| `SCRAPER_ROLES` | _(set in UI)_ | Target job titles, pipe-separated |
| `SCRAPER_LOCATIONS` | _(set in UI)_ | Target locations, pipe-separated |

---

## Running Tests

```bash
pytest --tb=short -q
```

All 104 tests must pass before any merge.

---

## Project Structure

```
src/
  core/
    ai.py              # RAG tailor engine and hallucination guard
    ledger.py          # Personal ledger manager + FAISS index
    models.py          # Pydantic domain models (Job, JobStatus, TailoredApplication)
    pdf_generator.py   # Jinja2 + Playwright PDF renderer
    repository.py      # JobRepository abstract base class
    env_writer.py      # Safe .env key upsert writer
  infrastructure/
    titanstore.py      # SQLAlchemy async repository implementation
  scrapers/
    daemon.py          # Sourcing daemon process
    worker.py          # SourcingEngine (JobSpy wrapper)
  ui/
    app.py             # Streamlit Dispatch Terminal
data/
  ledger.md            # Personal knowledge base (resume + GitHub projects)
docs/
  plans/               # Architecture and design documents
tests/                 # Full test suite (pytest-asyncio)
```

---

## Key Design Decisions

**No auto-submission.** The system never submits to external job portals on behalf of the user. This avoids bot-detection flags and maintains the user's control over every application sent.

**Strict RAG, zero hallucination.** The LLM prompt is constructed exclusively from chunks retrieved from `data/ledger.md`. The prompt explicitly instructs the model to refuse to invent any fact not present in the retrieved context.

**Repository pattern.** No component imports a database driver directly. All persistence goes through the `JobRepository` ABC (`src/core/repository.py`), making the storage layer fully swappable between SQLite and PostgreSQL without touching business logic.

---

## Deployment

TitanSwarm ships with a Docker Compose setup for one-command production deployment.

**Live instance:** [https://smartresume.dev](https://smartresume.dev)

### Deploy with Docker

**1. Copy and configure your environment file on the server:**

```bash
scp .env root@your-server-ip:/root/TitanSwarm/.env
```

**2. Build and start both containers:**

```bash
docker compose up -d --build
```

This starts two services:
| Service | Description |
|---|---|
| `titanswarm_ui` | Streamlit UI on port 8501 |
| `titanswarm_daemon` | Background job scraper |

Data is persisted across restarts via three Docker volumes: `titanswarm_db`, `titanswarm_data`, `titanswarm_output`.

### Securing with HTTPS (Nginx + Let's Encrypt)
To prevent modern browsers from blocking the native PDF auto-download mechanism (the "Keep or Discard" warning), the app must be served over HTTPS.

1. **Point your domain** (e.g. `smartresume.dev`) to your server IP.
2. **Install Nginx & Certbot**: `sudo apt install nginx certbot python3-certbot-nginx`
3. **Configure Nginx** to act as a reverse proxy for Streamlit's WebSocket connection:
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
4. **Issue SSL Certificate**: `sudo certbot --nginx -d smartresume.dev -d www.smartresume.dev`

### Continuous Deployment (GitHub Actions)

Every push to the `master` branch automatically deploys to the DigitalOcean Droplet via the workflow at [.github/workflows/deploy.yml](.github/workflows/deploy.yml).

To set this up on your own server:
1. Generate a passphrase-free SSH key: `ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""`
2. Copy the public key to your server: `ssh-copy-id -i ~/.ssh/deploy_key.pub root@your-server-ip`
3. Add the private key content as a GitHub repository secret named `DROPLET_SSH_KEY`
4. Update the `host` field in `deploy.yml` to your server IP

---

## License

MIT

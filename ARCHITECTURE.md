TITANSWARM: Master Architecture & Design Document
1. Executive Vision
TitanSwarm is an enterprise-grade, autonomous Application Co-Pilot designed to scale to 100+ concurrent users. It acts as a digital talent agency that automates the discovery, analysis, and tailoring of job applications for Fall 2026 Software Engineering Co-ops.

To bypass Applicant Tracking System (ATS) bot-detection and recruiter stigma, TitanSwarm operates under a "Human-in-the-Loop" (Co-Pilot) model. The system handles 99% of the computational heavy lifting (scraping, RAG-based resume tailoring, and Q&A generation), while packaging the final deliverables into a Dispatch Terminal for the user to execute the final manual submission.

2. Core Constraints & Engineering Principles
No Hallucinations: The RAG (Retrieval-Augmented Generation) engine is strictly sandboxed. It is forbidden from inventing experience. It may only synthesize bullet points using the user's verified Immutable Facts Ledger (e.g., Computing Science coursework, 3.74 GPA, custom Raft databases, SFU Course Tracker).

Decoupled State Management: The system must implement the Repository Pattern for all database interactions. The Python business logic must never hardcode database drivers. This ensures the current custom backend (TitanStore) can be swapped out for PostgreSQL in exactly one hour when scaling beyond the initial user base.

Production-Grade: Code must include extensive logging, exponential backoff for web scrapers, and strict type-hinting (Python pydantic models).

3. Technology Stack
Worker / Logic Layer: Python 3.11+

Scraping Engine: Playwright (Headless browser for complex DOMs) or BeautifulSoup (for static boards).

AI / RAG Engine: LangChain or LlamaIndex + OpenAI API (GPT-4o-mini) / Anthropic API (Claude 3.5).

Vector Store (Local): FAISS or ChromaDB.

Central Memory Bank (Database): TitanStore (Custom Go-based distributed Raft database communicating via raw TCP sockets on port 6001).

4. System Architecture & Data Flow
Phase 1: The Sourcing Engine (Scrapers)
Background Python daemon processes (Workers) continuously monitor designated target URLs (e.g., LinkedIn, Greenhouse, Workday boards).

Worker identifies a "Fall 2026 Software Engineering" position.

Worker extracts the raw text: Company, Role, Job Description (JD), Required Skills, and Custom Portal Questions.

Worker passes a hashed ID of the job to the Memory Bank interface. If the database returns EXISTS, the worker drops the job. If NEW, it proceeds.

Phase 2: The Memory Bank (Repository Interface)
The system utilizes a strict interface (DatabaseRepository) to interact with the storage layer.

Current Implementation (TitanStoreRepository): Opens a TCP socket to localhost:6001. Sends commands formatted as: SET job:<hash> <json_payload>.

State Machine: Every job transitions through strict states: DISCOVERED -> PROCESSING -> PENDING_REVIEW -> SUBMITTED -> REJECTED/INTERVIEW.

Phase 3: The RAG Tailor & Ingestion Engine
* **Context Ingestion:** The system includes an `/ingest` directory. The user drops their standard `base_resume.pdf` and a list of GitHub URLs into this folder. A Python ingestion script parses the PDF, scrapes the GitHub READMEs, chunks the text, and loads it into the local Vector Store (FAISS/ChromaDB).
* **Resume Synthesis:** When tailoring a resume, the LLM queries the Vector Store to retrieve the user's authentic facts. It scientifically rewrites the base resume bullets to match the target ATS keywords without hallucinating fake experience.
* **Q&A Generation:** The LLM generates 150-word responses to custom portal questions using the user's ingested project history.

Phase 4: The Streamlit Control Center (Web UI)
Instead of a raw terminal, the human-in-the-loop interacts with a lightweight Web UI built using `Streamlit`.
* **Dashboard:** Displays metrics (Jobs Scraped, Jobs Pending Review, Jobs Applied).
* **Review Queue:** A clean UI table showing jobs in the `PENDING_REVIEW` state.
* **Action Panel:** Clicking a job opens a split-screen view. The left side shows the required Q&A answers and the target URL. The right side contains a one-click download button for the newly generated, tailored `.pdf` resume.
* **State Update:** A button to manually mark the job as `SUBMITTED`, which updates the TitanStore database over TCP.

5. The Repository Pattern (Crucial AI Instruction)
Claude: When writing the database connection layer, you MUST create an abstract base class JobRepository. Define methods like save_job(), get_job(), and update_status(). Then, create a TitanStoreClient(JobRepository) that implements these using raw TCP sockets over raft/tcp.go. Do not tightly couple the web scraper directly to the TCP socket.

6. Two-Month Development Roadmap (8-Week Sprints)
Week 1: The Vault & The Interface. Define the Job Pydantic models. Build the JobRepository interface. Write the TCP client to successfully read/write JSON payloads to the running Go TitanStore cluster.

Week 2: Sourcing Engine (Scraping). Build the Playwright workers. Target 2-3 specific job boards. Implement the deduplication check against the repository.

Week 3: The Immutable Ledger. Construct the user's base context file (The SFU academic history, projects, tech stack). Setup the local FAISS/ChromaDB vector store to ingest this ledger.

Week 4: The ATS RAG Pipeline. Integrate the LLM. Write the strict system prompts that force the AI to tailor the resume and answer portal questions without hallucinating.

Week 5: PDF Generation. Write the Python module that takes the LLM JSON output and compiles it into a cleanly formatted, ATS-readable PDF using ReportLab or WeasyPrint.

Week 6: The Streamlit Web UI.** Build the interactive web dashboard using `streamlit`. Connect the UI buttons directly to the `JobRepository` interface to fetch `PENDING_REVIEW` jobs from the TitanStore database and display the tailored PDFs and Q&A text.

Week 7: Concurrency & Scaling. Spin up multiple asynchronous Playwright workers. Ensure the TitanStore TCP connection pool can handle concurrent lock-free writes.

Week 8: Hardening & Deployment. Implement logging, error recovery, and test the 1-hour swap to PostgreSQL locally using the Repository interface to prove the architecture scales to 100 users.

7. Developer Context for AI Assistant
The Lead Developer's name is Zen.

Treat Zen as an elite Systems Engineer capable of handling complex distributed architectures. Do not over-explain basic Python syntax; focus on architecture, concurrency, and clean enterprise patterns.

The system is being built to secure a Fall 2026 SWE Co-op. Ensure the generated application logic strictly targets Fall recruitment timelines and requirements.
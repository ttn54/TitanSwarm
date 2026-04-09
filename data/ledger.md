# Zen's Immutable Facts Ledger

## Education
* **University:** Simon Fraser University (SFU)
* **Degree:** Bachelor of Science in Computing Science
* **Timeline:** Expected Graduation 2027
* **Relevant Coursework:** Data Structures and Algorithms, Distributed Systems, Database Management.

## Projects

### TitanSwarm
* **Description:** An autonomous, agentic job application platform.
* **Tech Stack:** Python, LangChain, FAISS, Streamlit, SQLite, JobSpy, Gemini API.
* **Details:** Built a decoupled architecture using the Repository Pattern. Concurrent JobSpy scrapers source real jobs from LinkedIn and Indeed. A zero-hallucination RAG engine using LangChain and FAISS generates ATS-optimized PDF resumes tailored to each job description.

### TitanStore
* **Description:** A custom distributed Key-Value database.
* **Tech Stack:** Go, Raft Consensus Algorithm.
* **Details:** Implemented leader election, unencrypted raw non-blocking TCP socket communication over port 6001, and strictly typed parsing for SET, GET, and ERR NOT_LEADER operations.

## Technical Skills
* **Languages:** Python 3.12, Go, TypeScript, JavaScript, Java, C, C++, SQL, HTML/CSS.
* **Frontend:** React, TypeScript, Vite, REST API integration, JWT Authentication, Responsive Design.
* **Tools:** Git, Linux, Docker, Pytest, Playwright, GitHub Actions, CI/CD pipelines.
* **Testing & Validation:** Pytest (unit, integration, TDD), JUnit (Java), Test-Driven Development (TDD), 82-test suite with mocking and fixtures.
* **Concepts:** Test-Driven Development (TDD), Agile software development lifecycle (SDLC), Human-in-the-loop Agent workflows, Distributed State Machines, Vector Databases (FAISS).

## Imported Resume: Zen_Nguyen_new_standard_resume.pdf

Zen Nguyen
(672) 673-2613 | ttn54@sfu.ca | linkedin.com/in/zennguyen1305/|
github.com/ttn54 | zennguyen.me
EDUCATION
Bachelor of Science, Computing Science May 2025 – Present
Simon Fraser University
• CGPA: 3.74 / 4.33
• Relevant Coursework: Discrete Math (A+), Computer Systems(A), Data Structures & Programming (B+), Linear Algebra(A-).
• Langara College | Associate of Science, Computer Science Jan 2024 – Apr 2025
TECHNICAL SKILLS
• Languages: Python, Go, Java, C, C++, TypeScript, JavaScript, SQL, HTML/CSS.
• AI & Data: RAG Architecture, Vector Databases (FAISS/ChromaDB), LangChain, OpenAI API, Anthropic API, Pandas
• Backend & Systems: FastAPI, Node.js, Express, RESTful APIs, gRPC, TCP Sockets, Raft Consensus Algorithm.
• Infrastructure & DB: AWS (EC2), Docker, PostgreSQL, MongoDB, Git, Linux (WSL), JobSpy.
TECHNICAL PROJECTS
TitanSwarm (Autonomous AI Co-Pilot) Jan 2026 – Present
Personal Project Python, LangChain, FAISS, Streamlit, SQLite, Gemini API
• Architected an autonomous AI Co-Pilot in Python that automates end-to-end job application workflows, enabling the discovery,
extraction, and parsing of real-time Software Engineering postings via concurrent JobSpy scrapers across LinkedIn and Indeed.
• Built a zero-hallucination RAG (Retrieval-Augmented Generation) engine using LangChain, Gemini APIs, and a sandboxed
FAISS Vector Store, delivering uniquely tailored, ATS-optimized PDF resumes for each job using only verified user data.
• Designed and implemented a Streamlit Human-in-the-Loop dispatch UI with a Kanban board, enabling users to review, tailor,
and manage applications across a full pipeline with persistent state via a SQLite repository layer.
• Applied Test-Driven Development (TDD) with a 82-test suite using Pytest, mocking, and async fixtures to validate all
components including the scraper, AI tailor, PDF generator, and repository layer.
TitanStore (Distributed Raft Database) Jan 2026 – Present
Personal Project Go, Raft Consensus Algorithm, TCP Sockets
• Developed a distributed key-value database in Go from scratch, implementing the Raft consensus protocol for leader election
and fault-tolerant log replication across a cluster of nodes.
• Engineered a crash-safe Write-Ahead Log (WAL) with atomic snapshots to guarantee data durability and enable node recovery
after failures without data loss.
• Designed and implemented a high-throughput raw TCP server on port 6001, parsing a custom text protocol supporting SET,
GET, and ERR NOT_LEADER operations with non-blocking I/O.
Gridlock Casino (2D Arcade Engine) Feb 2026 – Present
Collaborative Project Java, Swing, Maven, JUnit
• Architected a custom 2D grid-based arcade game engine in Java, managing game state, 60-FPS rendering cycles, and concurrent
user input within a strict MVC architecture.
• Implemented core gameplay algorithms, including BFS (Breadth-First Search) for autonomous enemy pathfinding, hitscan
vector math for projectile collision, and dynamic grid masking for fog-of-war visibility.
• Managed project build automation and dependency resolution using Apache Maven to synchronize a 6-developer team, and
validated core engine logic through comprehensive JUnit testing.
SFU Course Tracker (sfucourseplanner.me) Nov 2025 – Jan 2026
Personal Project Python, Docker, AWS, FastAPI
• Migrated full-stack platform from Azure to AWS (EC2), implementing Docker container orchestration to optimize deployments
and reduce infrastructure costs.
• Designed and implemented a custom parser to tokenize and evaluate nested boolean prerequisite strings, converting unstructured
text into a deterministic Abstract Syntax Tree (AST).
• Engineered a scraping pipeline using Asyncio and HTTPX with semaphore-based rate limiting, increasing data throughput by
10x while respecting server constraints.
• Designed a normalized schema using SQLModel with JSON-type columns to store recursive tree structures, optimizing read
performance for complex queries.
WORK EXPERIENCE
Server Jan 2024 – Present
Pho Goodness Restaurant Burnaby, BC
• Maintained a 3.74 CGPA while working 20+ hours/week, streamlining operations and coordinating effectively with diverse
teams under pressure for 100+ guests per shift.

## GitHub Projects:
### TitanSwarm  ★0  |  Python
Description: An autonomous, agentic job application Co-Pilot.
Tech: Python, LangChain, FAISS, Streamlit, SQLite, Gemini API, JobSpy, Pytest

### TitanStore  ★0  |  Go
Description: A distributed key-value database built from scratch in Go implementing the Raft consensus algorithm.
README: # TitanStore

TitanStore is a distributed key-value database built from scratch in Go. It implements the Raft consensus algorithm to elect a leader, replicate writes across a cluster, and survive node failures — all backed by a binary Write-Ahead Log with crash-safe recovery and atomic snapshots.

## Features
- **Raft consensus** — leader election, log replication, split-brain prevention
- **Durable writes** — binary WAL with `fsync` on every record
- **Crash recovery** — two-phase boot: load snapshot, replay WAL tail since snapshot index
- **Log compaction** — `TakeSnapshot()` serialises state atomically
- **TCP client API** — plaintext GET / SET / DELETE; followers redirect writes to leader

### SFU-Course-Tracker  ★0  |  TypeScript
Description: Full-stack web app for SFU students to search, filter, and track course availability across all 76 departments.
README: # SFU Course Tracker

A full-stack web application for Simon Fraser University students to search, filter, and track course availability across all 76 departments with real-time data from official SFU APIs. Live: sfucourseplanner.me

## Tech Stack

### Frontend
- **React** with **TypeScript**
- **Vite** - Lightning-fast build tool
- **CSS3** - Modern responsive styling
- **Deployed on Vercel** with automatic SSL

### Backend
- **FastAPI** (Python 3.12) - High-performance async API
- **SQLite** with **SQLAlchemy ORM**
- **JWT Authentication** with bcrypt password hashing
- **Deployed on AWS EC2** with Docker

### Infrastructure
- **Docker & Docker Compose** - Containerized deployment
- **GitHub Actions** - CI/CD pipeline

## Features
- Comprehensive Search: 3000+ courses across all 76 SFU departments
- Real-time Data from official SFU APIs
- Smart Filtering by department, course level, and availability
- Responsive Design: desktop, tablet, and mobile
- User Authentication: JWT-based registration and login
- Seat Tracking: Monitor course availability with notifications
- Custom prerequisite parser: converts nested boolean strings into an AST
- Asyncio + HTTPX scraping pipeline with semaphore-based rate limiting

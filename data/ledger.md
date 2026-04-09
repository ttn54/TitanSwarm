# Zen's Immutable Facts Ledger

## Education
* **University:** Simon Fraser University (SFU)
* **Degree:** Bachelor of Science in Computing Science
* **Timeline:** Expected Graduation 2027
* **Relevant Coursework:** Data Structures and Algorithms, Distributed Systems, Database Management.

## Projects

### TitanSwarm
* **Description:** An autonomous, agentic job application platform.
* **Tech Stack:** Python, Go, Playwright, FAISS, Streamlit, Raw TCP Sockets, Raft Consensus.
* **Details:** Built a decoupled architecture using the Repository Pattern. Decoupled the scraping workers from the custom Go-based distributed database (TitanStore).

### TitanStore
* **Description:** A custom distributed Key-Value database.
* **Tech Stack:** Go, Raft Consensus Algorithm.
* **Details:** Implemented leader election, unencrypted raw non-blocking TCP socket communication over port 6001, and strictly typed parsing for SET, GET, and ERR NOT_LEADER operations.

## Technical Skills
* **Languages:** Python 3.12, Go, SQL.
* **Tools:** Git, Linux, Docker, Pytest, Playwright.
* **Concepts:** Test-Driven Development (TDD), Human-in-the-loop Agent workflows, Distributed State Machines, Vector Databases (FAISS).

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
TitanSwarm (Autonomous AI Co-Pilot) & TitanStore (Raft Database) Jan 2026 – Present
Personal Project Python, Go, LangChain, FAISS
• Architected an autonomous AI Co-Pilot in Python that automates end-to-end job application workflows, enabling the discovery,
extraction, and parsing of thousands of Software Engineering postings with advanced anti-bot evasion via concurrent JobSpy
scrapers.
• Built a zero-hallucination RAG (Retrieval-Augmented Generation) engine using LangChain, OpenAI APIs, and a sandboxed
FAISS Vector Store, delivering uniquely tailored, ATS-optimized PDF resumes for each job by leveraging only verified user
data.
• Developed TitanStore, a distributed memory bank in Go, implementing the Raft consensus protocol and a custom Write-Ahead
Log (WAL) to guarantee application state durability and fault tolerance across network failures.
• Designed and implemented a high-throughput TCP client API, enabling the Python AI workers to perform concurrent, real-time
status updates (e.g., Pending, Submitted) to the Go database cluster, supporting seamless scaling to 100+ users.
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
### n54  ★0  |  Unknown  |  config, github-config
Config files for my GitHub profile.
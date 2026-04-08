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

## Imported Resume: Zen Nguyen resume.pdf

Zen Nguyen
(672) 673-2613 | ttn54@sfu.ca | linkedin.com/in/zennguyen1305/|
github.com/ttn54 | zennguyen.me
EDUCATION
Bachelor of Science, Computing Science May 2025 – Present
Simon Fraser University
• CGPA: 3.74 / 4.33
• Relevant Coursework: Discrete Math (A+), Computer Systems(A), Data Structures & Programming (B+), Linear Algebra(A-).
Associate of Science, Computer Science Jan 2024 – Apr 2025
Langara College
• Completed foundational coursework in Computer Science and Calculus with distinction before transferring to SFU with advanced
standing.
TECHNICAL SKILLS
• Languages: Go (Golang), Python, C#, Java, JavaScript/TypeScript, SQL (PostgreSQL).
• Backend & Systems: FastAPI, SQLModel (ORM), Asyncio, RESTful APIs, gRPC/Protobuf, TCP, Authentication
(JWT/OAuth).
• Cloud & DevOps: AWS (EC2), Docker, GitHub Actions (CI/CD), Git, Linux (WSL)
• Frontend: React, Tailwind CSS, Zustand.
TECHNICAL PROJECTS
TitanStore Jan 2026 – Present
Personal Project Go , SQL, Docker
• Architected a highly available, distributed key-value database in Go, implementing the Raft consensus algorithm from scratch
to handle leader election and log replication.
• Engineered a custom binary Write-Ahead Log (WAL) with strict fsync durability and atomic snapshots (os.Rename), ensuring
zero data loss during simulated cluster failures and network partitions.
• Managed complex concurrency using Goroutines, channels, and sync.RWMutex, verifying absolute thread safety across 17
integration tests via go test -race.
• Developed a custom gRPC/Protobuf inter-node communication layer and a plaintext TCP client API with automatic leader
redirection.
SFU Course Tracker (sfucourseplanner.me) Nov 2025 – Jan 2025
Personal Project Python, AWS, Distributed Systems
• Originally architected the platform on Microsoft Azure before migrating to AWS (EC2) to implement custom container
orchestration with Docker and reduce infrastructure costs.
• Designed and implemented a custom parser to tokenize and evaluate nested boolean prerequisite strings, converting unstructured
text into a deterministic Abstract Syntax Tree (AST).
• Engineered a scraping pipeline using Asyncio and HTTPX with semaphore-based rate limiting, increasing data throughput by
10x while respecting server constraints.
• Designed a normalized schema using SQLModel with JSON-type columns to store recursive tree structures, optimizing read
performance for complex queries.
Chain Reaction Game (GDCxCSSS Game Jam) (meryxmas.itch.io/gamejam-game) Jun 2025
Collaborative Project C#, Unity ,Git
• Collaborated in a team of 4 under a strict 10-hour deadline to conceptualize and prototype a physics-based puzzle game.
• Implemented core mechanics including raycasting for lasers and area-of-effect explosions using vector mathematics, ensuring
responsive player feedback.
WORK EXPERIENCE
Server Jan 2024 – Present
Pho Goodness Restaurant Burnaby, BC
• Successfully maintained a 3.74 GPA while working 20+ hours/week. This demonstrates the work ethic required for high-
performance engineering environments.
• Streamlined operations for 100+ guests/shift by coordinating effectively with diverse teams under pressure.
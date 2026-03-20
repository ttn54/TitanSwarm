import json
import asyncio
from src.core.vault import Vault
from src.core.ledger import Ledger
from src.core.tailor import DocumentTailor

import os

async def generate_real_resume():
    # Load the real scraped data
    with open('example/real_scraped_data.json', 'r') as f:
        jobs = json.load(f)

    # Find the job with "Vancouver" or "Remote" or an internship
    target_job = None
    for j in jobs:
        # Check title and location
        title_lower = j.get('title', '').lower()
        location_lower = j.get('location', '').lower()
        if 'intern' in title_lower or 'coop' in title_lower or 'vancouver' in location_lower:
            target_job = j
            break
            
    # Fallback to the first job if none found
    if not target_job and jobs:
        target_job = jobs[0]
        
    print(f"🎯 Selected Target Real Job: {target_job['title']}")
    print(f"📍 Location: {target_job['location']}")
    print(f"🔗 URL: {target_job['url']}")
    
    # Init system
    vault = Vault(storage_dir="example/vault_data")
    ledger = Ledger(pdf_output_dir="example/out")
    tailor = DocumentTailor(vault)
    
    # Re-use our mock document from Phase 5 demo
    user_doc = """
    Name: Alex Chen
    Email: alex.chen@university.edu
    Phone: (555) 123-4567

    Education:
    - B.S. Computer Science, University of Technology, 2021-2025

    Skills:
    - Python, Go, C++, JavaScript, SQL
    - React, FastAPI, Docker, Kubernetes, AWS
    - Distributed Systems, Vector Databases, Playwright

    Experience:
    - Software Engineering Intern at DataCorp (Summer 2023)
      - Built a highly concurrent web crawler in Go processing 1M+ URLs/day.
      - Reduced database query latency by 40% using Redis caching.
    - Full Stack Intern at WebSolutions (Fall 2022)
      - Developed user facing React components serving 50k DAU.
      - Migrated legacy REST APIs to GraphQL using Node.js.

    Projects:
    - AutoRAG Pipeline: Built a document ingestion system using LangChain, FAISS, and OpenAI.
    - Raft KV Store: Implemented a distributed key-value store in Go based on the Raft consensus protocol.
    """
    vault.ingest_text("user_resume.txt", user_doc)
    
    # Execute AI Tailoring using the real job description
    print("\n🧠 Generating Tailored ATS Content via OpenAI RAG...")
    jd = target_job.get("job_description", "")
    
    summary = await tailor.generate_summary(jd)
    skills = await tailor.extract_matching_skills(jd)
    exp = await tailor.rewrite_experience(jd)
    
    record = {
        "name": "Alex Chen",
        "email": "alex.chen@university.edu",
        "linkedin": "linkedin.com/in/alexchen",
        "github": "github.com/alexc",
        "job_title": target_job['title'],
        "company": "Twitch (or related company)",
        "summary": summary,
        "skills": skills,
        "experience": exp,
        "education": [
            {
                "degree": "B.S. Computer Science",
                "university": "University of Technology",
                "dates": "2021-2025"
            }
        ]
    }
    
    pdf_path = await ledger.generate_pdf(record, "resume.html")
    print(f"\n🎉 WIN! Generated live tailored PDF -> {pdf_path}")
    
if __name__ == "__main__":
    asyncio.run(generate_real_resume())


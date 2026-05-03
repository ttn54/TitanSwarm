#!/usr/bin/env python3
"""
Quick test: verify jobs are discoverable for a specific user
Run with: python test_user_jobs.py test124
"""
import asyncio
import sys
from src.infrastructure.postgres_repo import PostgresRepository
from src.core.models import JobStatus

async def main(username: str):
    repo = PostgresRepository("sqlite+aiosqlite:///titanswarm.db")
    await repo.init_db()
    
    # Get user
    uid = await repo.verify_user(username, "password123")
    if not uid:
        print(f"❌ User '{username}' not found or wrong password")
        await repo.close()
        return
    
    print(f"✓ User {username} found (uid={uid})\n")
    
    # Check existing jobs
    discovered = await repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=uid)
    pending = await repo.get_jobs_by_status(JobStatus.PENDING_REVIEW, user_id=uid)
    submitted = await repo.get_jobs_by_status(JobStatus.SUBMITTED, user_id=uid)
    
    print(f"Jobs for {username}:")
    print(f"  DISCOVERED: {len(discovered)}")
    print(f"  PENDING_REVIEW: {len(pending)}")
    print(f"  SUBMITTED: {len(submitted)}")
    
    if discovered:
        print(f"\nSample discovered jobs:")
        for i, job in enumerate(discovered[:5], 1):
            print(f"  {i}. {job.role} @ {job.company}")
    else:
        print(f"\n⚠️  No DISCOVERED jobs found!")
        print("   Try running a search on the Job Feed page.")
    
    await repo.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_user_jobs.py <username>")
        print("Example: python test_user_jobs.py test124")
        sys.exit(1)
    
    asyncio.run(main(sys.argv[1]))

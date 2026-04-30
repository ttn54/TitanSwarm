#!/usr/bin/env python3
"""
Test the migration code locally to verify it works before applying to production.
Simulates the broken production state (single-column PK) and verifies the fix.
"""
import asyncio
import sqlite3
import tempfile
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.postgres_repo import PostgresRepository


async def test_migration():
    """Test the migration code against a broken SQLite database."""
    
    # Create a temporary broken database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        
        print("=" * 80)
        print("STEP 1: Creating broken schema (single-column PK on 'id' only)")
        print("=" * 80)
        
        # Create the broken schema (as it currently is in production)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create jobs table with BROKEN schema (id only as PK, no user_id in PK)
        cursor.execute("""
            CREATE TABLE jobs (
                id VARCHAR PRIMARY KEY,
                company VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                status VARCHAR(14) NOT NULL,
                job_description VARCHAR NOT NULL,
                url VARCHAR NOT NULL,
                required_skills VARCHAR NOT NULL,
                custom_questions VARCHAR NOT NULL,
                location VARCHAR NOT NULL,
                date_posted VARCHAR NOT NULL,
                user_id INTEGER DEFAULT 1,
                salary_min FLOAT,
                salary_max FLOAT,
                salary_currency VARCHAR NOT NULL,
                salary_interval VARCHAR NOT NULL
            )
        """)
        
        # Create tailored_results with BROKEN schema
        cursor.execute("""
            CREATE TABLE tailored_results (
                job_id VARCHAR PRIMARY KEY,
                resume_customized VARCHAR NOT NULL,
                cover_letter_customized VARCHAR NOT NULL,
                q_a_json VARCHAR NOT NULL,
                notes VARCHAR NOT NULL,
                user_id INTEGER DEFAULT 1
            )
        """)
        
        conn.commit()
        
        # Insert test data: job-1 for user 1
        cursor.execute("""
            INSERT INTO jobs (id, company, role, status, job_description, url, required_skills, custom_questions, location, date_posted, user_id, salary_currency, salary_interval)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("job-1", "CompanyA", "Engineer", "DISCOVERED", "Desc A", "http://a.com", "[]", "[]", "NYC", "2026-01-01", 1, "USD", "yearly"))
        conn.commit()
        
        # Try to insert same job ID for different user - this will FAIL with broken schema
        print("\nTrying to insert job-1 for user 2 (should fail with broken schema):")
        try:
            cursor.execute("""
                INSERT INTO jobs (id, company, role, status, job_description, url, required_skills, custom_questions, location, date_posted, user_id, salary_currency, salary_interval)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("job-1", "CompanyB", "Manager", "PENDING", "Desc B", "http://b.com", "[]", "[]", "SF", "2026-02-01", 2, "USD", "yearly"))
            conn.commit()
            print("  ✗ Unexpected success (bug not reproduced)")
        except sqlite3.IntegrityError as e:
            print(f"  ✓ Failed as expected: {e}")
            conn.rollback()
        
        # Check BEFORE migration
        print("\n--- BEFORE MIGRATION ---")
        print("\nPRAGMA table_info(jobs):")
        schema = cursor.execute("PRAGMA table_info(jobs)").fetchall()
        for row in schema:
            print(f"  {row}")
        
        current_pk = [row[1] for row in schema if row[5]]
        print(f"\nCurrent PK: {current_pk}")
        assert current_pk == ["id"], f"Expected ['id'] but got {current_pk}"
        
        print("\nJobs in database (BEFORE):")
        jobs = cursor.execute("SELECT id, company, role, user_id FROM jobs ORDER BY id").fetchall()
        for job in jobs:
            print(f"  {job}")
        assert len(jobs) == 1, f"Expected 1 row, got {len(jobs)}"
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("STEP 2: Running migration")
        print("=" * 80)
        
        # Create repo pointing to the broken database
        dsn = f"sqlite+aiosqlite:///{db_path}"
        repo = PostgresRepository(dsn)
        
        # Run the migration
        print("\nCalling _ensure_multi_tenant_keys()...")
        await repo._ensure_multi_tenant_keys()
        print("Migration completed!")
        
        await repo.close()
        
        print("\n" + "=" * 80)
        print("STEP 3: Verifying fixed schema")
        print("=" * 80)
        
        # Check AFTER migration
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\n--- AFTER MIGRATION ---")
        print("\nPRAGMA table_info(jobs):")
        schema = cursor.execute("PRAGMA table_info(jobs)").fetchall()
        for row in schema:
            print(f"  {row}")
        
        current_pk = [row[1] for row in schema if row[5]]
        print(f"\nCurrent PK: {current_pk}")
        assert current_pk == ["id", "user_id"], f"Expected ['id', 'user_id'] but got {current_pk}"
        print("✓ Composite PK verified!")
        
        # Verify old data is still there
        print("\nVerifying old data preserved:")
        jobs = cursor.execute("SELECT id, company, role, user_id FROM jobs ORDER BY id, user_id").fetchall()
        for job in jobs:
            print(f"  {job}")
        assert len(jobs) == 1, f"Expected 1 row after migration, got {len(jobs)}"
        
        # Now insert same job ID for a DIFFERENT user - should succeed!
        print("\nInserting job-1 for user 2 (should succeed with composite PK):")
        cursor.execute("""
            INSERT INTO jobs (id, company, role, status, job_description, url, required_skills, custom_questions, location, date_posted, user_id, salary_currency, salary_interval)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("job-1", "CompanyB", "Manager", "PENDING", "Desc B", "http://b.com", "[]", "[]", "SF", "2026-02-01", 2, "USD", "yearly"))
        conn.commit()
        print("  ✓ Insert succeeded!")
        
        print("\nJobs in database (AFTER):")
        jobs = cursor.execute("SELECT id, company, role, user_id FROM jobs ORDER BY id, user_id").fetchall()
        for job in jobs:
            print(f"  {job}")
        assert len(jobs) == 2, f"Expected 2 rows, but got {len(jobs)}"
        print("✓ Both rows inserted successfully (multi-tenant isolation working!)")
        
        # Verify tailored_results was also migrated
        print("\nPRAGMA table_info(tailored_results):")
        schema = cursor.execute("PRAGMA table_info(tailored_results)").fetchall()
        for row in schema:
            print(f"  {row}")
        
        current_pk = [row[1] for row in schema if row[5]]
        print(f"\nCurrent PK: {current_pk}")
        assert current_pk == ["job_id", "user_id"], f"Expected ['job_id', 'user_id'] but got {current_pk}"
        print("✓ tailored_results composite PK verified!")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("✓ ALL TESTS PASSED - Migration code is working correctly!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_migration())

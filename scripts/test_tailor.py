"""
End-to-end test: run tailor_application for user_id=3, Frontend JD.
Checks annotation injection and final project ranking.
"""
import asyncio
import sys
import os
import re

sys.path.insert(0, "/app")

from src.infrastructure.postgres_repo import PostgresRepository
from src.core.ai import (
    AITailor,
    _enrich_resume_with_github_tech,
    _extract_github_tech_map,
)
from src.core.ledger import LedgerManager


FRONTEND_JOB_ID = "in-7d00f66f5b51fded"  # Best Buy Intermediate Frontend Developer
USER_ID = 3


async def main():
    dsn = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///titanswarm.db")
    repo = PostgresRepository(dsn)
    await repo.init_db()

    # 1. Load the ledger content
    content = await repo.get_ledger(USER_ID)
    if not content:
        print("ERROR: No ledger found for user_id=3")
        return
    print(f"[OK] Ledger loaded, length={len(content)}")

    # 2. Check tech_map
    tech_map = _extract_github_tech_map(content)
    print(f"\n[TECH MAP] {len(tech_map)} repos:")
    for k, v in tech_map.items():
        print(f"  {k!r}: {v}")

    # 3. Simulate EXACTLY what tailor_application does:
    #    _parse_ledger_as_resume(ledger_path) → _enrich_resume_with_github_tech(parsed)
    import tempfile, os as _os
    from src.core.ai import _parse_ledger_as_resume
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp_path = f.name
    try:
        parsed = _parse_ledger_as_resume(tmp_path)
        print(f"\n[PARSED resume] length={len(parsed)}")
        print(f"  Starts with: {parsed[:80]!r}")

        # Check tech_map from parsed
        tech_map_parsed = _extract_github_tech_map(parsed)
        print(f"\n[TECH MAP from parsed] {len(tech_map_parsed)} repos:")
        for k, v in tech_map_parsed.items():
            print(f"  {k!r}: {v[:60]}")

        enriched_parsed = _enrich_resume_with_github_tech(parsed)
        print(f"\n[ENRICHED parsed] length={len(enriched_parsed)} (delta={len(enriched_parsed)-len(parsed)})")

        # Find SFU in the enriched parsed text (TECHNICAL PROJECTS section)
        sfu_idx = enriched_parsed.lower().find("sfu course tracker")
        if sfu_idx >= 0:
            print("\n[SFU SECTION in AI's actual input]:")
            print(repr(enriched_parsed[max(0,sfu_idx-20):sfu_idx+300]))
        else:
            print("WARNING: SFU not found in parsed+enriched text!")
    finally:
        _os.unlink(tmp_path)

    # 4. Quick check
    if "TypeScript" in enriched_parsed or "React" in enriched_parsed:
        print("\n[OK] TypeScript/React found in enriched_parsed (tailor's actual input)")
    else:
        print("\nWARNING: TypeScript/React NOT in enriched_parsed!")

    # 5. Load the job
    job = await repo.get_job(FRONTEND_JOB_ID, user_id=USER_ID)
    if not job:
        print(f"\nERROR: Job {FRONTEND_JOB_ID} not found")
        return
    print(f"\n[JOB] {job.role} @ {job.company}")
    print(f"  JD (first 150): {job.job_description[:150]!r}")

    # 6. Run tailor_application
    print("\n[TAILOR] Running tailor_application (calls Gemini)...")
    ledger_mgr = LedgerManager.from_content(content, db_path=":memory:")
    tailor = AITailor(ledger_manager=ledger_mgr)
    result = await tailor.tailor_application(job)

    print("\n[RESULT] TailoredProjects:")
    for i, proj in enumerate(result.tailored_projects, 1):
        print(f"  #{i}: {proj.title}")
        print(f"       tech={proj.tech}")
        print(f"       keyword_overlap={proj.keyword_overlap_count}")
        print(f"       bullets[0]: {proj.bullets[0] if proj.bullets else '—'}")

    print("\n[RESULT] Skills:")
    for cat, items in result.skills_to_highlight.items():
        print(f"  {cat}: {', '.join(items[:5])}")

    print("\nDONE.")


asyncio.run(main())

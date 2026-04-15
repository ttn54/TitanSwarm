import os
import asyncio
import logging
from src.scrapers.worker import SourcingEngine
from src.infrastructure.postgres_repo import PostgresRepository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SourcingDaemon")


def _parse_targets(roles_str: str, locs_str: str) -> list[tuple[str, str]]:
    """
    Parse pipe-separated role and location strings into a cartesian product
    of (role, location) pairs.  Pipe is used (not comma) because location
    strings like "Vancouver, BC" legitimately contain commas.

    Example:
        roles_str  = "SWE Intern|Frontend Intern"
        locs_str   = "Vancouver, BC|Remote Canada"
        → [("SWE Intern", "Vancouver, BC"), ("SWE Intern", "Remote Canada"),
           ("Frontend Intern", "Vancouver, BC"), ("Frontend Intern", "Remote Canada")]

    Single values (no pipe) work unchanged:
        roles_str  = "Software Engineer Intern"
        locs_str   = "Vancouver, BC"
        → [("Software Engineer Intern", "Vancouver, BC")]
    """
    roles = [r.strip() for r in roles_str.split("|") if r.strip()]
    locations = [loc.strip() for loc in locs_str.split("|") if loc.strip()]
    return [(role, loc) for role in roles for loc in locations]


async def _run_concurrent_sweep(
    engine: SourcingEngine,
    targets: list[tuple[int, str, str]],
    results_wanted: int,
) -> int:
    """
    Run all (user_id, role, location) triples concurrently via asyncio.gather.
    Individual sweep failures are caught and logged — they do not cancel
    other sweeps. Returns the total number of new jobs saved across all sweeps.
    """
    if not targets:
        return 0

    async def _safe_sweep(user_id: int, role: str, location: str) -> int:
        try:
            saved, _ = await engine.run_sweep(
                role=role, location=location, results_wanted=results_wanted,
                user_id=user_id,
            )
            logger.info(f"Sweep done: '{role}' in '{location}' (user {user_id}) → {saved} new jobs")
            return saved
        except Exception as exc:
            logger.error(f"Sweep failed for '{role}' in '{location}' (user {user_id}): {exc}")
            return 0

    counts = await asyncio.gather(*[_safe_sweep(uid, role, loc) for uid, role, loc in targets])
    return sum(counts)


async def main():
    dsn = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///titanswarm.db")
    interval_hours = int(os.getenv("SCRAPER_INTERVAL_HOURS", "12"))
    results_wanted = int(os.getenv("SCRAPER_RESULTS_WANTED", "50"))

    repo = PostgresRepository(dsn)
    await repo.init_db()
    engine = SourcingEngine(repository=repo, interval_hours=interval_hours)

    # Env-var fallback targets (used when no users have saved preferences yet)
    roles_str = os.getenv("SCRAPER_ROLES", os.getenv("SCRAPER_ROLE", "Software Engineer Intern"))
    locs_str  = os.getenv("SCRAPER_LOCATIONS", os.getenv("SCRAPER_LOCATION", "Vancouver, BC"))
    _fallback_targets = _parse_targets(roles_str, locs_str)
    # Convert legacy (role, loc) pairs to (user_id=1, role, loc) triples
    _fallback_triples: list[tuple[int, str, str]] = [(1, r, l) for r, l in _fallback_targets]

    logger.info("Initializing multi-tenant Sourcing Daemon")

    try:
        while True:
            # ── Pull live targets from DB ──────────────────────────────────
            db_targets: list[tuple[int, str, str]] = await repo.get_all_user_targets()
            if db_targets:
                targets = db_targets
                logger.info(f"Using {len(targets)} DB user target(s)")
            else:
                targets = _fallback_triples
                logger.info(f"No user profiles found — using {len(targets)} env-var fallback target(s)")

            if not targets:
                logger.warning("No targets configured. Sleeping until next interval.")
            else:
                logger.info(f"Starting concurrent sweep across {len(targets)} target(s)…")
                total_saved = await _run_concurrent_sweep(engine, targets, results_wanted)
                logger.info(f"All sweeps complete. {total_saved} new jobs saved. Sleeping {interval_hours}h…")

            await asyncio.sleep(interval_hours * 3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Daemon received shutdown signal. Exiting.")
    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(main())

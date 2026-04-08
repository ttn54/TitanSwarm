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

async def main():
    dsn = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/titanswarm")
    target_role = os.getenv("SCRAPER_ROLE", "Software Engineer")
    target_location = os.getenv("SCRAPER_LOCATION", "Vancouver, BC")
    interval_hours = int(os.getenv("SCRAPER_INTERVAL_HOURS", "12"))
    results_wanted = int(os.getenv("SCRAPER_RESULTS_WANTED", "10"))

    logger.info("Initializing Sourcing Engine Daemon...")

    repo = PostgresRepository(dsn)
    await repo.init_db()

    engine = SourcingEngine(repository=repo, interval_hours=interval_hours)

    try:
        while True:
            logger.info(f"Waking up for scraping sweep. Target: '{target_role}' in '{target_location}'")
            try:
                saved = await engine.run_sweep(
                    role=target_role,
                    location=target_location,
                    results_wanted=results_wanted
                )
                logger.info(f"Scraping sweep completed. {saved} new jobs persisted.")
            except Exception as e:
                logger.error(f"Scraping sweep failed: {e}")

            sleep_seconds = interval_hours * 3600
            logger.info(f"Sweep finished. Sleeping for {interval_hours} hours...")
            await asyncio.sleep(sleep_seconds)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Daemon received shutdown signal. Exiting.")
    finally:
        await repo.close()

if __name__ == "__main__":
    asyncio.run(main())

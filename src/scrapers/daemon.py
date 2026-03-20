import os
import time
import logging
from src.scrapers.worker import SourcingEngine
from src.core.models import Job

# For now, if we don't have a real repo, we'll try to load the mock one, 
# or raise if not provided properly. (Since phase 2 is the db, we will inject a dummy for now 
# just to show it runs standalone)
# Wait, let's create a minimal logger and the loop.

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SourcingDaemon")

def main():
    target_role = os.getenv("SCRAPER_ROLE", "Software Engineer")
    target_location = os.getenv("SCRAPER_LOCATION", "Vancouver, BC")
    interval_hours = int(os.getenv("SCRAPER_INTERVAL_HOURS", "12"))
    results_wanted = int(os.getenv("SCRAPER_RESULTS_WANTED", "10"))
    
    logger.info("Initializing Sourcing Engine Daemon...")
    
    # We will need the repository here. For now we can use MockUIRepository 
    # until Phase 2 (TitanStore) is built.
    try:
        from src.ui.mock_repo import MockUIRepository
        repo = MockUIRepository()
    except ImportError:
        logger.warning("MockUIRepository not found. Using a bare mock.")
        class DummyRepo:
            def job_exists(self, _id): return False
            def save_job(self, job): logger.info(f"Saved: {job.title} at {job.company}")
        repo = DummyRepo()
        
    engine = SourcingEngine(repository=repo, interval_hours=interval_hours)

    while True:
        logger.info(f"Waking up for scraping sweep. Target: '{target_role}' in '{target_location}'")
        try:
            engine.run_sweep(role=target_role, location=target_location, results_wanted=results_wanted)
            logger.info("Scraping sweep completed successfully.")
        except Exception as e:
            logger.error(f"Scraping sweep failed: {e}")
        
        sleep_seconds = interval_hours * 3600
        logger.info(f"Sweep finished. Going to sleep for {interval_hours} hours...")
        
        try:
            time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            logger.info("Daemon received shutdown signal. Exiting.")
            break

if __name__ == "__main__":
    main()

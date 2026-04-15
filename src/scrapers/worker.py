from typing import Any
import asyncio
import logging
import re
import pandas as pd
from jobspy import scrape_jobs
from src.core.models import Job, JobStatus

# ── Salary description fallback ───────────────────────────────────────────────
# LinkedIn hides structured salary data from scrapers.  This regex scans the
# raw job description text for embedded salary ranges like:
#   "89,700.00 - 149,800.00 CAD annually"
#   "$21 - $25 an hour"
#   "$80,000 - $120,000 per year"
_SALARY_RANGE_RE = re.compile(
    r'(CA\$|C\$|\$)?\s*([\d,]+(?:\.\d+)?)\s*[-–]\s*(CA\$|C\$|\$)?\s*([\d,]+(?:\.\d+)?)'
    r'([^\n]{0,80})',   # rest of the line — scanned for currency + interval
    re.IGNORECASE,
)


def _extract_salary_from_description(
    description: str,
) -> tuple[float | None, float | None, str, str]:
    """
    Scan *description* for an embedded salary range.
    Returns (salary_min, salary_max, currency, interval).
    Returns (None, None, "", "") when no recognisable pattern is found.
    """
    if not description:
        return None, None, "", ""

    # LinkedIn descriptions are stored with markdown escapes (e.g. \\- and \\.)
    # Unescape them so the regex can match plain numbers and hyphens.
    desc = re.sub(r'\\(.)', r'\1', description)

    m = _SALARY_RANGE_RE.search(desc)
    if not m:
        return None, None, "", ""

    prefix1, num1, prefix2, num2, rest = m.groups()

    try:
        sal_min = float(num1.replace(",", ""))
        sal_max = float(num2.replace(",", ""))
    except (ValueError, AttributeError):
        return None, None, "", ""

    # Guard: ignore small numbers that are not salaries (e.g. "3-5 years")
    if sal_min < 10 or sal_max < 10:
        return None, None, "", ""

    # Currency: check prefixes first, then rest of line
    currency_ctx = (prefix1 or "") + (prefix2 or "") + (rest or "")
    if re.search(r'CAD|CA\$|C\$', currency_ctx, re.IGNORECASE):
        currency = "CAD"
    elif re.search(r'\$|USD', currency_ctx, re.IGNORECASE):
        currency = "USD"
    else:
        currency = ""

    # Interval: scan rest of line
    rest_l = (rest or "").lower()
    if re.search(r'annual|per\s+year|a\s+year|/yr\b|/year\b', rest_l):
        interval = "yearly"
    elif re.search(r'hour|/hr\b|/hour\b|an\s+hour', rest_l):
        interval = "hourly"
    elif re.search(r'month|/mo\b|/month\b', rest_l):
        interval = "monthly"
    else:
        interval = ""

    return sal_min, sal_max, currency, interval

logger = logging.getLogger(__name__)

# Canadian province/territory markers used to auto-select country_indeed
_CA_MARKERS = {", bc", ", on", ", ab", ", qc", ", mb", ", sk", ", ns", ", nb",
               ", nl", ", pe", ", nt", ", yt", ", nu", "canada"}


def _detect_country_indeed(location: str) -> str:
    """Return 'canada' if the location string looks Canadian, else 'usa'."""
    loc = location.lower()
    if any(m in loc for m in _CA_MARKERS):
        return "canada"
    return "usa"


class SourcingEngine:
    def __init__(self, repository: Any, interval_hours: int = 12):
        self.repository = repository
        self.interval_hours = interval_hours

    async def _scrape_df(self, role: str, location: str, results_wanted: int) -> pd.DataFrame:
        """Run the blocking JobSpy scrape in a thread pool and return the raw DataFrame."""
        loop = asyncio.get_event_loop()
        country = _detect_country_indeed(location)

        def _scrape() -> pd.DataFrame:
            return scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=role,
                location=location,
                results_wanted=results_wanted,
                linkedin_fetch_description=True,
                country_indeed=country,
            )

        return await loop.run_in_executor(None, _scrape)

    async def run_sweep(self, role: str, location: str, results_wanted: int = 25, user_id: int = 1) -> tuple[int, list[str]]:
        """
        Executes a scraping sweep utilizing jobspy, converts the raw DataFrame
        to Pydantic Job models, deduplicates against the repository, and persists
        new jobs.
        Returns (new_saved_count, all_found_job_ids) so the UI can display
        all results for this sweep regardless of their current status.
        """
        jobs_df = await self._scrape_df(role, location, results_wanted)

        if jobs_df is None or jobs_df.empty:
            logger.info("Scraping sweep returned no results.")
            return 0, []

        # Post-filter: prevent LinkedIn from injecting irrelevant jobs.
        #
        # Rules (applied in order):
        #   1. Intern-type guard: if user searched "intern/internship/co-op",
        #      title MUST contain an intern-type word. Blocks "Senior SWE" results.
        #   2. Seniority guard: if user searched a seniority word (senior/lead/…),
        #      title MUST contain THAT seniority word.
        #   3. Role-word guard: at least ONE non-qualifier role word (≥4 chars)
        #      must appear in the title. Blocks "Research Intern - AI" for "SWE Intern".
        _INTERN_QUALS = {"intern", "internship", "co-op", "coop"}
        _SENIORITY_QUALS = {"junior", "senior", "lead", "staff", "principal"}

        _search_words = [w.lower() for w in role.split() if w]
        _has_intern = any(w in _INTERN_QUALS for w in _search_words)
        _search_seniority = [w for w in _search_words if w in _SENIORITY_QUALS]
        _role_words = [w for w in _search_words
                       if w not in _INTERN_QUALS and w not in _SENIORITY_QUALS and len(w) >= 4]

        def _title_matches(title_val) -> bool:
            if not title_val or (isinstance(title_val, float) and pd.isna(title_val)):
                return False
            t = str(title_val).lower()
            # Rule 1: intern-type guard
            if _has_intern and not any(q in t for q in _INTERN_QUALS):
                return False
            # Rule 2: seniority guard
            if _search_seniority and not any(s in t for s in _search_seniority):
                return False
            # Rule 3: at least one core role word must appear
            if _role_words and not any(w in t for w in _role_words):
                return False
            return True

        jobs_df = jobs_df[jobs_df["title"].apply(_title_matches)]
        if jobs_df.empty:
            logger.info("No jobs matched title filter after scraping.")
            return 0, []

        saved_count = 0
        all_found_ids: list[str] = []
        for _, row in jobs_df.iterrows():
            job_id = str(row.get("id"))
            if job_id == "None":
                logger.warning("Skipping job with null ID from scraper.")
                continue

            all_found_ids.append(job_id)

            # ── No-description filter ─────────────────────────────────────
            # Jobs without a real description cannot be tailored — skip them.
            _BAD_DESC = {"", "Description not provided.", "None", "nan"}
            description = row.get("description")
            _desc_str = "" if (not description or (isinstance(description, float) and pd.isna(description))) else str(description).strip()
            if _desc_str in _BAD_DESC:
                logger.debug(f"Skipping job {job_id}: no description")
                continue

            # Deduplication: track whether this is a new record so we can
            # increment saved_count correctly.  We always call save_job so the
            # UPSERT can refresh enrichment fields (salary, description, etc.)
            # for jobs that were scraped before those columns existed.
            # We only consider a job "new" if it wasn't already in the DB with
            # a real description.
            existing = await self.repository.get_job(job_id, user_id=user_id)
            is_new = existing is None or existing.job_description.strip() in _BAD_DESC

            # Extract skills list from JobSpy 'skills' column (may be None or a list)
            raw_skills = row.get("skills")
            if raw_skills and not (isinstance(raw_skills, float) and pd.isna(raw_skills)):
                if isinstance(raw_skills, list):
                    required_skills = [str(s) for s in raw_skills if s]
                else:
                    required_skills = [s.strip() for s in str(raw_skills).split(",") if s.strip()]
            else:
                required_skills = []

            company_raw = row.get("company")
            company = str(company_raw) if company_raw and not (isinstance(company_raw, float) and pd.isna(company_raw)) else "Unknown Company"

            location_raw = row.get("location")
            job_location = str(location_raw) if location_raw and not (isinstance(location_raw, float) and pd.isna(location_raw)) else ""

            date_raw = row.get("date_posted")
            if date_raw and not (isinstance(date_raw, float) and pd.isna(date_raw)):
                job_date = str(date_raw)
            else:
                job_date = ""

            def _safe_float(val) -> float | None:
                try:
                    f = float(val)
                    return None if pd.isna(f) else f
                except (TypeError, ValueError):
                    return None

            salary_min      = _safe_float(row.get("min_amount"))
            salary_max      = _safe_float(row.get("max_amount"))
            salary_currency = str(row.get("currency") or "").strip()
            salary_interval = str(row.get("interval") or "").strip()

            # Fallback: LinkedIn embeds salary in the description body but does
            # not expose it as structured data.  Parse it out when JobSpy gives
            # us nothing.
            if salary_min is None and salary_max is None:
                salary_min, salary_max, salary_currency, salary_interval = (
                    _extract_salary_from_description(_desc_str)
                )

            job = Job(
                id=job_id,
                company=company,
                role=str(row.get("title")),
                status=JobStatus.DISCOVERED,
                job_description=_desc_str,
                required_skills=required_skills,
                url=str(row.get("job_url")),
                location=job_location,
                date_posted=job_date,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                salary_interval=salary_interval,
            )

            await self.repository.save_job(job, user_id=user_id)
            if is_new:
                saved_count += 1
                logger.info(f"Saved new job: {job.role} at {job.company}")
            else:
                logger.debug(f"Refreshed enrichment for existing job: {job_id}")

        return saved_count, all_found_ids

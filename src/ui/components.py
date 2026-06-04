"""
Shared UI components and pure helper functions.

Extracted from the monolith app.py so that page modules can import them
without circular dependencies.  All functions here are pure (no Streamlit
state mutations) and unit-testable.
"""
from __future__ import annotations

import asyncio
import re
import os
from datetime import date as _date, timedelta
from typing import List, Optional

from src.core.models import Job, JobStatus, UserProfile


# ─────────────────────────────────────────────────────────────────────────────
# PURE HELPER FUNCTIONS (importable for testing)
# ─────────────────────────────────────────────────────────────────────────────

def run_async(coro):
    """Run an async coroutine synchronously (Streamlit bridge)."""
    return asyncio.run(coro)


def filter_jobs(jobs: List[Job], chip: Optional[str]) -> List[Job]:
    """Filter a list of jobs based on the selected filter chip.

    Uses word-boundary matching to avoid false positives:
      - 'intern' matches 'Software Engineer Intern' but NOT 'international'
      - 'remote' matches 'Remote' but NOT 'remote-first' as a substring artefact
    """
    if not chip or chip == "All":
        return jobs
    result = []
    for job in jobs:
        text = (job.role + " " + job.job_description).lower()
        if chip == "Remote":
            if re.search(r'\bremote\b', text):
                result.append(job)
        elif chip == "Internship":
            if re.search(r'\bintern(?:ship)?\b', text):
                result.append(job)
        elif chip == "Full-time":
            if re.search(r'\bfull[-\s]?time\b', text):
                result.append(job)
        elif chip == "Co-op":
            if re.search(r'\bco[-\s]?op\b', text):
                result.append(job)
    return result


def profile_completion(pf: UserProfile) -> float:
    """Return 0.0–1.0 profile completion ratio across all meaningfully filled fields."""
    filled = sum([
        bool(pf.name),
        bool(pf.email),
        bool(pf.phone),
        bool(pf.github),
        bool(pf.linkedin),
        bool(pf.website),
        bool(pf.skills),
        bool(pf.base_summary),
        bool(pf.education),
        bool(pf.experience),
    ])
    return filled / 10


def search_jobs(jobs: List[Job], query: Optional[str]) -> List[Job]:
    """Filter jobs by substring match on company or role."""
    if not query:
        return jobs
    q = query.lower()
    return [j for j in jobs if q in j.company.lower() or q in j.role.lower()]


_DATE_WINDOWS = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30}


def filter_by_date(jobs: List[Job], window: Optional[str]) -> List[Job]:
    """Filter jobs by date_posted window.

    Jobs with an empty/unknown date_posted are ALWAYS included (Option A).
    'Any' or None returns all jobs unfiltered.
    """
    if not window or window == "Any":
        return jobs
    days = _DATE_WINDOWS.get(window)
    if days is None:
        return jobs
    cutoff = _date.today() - timedelta(days=days)
    result = []
    for job in jobs:
        if not job.date_posted:
            result.append(job)  # unknown date → include
            continue
        try:
            posted = _date.fromisoformat(job.date_posted[:10])
            if posted >= cutoff:
                result.append(job)
        except ValueError:
            result.append(job)  # unparseable → include
    return result


# Pre-compiled regex constants — defined once at module load
_SECTION_RE = re.compile(
    r'^(EDUCATION|TECHNICAL PROJECTS?|TECHNICAL SKILLS?|WORK EXPERIENCE|EXPERIENCE|PROJECTS?)$',
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}'
    r'|\b\d{4}\b'
    r'|\u2013\s*Present'
)
_FNAME_SANITIZE_RE = re.compile(r'[^\w\s-]')

# Module-level lookup tables — avoid rebuilding on every function call
STATUS_BADGE_MAP = {
    JobStatus.PENDING_REVIEW: ("pending",   "Pending Review"),
    JobStatus.SUBMITTED:      ("submitted", "Applied"),
    JobStatus.DISCOVERED:     ("new",       "New"),
    JobStatus.REJECTED:       ("rejected",  "Rejected"),
    JobStatus.PROCESSING:     ("pending",   "Processing"),
    JobStatus.INTERVIEW:      ("interview", "Interview"),
}
AVATAR_COLORS = (
    "linear-gradient(135deg,#6366f1,#8b5cf6)",
    "linear-gradient(135deg,#0ea5e9,#6366f1)",
    "linear-gradient(135deg,#f59e0b,#ef4444)",
    "linear-gradient(135deg,#10b981,#0ea5e9)",
    "linear-gradient(135deg,#8b5cf6,#ec4899)",
)


def badge(status: JobStatus) -> str:
    """Return an HTML badge span for the given job status."""
    cls, label = STATUS_BADGE_MAP.get(status, ("new", status.value))
    return f'<span class="badge badge-{cls}">{label}</span>'


def avatar_html(company: str, size: int = 44, radius: int = 12) -> str:
    """Return an HTML div with company initials as an avatar."""
    initials = "".join(w[0] for w in company.split()[:2]).upper()
    bg = AVATAR_COLORS[sum(ord(c) for c in company) % len(AVATAR_COLORS)]
    return (f'<div style="width:{size}px;height:{size}px;border-radius:{radius}px;'
            f'background:{bg};color:#fff;font-size:{size//2.5:.0f}px;font-weight:800;'
            f'display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
            f'{initials}</div>')


def build_manual_ledger_section(education: list[dict], experience: list[dict]) -> str:
    """
    Converts profile education + experience dicts into the EDUCATION /
    WORK EXPERIENCE text format that _parse_ledger_for_pdf already understands.
    Returns "" if both lists are empty.
    """
    lines: list[str] = []

    if education:
        lines.append("EDUCATION")
        for e in education:
            degree = e.get("degree", "").strip()
            inst   = e.get("institution", "").strip()
            start  = e.get("start_date", "").strip()
            end    = e.get("end_date", "").strip()
            if not degree and not inst:
                continue
            date_str = f"  {start} – {end}" if (start or end) else ""
            lines.append(f"{degree}{date_str}")
            if inst:
                lines.append(inst)
            for b in e.get("bullets", []):
                if b.strip():
                    lines.append(f"• {b.strip()}")
            lines.append("")

    if experience:
        lines.append("WORK EXPERIENCE")
        for ex in experience:
            title   = ex.get("title", "").strip()
            company = ex.get("company", "").strip()
            start   = ex.get("start_date", "").strip()
            end     = ex.get("end_date", "").strip()
            if not title and not company:
                continue
            date_str = f"  {start} – {end}" if (start or end) else ""
            lines.append(f"{title}{date_str}")
            if company:
                lines.append(company)
            for b in ex.get("bullets", []):
                if b.strip():
                    lines.append(f"• {b.strip()}")
            lines.append("")

    return "\n".join(lines).strip()


def merge_structured(profile_entries: list[dict], ledger_entries: list[dict]) -> list[dict]:
    """
    Merge profile (manually entered) and ledger-parsed (resume upload / website)
    entries without duplicates. Profile entries take priority and come first.
    Deduplication key: lowercase degree/title + institution/company.
    """
    seen: set[str] = set()
    result: list[dict] = []

    for e in profile_entries:
        key = (e.get("degree") or e.get("title") or "").lower() + "|" + \
              (e.get("institution") or e.get("company") or "").lower()
        if key not in seen:
            seen.add(key)
            result.append(e)

    for e in ledger_entries:
        key = (e.get("degree") or e.get("title") or "").lower() + "|" + \
              (e.get("institution") or e.get("company") or "").lower()
        if key and key not in seen:
            seen.add(key)
            result.append(e)

    return result


async def run_discovery(repo, role: str, location: str, count: int, user_id: int = 1) -> list[str]:
    """Clears previous DISCOVERED jobs, runs a real JobSpy sweep.
    Returns the list of ALL job IDs found by this sweep (new + already in DB)."""
    from src.scrapers.worker import SourcingEngine
    await repo.delete_jobs_by_status(JobStatus.DISCOVERED, user_id=user_id)
    engine = SourcingEngine(repository=repo)
    _saved, all_ids = await engine.run_sweep(role=role, location=location, results_wanted=count, user_id=user_id)
    return all_ids


def parse_ledger_for_pdf(ledger_path: str = "", content: str | None = None) -> dict:
    """
    Parses the imported resume section of ledger.md into structured
    education and experience lists for the PDF template.

    Returns a dict with keys: education, experience.
    Each education entry: {institution, degree, start_date, end_date, location, bullets}
    Each experience entry: {title, company, start_date, end_date, location, bullets}

    Pass ``content`` directly to skip the disk read when the caller already
    holds the ledger string (e.g. freshly fetched from the DB).
    """
    if content is None:
        if not ledger_path or not os.path.exists(ledger_path):
            return {"education": [], "experience": []}
        content = open(ledger_path, encoding="utf-8").read()
    marker = "## Imported Resume:"
    text = content.split(marker, 1)[1] if marker in content else content
    lines = [l.rstrip() for l in text.splitlines()]

    education = []
    experience = []
    current_section = None
    current_entry = None

    def flush(entry, section):
        if not entry:
            return
        if section in ("EDUCATION",):
            education.append(entry)
        elif section in ("WORK EXPERIENCE", "EXPERIENCE"):
            experience.append(entry)

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if _SECTION_RE.match(line):
            flush(current_entry, current_section)
            current_entry = None
            current_section = line.upper()
            i += 1
            continue

        if current_section == "EDUCATION":
            date_m = _DATE_RE.search(line)
            if not line.startswith("•") and date_m:
                flush(current_entry, current_section)
                date_str = line[date_m.start():].strip()
                title_part = line[:date_m.start()].strip()
                institution = ""
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and not lines[j].strip().startswith("•") and not _SECTION_RE.match(lines[j].strip()):
                    institution = lines[j].strip()
                    i = j
                parts = re.split(r'[–—-]', date_str)
                start_d = parts[0].strip() if parts else ""
                end_d   = parts[1].strip() if len(parts) > 1 else "Present"
                current_entry = {
                    "institution": institution,
                    "degree": title_part,
                    "start_date": start_d,
                    "end_date": end_d,
                    "location": "",
                    "bullets": [],
                }
            elif not line.startswith("•"):
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    next_line = lines[j].strip()
                    next_date_m = _DATE_RE.search(next_line)
                    if next_date_m and not next_line.startswith("•") and not _SECTION_RE.match(next_line):
                        flush(current_entry, current_section)
                        degree = line
                        institution = next_line[:next_date_m.start()].strip()
                        date_str = next_line[next_date_m.start():].strip()
                        parts = re.split(r'[–—-]', date_str)
                        start_d = parts[0].strip() if parts else ""
                        end_d   = parts[1].strip() if len(parts) > 1 else "Present"
                        current_entry = {
                            "institution": institution,
                            "degree": degree,
                            "start_date": start_d,
                            "end_date": end_d,
                            "location": "",
                            "bullets": [],
                        }
                        i = j
            elif line.startswith("•") and current_entry:
                current_entry["bullets"].append(line.lstrip("• ").strip())

        elif current_section in ("WORK EXPERIENCE", "EXPERIENCE"):
            date_m = _DATE_RE.search(line)
            if date_m and not line.startswith("•"):
                flush(current_entry, current_section)
                date_str   = line[date_m.start():].strip()
                title_part = line[:date_m.start()].strip()
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                company  = ""
                location = ""
                if j < len(lines) and not lines[j].strip().startswith("•"):
                    cline = lines[j].strip()
                    loc_m = re.search(r'\b([A-Z][a-z]+,\s*[A-Z]{2})\s*$', cline)
                    if loc_m:
                        location = loc_m.group(1)
                        company  = cline[:loc_m.start()].strip()
                    else:
                        company = cline
                    i = j
                parts  = re.split(r'[–—-]', date_str)
                start_d = parts[0].strip() if parts else ""
                end_d   = parts[1].strip() if len(parts) > 1 else "Present"
                current_entry = {
                    "title": title_part,
                    "company": company,
                    "start_date": start_d,
                    "end_date": end_d,
                    "location": location,
                    "bullets": [],
                }
            elif line.startswith("•") and current_entry:
                current_entry["bullets"].append(line.lstrip("• ").strip())

        i += 1

    flush(current_entry, current_section)
    return {"education": education, "experience": experience}

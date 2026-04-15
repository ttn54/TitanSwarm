import streamlit as st
import asyncio
import sys
import os
import time
import html as _html
from datetime import date as _date, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.models import Job, JobStatus, UserProfile, TailoredApplication
from src.core.matching import compute_match_score
from src.infrastructure.postgres_repo import PostgresRepository
from src.scrapers.worker import SourcingEngine
from src.core.ledger import LedgerManager
from src.core.ai import AITailor
from src.core.pdf_generator import PDFGenerator
from src.core.env_writer import upsert_env_vars, read_env_var
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# PURE HELPER FUNCTIONS (importable for testing)
# ─────────────────────────────────────────────────────────────────────────────

def filter_jobs(jobs: List[Job], chip: Optional[str]) -> List[Job]:
    """Filter a list of jobs based on the selected filter chip."""
    if not chip or chip == "All":
        return jobs
    result = []
    for job in jobs:
        text = (job.role + " " + job.job_description).lower()
        if chip == "Remote" and "remote" in text:
            result.append(job)
        elif chip == "Internship" and "intern" in text:
            result.append(job)
        elif chip == "Full-time" and ("full-time" in text or "full time" in text):
            result.append(job)
        elif chip == "Co-op" and ("co-op" in text or "coop" in text):
            result.append(job)
    return result


def profile_completion(pf: UserProfile) -> float:
    """Return 0.0–1.0 profile completion ratio (6 fields)."""
    filled = sum([
        bool(pf.name), bool(pf.email), bool(pf.github),
        bool(pf.skills), bool(pf.base_summary), bool(pf.website),
    ])
    return filled / 6


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


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TitanSwarm",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }
/* Make header transparent (hides Streamlit branding) but keep toggle button clickable */
header[data-testid="stHeader"] { background: transparent !important; }
header[data-testid="stHeader"] > * { visibility: hidden; }
header[data-testid="stHeader"] button { visibility: visible !important; }
.stApp { background: #f1f5f9; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] * { color: #94a3b8 !important; }
section[data-testid="stSidebar"] .stRadio label { font-size: 0.88rem !important; }

.nav-logo {
    font-size: 1.3rem; font-weight: 800; color: #fff !important;
    letter-spacing: -0.04em; padding: 0.5rem 0 1.5rem 0;
}
.nav-logo span { color: #818cf8 !important; }

.nav-divider { border: none; border-top: 1px solid #1e293b; margin: 0.75rem 0; }

.nav-section-label {
    font-size: 0.68rem !important; font-weight: 600 !important;
    text-transform: uppercase; letter-spacing: 0.08em;
    color: #475569 !important; padding: 0.4rem 0 0.2rem 0;
}

div[data-testid="stRadio"] label {
    display: flex !important; align-items: center !important;
    padding: 0.5rem 0.75rem !important; border-radius: 8px !important;
    font-weight: 500 !important; font-size: 0.875rem !important;
    color: #94a3b8 !important; cursor: pointer;
    transition: background 0.1s;
}
div[data-testid="stRadio"] label:hover { background: #1e293b !important; color: #e2e8f0 !important; }

/* Active nav item: Streamlit marks selected radio differently in DOM */
div[data-testid="stRadio"] label[data-checked="true"],
div[data-testid="stRadio"] div[aria-checked="true"] label {
    background: #1e293b !important; color: #ffffff !important;
}

/* ── Main area ── */
.main-header {
    font-size: 1.6rem; font-weight: 800; color: #0f172a;
    letter-spacing: -0.04em; line-height: 1.2;
}
.main-subheader { font-size: 0.88rem; color: #64748b; margin-top: 2px; }

/* ── KPI strip ── */
.kpi-card {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 1.1rem 1.4rem; box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.kpi-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.07em; color: #94a3b8; font-weight: 600; }
.kpi-value { font-size: 1.9rem; font-weight: 800; color: #0f172a; line-height: 1.1; margin-top: 2px; }
.kpi-sub   { font-size: 0.78rem; color: #10b981; font-weight: 500; margin-top: 2px; }

/* ── Search bar ── */
.search-wrap {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 1rem 1.25rem; margin-bottom: 1rem; box-shadow: 0 1px 4px rgba(0,0,0,.04);
}

/* ── Filter chips ── */
.chip-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 0.5rem 0 1rem 0; }
.chip {
    padding: 4px 14px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
    cursor: pointer; border: 1.5px solid #e2e8f0; background: #fff; color: #64748b;
    transition: all 0.12s;
}
.chip.active { background: #ede9fe; border-color: #818cf8; color: #4f46e5; }

/* ── Job card ── */
.jcard {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 1.1rem 1.3rem 1rem 1.3rem; margin-bottom: 0.65rem;
    transition: box-shadow 0.15s, border-color 0.15s;
}
.jcard:hover { box-shadow: 0 6px 24px rgba(0,0,0,.08); border-color: #c7d2fe; }
.jcard-top { display: flex; align-items: flex-start; gap: 0.85rem; }
.jcard-avatar {
    width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
    background: linear-gradient(135deg,#6366f1,#8b5cf6);
    color: #fff; font-size: 1.05rem; font-weight: 800;
    display: flex; align-items: center; justify-content: center;
}
.jcard-company { font-size: 1rem; font-weight: 700; color: #0f172a; }
.jcard-role    { font-size: 0.875rem; font-weight: 600; color: #6366f1; margin-top: 1px; }
.jcard-meta    { font-size: 0.76rem; color: #94a3b8; margin-top: 3px; }
.jcard-desc    { font-size: 0.82rem; color: #64748b; margin-top: 0.55rem; line-height: 1.55; }
.jcard-skills  { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 0.5rem; }
.skill-pill {
    background: #f1f5f9; color: #475569; font-size: 0.72rem; font-weight: 500;
    padding: 2px 9px; border-radius: 6px;
}

/* ── Status badges ── */
.badge { display:inline-flex; align-items:center; gap:4px; padding:3px 10px; border-radius:999px; font-size:0.72rem; font-weight:600; letter-spacing:0.03em; }
.badge::before { content:''; width:6px; height:6px; border-radius:50%; }
.badge-pending   { background:#fef3c7; color:#92400e; } .badge-pending::before   { background:#f59e0b; }
.badge-submitted { background:#d1fae5; color:#065f46; } .badge-submitted::before { background:#10b981; }
.badge-new       { background:#ede9fe; color:#4338ca; } .badge-new::before       { background:#818cf8; }
.badge-rejected  { background:#fee2e2; color:#991b1b; } .badge-rejected::before  { background:#f87171; }
.badge-interview { background:#dbeafe; color:#1d4ed8; } .badge-interview::before { background:#60a5fa; }

/* ── Primary / secondary buttons ── */
.stButton > button[kind="primary"] {
    background: #6366f1 !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: 0.855rem !important;
    padding: 0.45rem 1rem !important;
    transition: background 0.15s !important;
}
.stButton > button[kind="primary"]:hover { background: #4f46e5 !important; }
.stButton > button[kind="secondary"] {
    background: #fff !important; color: #374151 !important;
    border: 1.5px solid #e2e8f0 !important; border-radius: 8px !important;
    font-weight: 500 !important; font-size: 0.855rem !important;
}
.stButton > button[kind="secondary"]:hover { border-color: #818cf8 !important; color: #4f46e5 !important; }

/* ── Inputs ── */
input, textarea, .stSelectbox > div {
    border-radius: 8px !important; border: 1.5px solid #e2e8f0 !important;
    font-size: 0.875rem !important; color: #1e293b !important;
}
input:focus, textarea:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,.12) !important; outline: none !important; }
label { font-size: 0.8rem !important; font-weight: 600 !important; color: #374151 !important; }

/* ── Kanban columns ── */
.kanban-col {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 14px; padding: 0.85rem;
}
.kanban-col-header {
    font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #64748b; margin-bottom: 0.75rem;
    display: flex; align-items: center; justify-content: space-between;
}
.kanban-count {
    background: #e2e8f0; color: #64748b; border-radius: 999px;
    font-size: 0.72rem; font-weight: 700; padding: 1px 7px;
}
.kanban-card {
    background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 0.75rem 0.85rem; margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.kanban-card .kc-company { font-size: 0.82rem; font-weight: 700; color: #0f172a; }
.kanban-card .kc-role    { font-size: 0.78rem; color: #6366f1; font-weight: 500; margin-top:1px; }
.kanban-card .kc-url     { font-size: 0.72rem; color: #94a3b8; margin-top:3px; }

/* ── Profile page ── */
.profile-card {
    background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 1.4rem 1.6rem; margin-bottom: 1rem;
}
.profile-card-title { font-size: 0.875rem; font-weight: 700; color: #0f172a; margin-bottom: 0.85rem; }

/* ── Divider ── */
.divider { border: none; border-top: 1px solid #e2e8f0; margin: 1rem 0; }

/* ── Progress ── */
div[data-testid="stProgress"] > div { background: #ede9fe !important; border-radius: 999px !important; }
div[data-testid="stProgress"] > div > div { background: #6366f1 !important; border-radius: 999px !important; }

/* ── Expander ── */
details summary { font-size: 0.82rem !important; font-weight: 600 !important; color: #475569 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS / HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def run_async(coro):
    return asyncio.run(coro)

def badge(status: JobStatus) -> str:
    m = {
        JobStatus.PENDING_REVIEW: ("pending",   "Pending Review"),
        JobStatus.SUBMITTED:      ("submitted", "Applied"),
        JobStatus.DISCOVERED:     ("new",       "New"),
        JobStatus.REJECTED:       ("rejected",  "Rejected"),
        JobStatus.PROCESSING:     ("pending",   "Processing"),
        JobStatus.INTERVIEW:      ("interview", "Interview"),
    }
    cls, label = m.get(status, ("new", status.value))
    return f'<span class="badge badge-{cls}">{label}</span>'

def avatar_html(company: str, size: int = 44, radius: int = 12) -> str:
    initials = "".join(w[0] for w in company.split()[:2]).upper()
    colors = [
        "linear-gradient(135deg,#6366f1,#8b5cf6)",
        "linear-gradient(135deg,#0ea5e9,#6366f1)",
        "linear-gradient(135deg,#f59e0b,#ef4444)",
        "linear-gradient(135deg,#10b981,#0ea5e9)",
        "linear-gradient(135deg,#8b5cf6,#ec4899)",
    ]
    bg = colors[sum(ord(c) for c in company) % len(colors)]
    return (f'<div style="width:{size}px;height:{size}px;border-radius:{radius}px;'
            f'background:{bg};color:#fff;font-size:{size//2.5:.0f}px;font-weight:800;'
            f'display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
            f'{initials}</div>')

async def _run_discovery(repo, role: str, location: str, count: int) -> list[str]:
    """Clears previous DISCOVERED jobs, runs a real JobSpy sweep.
    Returns the list of ALL job IDs found by this sweep (new + already in DB)."""
    await repo.delete_jobs_by_status(JobStatus.DISCOVERED)
    engine = SourcingEngine(repository=repo)
    _saved, all_ids = await engine.run_sweep(role=role, location=location, results_wanted=count)
    return all_ids


def _parse_ledger_for_pdf(ledger_path: str) -> dict:
    """
    Parses the imported resume section of ledger.md into structured
    education and experience lists for the PDF template.

    Returns a dict with keys: education, experience.
    Each education entry: {institution, degree, start_date, end_date, location, bullets}
    Each experience entry: {title, company, start_date, end_date, location, bullets}
    """
    import re
    if not os.path.exists(ledger_path):
        return {"education": [], "experience": []}

    content = open(ledger_path, encoding="utf-8").read()
    marker = "## Imported Resume:"
    text = content.split(marker, 1)[1] if marker in content else content
    lines = [l.rstrip() for l in text.splitlines()]

    # Detect section headings (all-caps lines or lines like "EDUCATION", "TECHNICAL PROJECTS", etc.)
    SECTION_RE = re.compile(
        r'^(EDUCATION|TECHNICAL PROJECTS?|TECHNICAL SKILLS?|WORK EXPERIENCE|EXPERIENCE|PROJECTS?)$',
        re.IGNORECASE
    )
    # Date pattern: looks like "Jan 2026 – Present" or "May 2025 – Present"
    DATE_RE = re.compile(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}')

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
        # TECHNICAL PROJECTS → handled as tailored_projects by AI, not here

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if SECTION_RE.match(line):
            flush(current_entry, current_section)
            current_entry = None
            current_section = line.upper()
            i += 1
            continue

        if current_section == "EDUCATION":
            # Lines like: "Bachelor of Science, Computing Science May 2025 – Present"
            date_m = DATE_RE.search(line)
            if date_m and not line.startswith("•"):
                flush(current_entry, current_section)
                # Extract dates
                date_str = line[date_m.start():].strip()
                title_part = line[:date_m.start()].strip()
                # Next non-empty line is usually the institution name
                institution = ""
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and not lines[j].strip().startswith("•"):
                    institution = lines[j].strip()
                    i = j
                # Parse date range
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
            elif line.startswith("•") and current_entry:
                current_entry["bullets"].append(line.lstrip("• ").strip())

        elif current_section in ("WORK EXPERIENCE", "EXPERIENCE"):
            date_m = DATE_RE.search(line)
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
                    # "Pho Goodness Restaurant Burnaby, BC"
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


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
if "repo" not in st.session_state:
    dsn = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///titanswarm.db")
    _r = PostgresRepository(dsn)
    run_async(_r.init_db())
    st.session_state.repo = _r

# ─────────────────────────────────────────────────────────────────────────────
# AUTH GATE — must be satisfied before any other UI renders
# ─────────────────────────────────────────────────────────────────────────────
def _render_auth_page():
    """Renders the login / register page and halts app rendering until authenticated."""
    st.markdown("""
    <style>
    .auth-wrap { max-width: 420px; margin: 6rem auto 0 auto; }
    .auth-title { font-size: 2rem; font-weight: 800; color: #0f172a;
                  letter-spacing: -0.04em; text-align: center; margin-bottom: 0.25rem; }
    .auth-sub   { font-size: 0.9rem; color: #64748b; text-align: center; margin-bottom: 2rem; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="auth-title">⚡ TitanSwarm</div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-sub">Your autonomous job application Co-Pilot</div>', unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Log In", "Register"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")
        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                uid = run_async(st.session_state.repo.verify_user(username, password))
                if uid is None:
                    st.error("Invalid username or password.")
                else:
                    st.session_state["user_id"] = uid
                    st.session_state["username"] = username
                    st.rerun()

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_password = st.text_input("Choose a password", type="password")
            confirm_pw   = st.text_input("Confirm password", type="password")
            reg_submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")
        if reg_submitted:
            if not new_username or not new_password:
                st.error("Username and password are required.")
            elif new_password != confirm_pw:
                st.error("Passwords do not match.")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                try:
                    uid = run_async(st.session_state.repo.create_user(new_username, new_password))
                    # Seed ledger from data/ledger.md for first user only
                    _seed_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ledger.md")
                    if os.path.exists(_seed_path):
                        _seed_content = open(_seed_path, encoding="utf-8").read()
                        run_async(st.session_state.repo.save_ledger(uid, _seed_content))
                    st.session_state["user_id"] = uid
                    st.session_state["username"] = new_username
                    st.success(f"Account created! Welcome, {new_username}.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

if "user_id" not in st.session_state:
    _render_auth_page()
    st.stop()

# From here down, the user is authenticated. user_id is always available.
_USER_ID: int = st.session_state.get("user_id", 1)

if "profile" not in st.session_state:
    _db_profile = run_async(st.session_state.repo.get_profile(user_id=_USER_ID))
    st.session_state.profile = _db_profile if _db_profile else UserProfile()

# Seed form display keys from the saved profile.
# Re-seed whenever we navigate TO the Preferences page (widget keys may have
# been cleaned up or reset to defaults while the widgets were not rendered).
def _seed_profile_keys():
    """Populate _pf_* session-state keys from the saved profile + ledger fallback."""
    _pf0 = st.session_state.profile
    _ledger_name = ""
    _ledger_email = ""
    _ledger_phone = ""
    _ledger_linkedin = ""
    _ledger_github = ""
    _ledger_website = ""
    try:
        _lp = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ledger.md")
        if os.path.exists(_lp):
            _lc = open(_lp, encoding="utf-8").read()
            _marker = "## Imported Resume:"
            _body = _lc.split(_marker, 1)[1] if _marker in _lc else _lc
            _lines = [l.strip() for l in _body.splitlines() if l.strip()]
            if _lines and not _lines[0].endswith(".pdf"):
                _ledger_name = _lines[0]
            elif len(_lines) > 1:
                _ledger_name = _lines[1]
            import re as _re_init
            for _ll in _lines[1:4]:
                if not _ledger_email:
                    _em = _re_init.search(r'[\w.+-]+@[\w-]+\.[\w.]+', _ll)
                    if _em: _ledger_email = _em.group()
                if not _ledger_phone:
                    _ph = _re_init.search(r'\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}', _ll)
                    if _ph: _ledger_phone = _ph.group()
                if not _ledger_linkedin:
                    _li = _re_init.search(r'linkedin\.com/in/[\w/-]+', _ll)
                    if _li: _ledger_linkedin = _li.group().rstrip('/|')
                if not _ledger_github:
                    _gh = _re_init.search(r'github\.com/[\w-]+', _ll)
                    if _gh: _ledger_github = _gh.group()
                if not _ledger_website:
                    _ws = _re_init.search(r'\b[\w-]+\.me\b', _ll)
                    if _ws: _ledger_website = _ws.group()
    except Exception:
        pass
    st.session_state["_pf_name"]    = _pf0.name    or _ledger_name
    st.session_state["_pf_email"]   = _pf0.email   or _ledger_email
    st.session_state["_pf_phone"]   = _pf0.phone   or _ledger_phone
    st.session_state["_pf_github"]  = _pf0.github  or _ledger_github
    st.session_state["_pf_linkedin"]= _pf0.linkedin or _ledger_linkedin
    st.session_state["_pf_website"] = _pf0.website or _ledger_website
    st.session_state["_pf_summary"] = _pf0.base_summary
    st.session_state["_pf_skills"]  = ", ".join(_pf0.skills)

# Capture navigation state from the PREVIOUS render before anything updates it.
# This must happen at the very top so the sidebar cannot overwrite it first.
_prev_on_prefs = st.session_state.get("_on_prefs_page", False)

# Initial seed on first session load
if "_pf_name" not in st.session_state:
    _seed_profile_keys()

if "pref_role" not in st.session_state:
    _pf_prefs = st.session_state.profile
    st.session_state.pref_role = _pf_prefs.pref_role or "Software Engineer"

if "pref_location" not in st.session_state:
    _pf_prefs = st.session_state.profile
    st.session_state.pref_location = _pf_prefs.pref_location or "Remote"

if "kanban_page" not in st.session_state:
    st.session_state.kanban_page = 0

# AITailor + PDFGenerator — initialized once, reused across all button clicks.
# AITailor will be None if OPENAI_API_KEY is not set; the UI handles that gracefully.

# Load the sentence-transformer model FIRST so LedgerManager can reuse it,
# avoiding a second redundant download and preventing BrokenPipeError from
# tqdm trying to flush a broken stderr pipe during Streamlit's process fork.
if "st_model" not in st.session_state:
    import sys, io
    from sentence_transformers import SentenceTransformer
    _old_stderr = sys.stderr
    sys.stderr = io.StringIO()   # silence tqdm progress during model load
    try:
        st.session_state.st_model = SentenceTransformer("all-MiniLM-L6-v2")
    finally:
        sys.stderr = _old_stderr

if "tailor" not in st.session_state:
    _ledger_content = run_async(st.session_state.repo.get_ledger(_USER_ID))
    if _ledger_content:
        _lm = LedgerManager.from_content(_ledger_content, db_path="data/faiss.index")
    else:
        _ledger_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ledger.md")
        _lm = LedgerManager(ledger_path=_ledger_path, db_path="data/faiss.index")
    _lm.model = st.session_state.st_model   # inject — skip second model load
    try:
        _lm.build_index()
    except FileNotFoundError:
        pass  # ledger not yet created — tailor will show empty facts warning
    try:
        st.session_state.tailor = AITailor(ledger_manager=_lm)
    except ValueError:
        st.session_state.tailor = None  # API key not set

if "pdf_gen" not in st.session_state:
    _tmpl = os.path.join(os.path.dirname(__file__), "..", "core", "templates")
    st.session_state.pdf_gen = PDFGenerator(template_dir=_tmpl)

repo    = st.session_state.repo
profile = st.session_state.profile
tailor  = st.session_state.tailor
pdf_gen = st.session_state.pdf_gen

# st_model is already loaded above — just alias it for use in match scoring
st_model = st.session_state.st_model

# Cache resume text for match scoring (avoids re-reading file every rerun)
if "resume_text_cache" not in st.session_state:
    from src.core.ai import _parse_ledger_as_resume
    _lp_match = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ledger.md")
    st.session_state.resume_text_cache = _parse_ledger_as_resume(_lp_match)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="nav-logo">⚡ Titan<span>Swarm</span></div>', unsafe_allow_html=True)

    total        = run_async(repo.count_all(user_id=_USER_ID))
    n_pending    = len(run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW, user_id=_USER_ID)))
    n_submitted  = len(run_async(repo.get_jobs_by_status(JobStatus.SUBMITTED, user_id=_USER_ID)))
    n_discovered = len(run_async(repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=_USER_ID)))
    n_interview  = len(run_async(repo.get_jobs_by_status(JobStatus.INTERVIEW, user_id=_USER_ID)))

    st.markdown('<hr class="nav-divider">', unsafe_allow_html=True)
    st.markdown('<div class="nav-section-label">Menu</div>', unsafe_allow_html=True)

    nav = st.radio(
        "nav",
        ["Job Feed", "My Applications", "Preferences"],
        label_visibility="collapsed",
        format_func=lambda x: {
            "Job Feed":        "🔍  Job Feed",
            "My Applications": "📋  My Applications",
            "Preferences":     "⚙️  Preferences",
        }[x],
    )

    st.markdown('<hr class="nav-divider">', unsafe_allow_html=True)
    st.markdown('<div class="nav-section-label">Pipeline</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div style="font-size:0.82rem;line-height:2;">
        <span style="color:#475569;">Sourced</span>
        <span style="float:right;color:#e2e8f0;font-weight:700;">{total}</span><br>
        <span style="color:#475569;">Pending Review</span>
        <span style="float:right;color:#fbbf24;font-weight:700;">{n_pending}</span><br>
        <span style="color:#475569;">Applied</span>
        <span style="float:right;color:#34d399;font-weight:700;">{n_submitted}</span><br>
        <span style="color:#475569;">Interview</span>
        <span style="float:right;color:#3b82f6;font-weight:700;">{n_interview}</span>
    </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="nav-divider">', unsafe_allow_html=True)

    # Profile completion score
    pct = profile_completion(profile)
    st.markdown(f'<div style="font-size:0.72rem;color:#475569;font-weight:600;margin-bottom:4px;">PROFILE {int(pct*100)}%</div>', unsafe_allow_html=True)
    st.progress(pct)

    if pct < 1.0:
        st.markdown('<div style="font-size:0.75rem;color:#f59e0b;margin-top:4px;">⚠ Complete your profile for better tailoring</div>', unsafe_allow_html=True)

    st.markdown("")
    st.caption("TitanSwarm v2.0 · Fall 2026 SWE")

# Track which page we're on so Preferences can detect "just arrived" state
st.session_state["_on_prefs_page"] = (nav == "Preferences")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: JOB FEED
# ═════════════════════════════════════════════════════════════════════════════
if nav == "Job Feed":

    # ── Top header ──
    hc, bc = st.columns([4, 1])
    with hc:
        st.markdown('<div class="main-header">Job Feed</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="main-subheader">Showing opportunities for <strong>{st.session_state.pref_role}</strong> · {st.session_state.pref_location}</div>', unsafe_allow_html=True)

    # ── KPI strip ──
    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    kpi_data = [
        (total,       "Total Sourced",  f"+{n_discovered} new"),
        (n_pending,   "Pending Review", "Needs action"),
        (n_submitted, "Applications",   "Sent"),
        (int(n_submitted * 0.15) if n_submitted else 0, "Responses", "Est. rate"),
    ]
    for col, (val, label, sub) in zip([k1, k2, k3, k4], kpi_data):
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{val}</div>
            <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Discovery bar ──
    with st.container(border=True):
        dc1, dc2, dc3 = st.columns([3, 2, 1])
        with dc1:
            search_role = st.text_input("Role", value=st.session_state.pref_role,
                                         placeholder="Software Engineer, ML Engineer…",
                                         label_visibility="collapsed")
        with dc2:
            search_loc = st.text_input("Location", value=st.session_state.pref_location,
                                        placeholder="Remote · San Francisco · Vancouver",
                                        label_visibility="collapsed")
        with dc3:
            find = st.button("🔍  Find Jobs", type="primary", use_container_width=True)

    if find:
        st.session_state.pref_role = search_role
        st.session_state.pref_location = search_loc
        with st.status(f"Sourcing **{search_role}** roles in **{search_loc}**…", expanded=True) as s:
            st.write("🌐  Connecting to job aggregators (LinkedIn · Indeed)…")
            time.sleep(0.5)
            st.write("🔍  Parsing role requirements and extracting JDs…")
            time.sleep(0.4)
            found_ids = run_async(_run_discovery(repo, search_role, search_loc, 25))
            st.session_state.feed_job_ids = found_ids
            st.write(f"✅  **{len(found_ids)} roles** found for this search.")
            s.update(label=f"Done — {len(found_ids)} jobs in feed.", state="complete")
        st.toast(f"{len(found_ids)} opportunities loaded!", icon="⚡")
        st.rerun()

    # ── Filter chips ──
    selected_chip = st.pills(
        "Filter",
        options=["All", "Remote", "Internship", "Full-time", "Co-op"],
        default="All",
        label_visibility="collapsed",
    )

    # ── Search & Sort & Date bar ──
    _search_col, _date_col, _sort_col = st.columns([3, 2, 1])
    with _search_col:
        _search_q = st.text_input(
            "🔎 Search jobs",
            placeholder="Filter by company or role…",
            label_visibility="collapsed",
        )
    with _date_col:
        _date_opt = st.selectbox(
            "Date posted",
            ["Any", "Last 7 days", "Last 14 days", "Last 30 days"],
            label_visibility="collapsed",
        )
    with _sort_col:
        _sort_opt = st.selectbox(
            "Sort",
            ["Best Match", "Company A→Z", "Company Z→A"],
            label_visibility="collapsed",
        )

    # ── Job feed ──
    # Always include both DISCOVERED and PENDING_REVIEW so that a job card's
    # download button remains visible immediately after tailoring (before the
    # user navigates away). Filter to feed_job_ids when a search has been done.
    _feed_ids: list[str] = st.session_state.get("feed_job_ids", [])
    _all_repo_jobs = (run_async(repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=_USER_ID)) +
                      run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW, user_id=_USER_ID)))
    if _feed_ids:
        _id_set = set(_feed_ids)
        _raw_jobs = [j for j in _all_repo_jobs if j.id in _id_set]
    else:
        _raw_jobs = _all_repo_jobs
    all_jobs = filter_jobs(_raw_jobs, selected_chip)
    all_jobs = filter_by_date(all_jobs, _date_opt)
    all_jobs = search_jobs(all_jobs, _search_q)

    # Compute match scores for sorting/display
    _resume_cache = st.session_state.resume_text_cache
    _match_scores: dict[str, int] = {}
    for _j in all_jobs:
        _match_scores[_j.id] = compute_match_score(_resume_cache, _j.job_description, st_model)

    # Apply sort
    if _sort_opt == "Best Match":
        all_jobs.sort(key=lambda j: _match_scores.get(j.id, 0), reverse=True)
    elif _sort_opt == "Company A→Z":
        all_jobs.sort(key=lambda j: j.company.lower())
    elif _sort_opt == "Company Z→A":
        all_jobs.sort(key=lambda j: j.company.lower(), reverse=True)

    if not all_jobs:
        st.markdown("""
        <div style="text-align:center;padding:4rem 1rem;">
            <div style="font-size:3rem;margin-bottom:0.75rem;">🤖</div>
            <div style="font-size:1.1rem;font-weight:700;color:#0f172a;">Your feed is empty</div>
            <div style="font-size:0.875rem;color:#64748b;margin-top:0.4rem;">
                Search for a role above to start sourcing opportunities.
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="font-size:0.82rem;color:#64748b;margin-bottom:0.5rem;">{len(all_jobs)} opportunities found</div>', unsafe_allow_html=True)

        for job in all_jobs:
            skills_html = "".join(f'<span class="skill-pill">{s}</span>' for s in (job.required_skills or [])[:5])
            # HTML-escape the description snippet so scraped HTML/markdown can't
            # break out of the card template and render as raw code on screen.
            desc = _html.escape(job.job_description[:180].rstrip()) + "…"
            _ms = _match_scores.get(job.id, 0)
            _ms_color = "#22c55e" if _ms >= 70 else "#eab308" if _ms >= 40 else "#ef4444"
            _ms_badge = f'<span style="background:{_ms_color};color:#fff;padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:700;">{_ms}% match</span>'

            with st.container(border=True):
                left, right = st.columns([5, 1])

                with left:
                    st.markdown(f"""
                    <div class="jcard-top">
                        {avatar_html(job.company)}
                        <div style="flex:1;min-width:0;">
                            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                                <span class="jcard-company">{job.company}</span>
                                {badge(job.status)}
                                {_ms_badge}
                            </div>
                            <div class="jcard-role">{job.role}</div>
                            <div class="jcard-meta">
                                {f"📍 {job.location} &nbsp;·&nbsp;" if job.location else ""}
                                {f"🕐 {job.date_posted} &nbsp;·&nbsp;" if job.date_posted else ""}
                                🔗 <a href="{job.url}" target="_blank"
                                   style="color:#6366f1;text-decoration:none;">{job.url[:60]}…</a>
                            </div>
                            <div class="jcard-desc">{desc}</div>
                            <div class="jcard-skills">{skills_html}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                with right:
                    st.markdown("<br>", unsafe_allow_html=True)

                    # Show any error from a previous tailor attempt for this job
                    err_key = f"tailor_err_{job.id}"
                    if err_key in st.session_state:
                        st.error(st.session_state.pop(err_key))

                    if st.button("📄 Tailor Resume", key=f"apply_{job.id}", type="primary", use_container_width=True):
                        if tailor is None:
                            st.session_state[err_key] = (
                                "AI engine is not configured. "
                                "Make sure GEMINI_API_KEY (or OPENAI_API_KEY) is set in your .env file."
                            )
                            st.rerun()
                        else:
                            with st.spinner(f"Tailoring resume for {job.company}… (may retry if Gemini is busy)"):
                                try:
                                    result: TailoredApplication = run_async(tailor.tailor_application(job))
                                    _ledger_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ledger.md")
                                    _structured  = _parse_ledger_for_pdf(_ledger_path)
                                    # Always read latest form values — avoids "Your Name" when
                                    # auto-fill populated the keys but Save Profile wasn't clicked
                                    _pi = st.session_state.profile
                                    user_ledger = {
                                        "personal_info": {
                                            "name":     st.session_state.get("_pf_name")     or _pi.name     or "",
                                            "email":    st.session_state.get("_pf_email")    or _pi.email    or "",
                                            "phone":    st.session_state.get("_pf_phone")    or _pi.phone    or "",
                                            "linkedin": st.session_state.get("_pf_linkedin") or _pi.linkedin or "",
                                            "github":   st.session_state.get("_pf_github")   or _pi.github   or "",
                                            "website":  st.session_state.get("_pf_website")  or "",
                                        },
                                        "education":  _structured["education"],
                                        "experience": _structured["experience"],
                                    }
                                    # Sanitize company + role for a readable filename
                                    import re as _re
                                    _safe = lambda s: _re.sub(r'[^\w\s-]', '', s).strip().replace(' ', '_')
                                    _fname = f"{_safe(job.company)}_{_safe(job.role)}_Resume.pdf"
                                    output_path = os.path.join("output", _fname)
                                    os.makedirs("output", exist_ok=True)
                                    run_async(pdf_gen.generate_resume_pdf(user_ledger, result, output_path=output_path))
                                    with open(output_path, "rb") as fh:
                                        pdf_bytes = fh.read()
                                    st.session_state[f"pdf_{job.id}"] = pdf_bytes
                                    st.session_state[f"qa_{job.id}"]  = result.q_and_a_responses
                                    st.session_state[f"gaps_{job.id}"] = result.missing_skills
                                    st.session_state[f"autodownload_{job.id}"] = True
                                    # Persist tailored result to DB so it survives page refresh
                                    run_async(repo.save_tailored_result(
                                        job.id, result.model_dump_json(), pdf_bytes, user_id=_USER_ID
                                    ))
                                    run_async(repo.update_status(job.id, JobStatus.PENDING_REVIEW, user_id=_USER_ID))
                                    st.toast(f"Resume for {job.company} is ready!", icon="✅")
                                    st.rerun()
                                except Exception as e:
                                    import traceback
                                    st.session_state[err_key] = f"Tailoring failed: {e}\n\n{traceback.format_exc()}"
                                    st.rerun()

                    # Show download button if PDF is already generated for this job
                    # Load from DB if not in session state (page was refreshed)
                    if f"pdf_{job.id}" not in st.session_state:
                        _db_result = run_async(repo.get_tailored_result(job.id, user_id=_USER_ID))
                        if _db_result:
                            _db_ai_json, _db_pdf, _db_cl = _db_result
                            st.session_state[f"pdf_{job.id}"] = _db_pdf
                            if _db_cl:
                                st.session_state[f"cl_{job.id}"] = _db_cl
                            try:
                                _db_ta = TailoredApplication.model_validate_json(_db_ai_json)
                                st.session_state[f"qa_{job.id}"] = _db_ta.q_and_a_responses
                                st.session_state[f"gaps_{job.id}"] = _db_ta.missing_skills
                            except Exception:
                                pass
                    if f"pdf_{job.id}" in st.session_state:
                        import re as _re2
                        import base64 as _b64
                        _s2 = lambda s: _re2.sub(r'[^\w\s-]', '', s).strip().replace(' ', '_')
                        _dl_fname = f"{_s2(job.company)}_{_s2(job.role)}_Resume.pdf"
                        _b64_pdf = _b64.b64encode(st.session_state[f"pdf_{job.id}"]).decode()
                        _auto = st.session_state.pop(f"autodownload_{job.id}", False)
                        # Render an invisible anchor; auto-click it once after tailoring
                        st.components.v1.html(
                            f'<a id="dl" href="data:application/pdf;base64,{_b64_pdf}"'
                            f' download="{_dl_fname}" style="display:none">dl</a>'
                            f'{"<script>document.getElementById(\'dl\').click();</script>" if _auto else ""}',
                            height=0,
                        )
                        st.download_button(
                            "⬇️ Download PDF",
                            data=st.session_state[f"pdf_{job.id}"],
                            file_name=_dl_fname,
                            mime="application/pdf",
                            key=f"dl_{job.id}",
                            use_container_width=True,
                        )
                        # Skill Gaps — shown only when there are gaps to report
                        _gaps = st.session_state.get(f"gaps_{job.id}", [])
                        if _gaps:
                            with st.expander(f"Skill Gaps ({len(_gaps)})", expanded=False):
                                st.caption("These skills appear in the JD but are not in your ledger. Consider adding them.")
                                for _g in _gaps:
                                    st.markdown(f"- {_g}")

                    if st.button("Skip", key=f"skip_{job.id}", use_container_width=True):
                        run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=_USER_ID))
                        st.rerun()

                    # Cover letter button — always visible; only active after resume is tailored
                    _has_pdf = f"pdf_{job.id}" in st.session_state
                    if _has_pdf:
                        _cl_err_key = f"cl_err_{job.id}"
                        if _cl_err_key in st.session_state:
                            st.error(st.session_state.pop(_cl_err_key))
                        if f"cl_{job.id}" not in st.session_state:
                            if st.button("✉️ Cover Letter", key=f"cl_{job.id}_btn", use_container_width=True):
                                if tailor is None:
                                    st.session_state[_cl_err_key] = "AI engine not configured."
                                    st.rerun()
                                else:
                                    with st.spinner("Generating cover letter… (may retry if Gemini is busy)"):
                                        try:
                                            from src.core.models import CoverLetterResult
                                            _cl_result = run_async(tailor.generate_cover_letter(job))
                                            st.session_state[f"cl_{job.id}"] = _cl_result
                                            # Generate PDF immediately
                                            _cl_output = f"output/cover_letter_{job.id[:8]}.pdf"
                                            _cl_pdf = run_async(pdf_gen.generate_cover_letter_pdf(
                                                profile=profile,
                                                company=job.company,
                                                role=job.role,
                                                cover_letter=_cl_result,
                                                output_path=_cl_output,
                                            ))
                                            st.session_state[f"cl_pdf_{job.id}"] = _cl_pdf
                                            # Persist body text to DB
                                            run_async(repo.save_tailored_result(
                                                job.id,
                                                st.session_state.get(f"qa_{job.id}", "{}"),
                                                st.session_state[f"pdf_{job.id}"],
                                                cover_letter=_cl_result.body,
                                                user_id=_USER_ID,
                                            ))
                                            st.rerun()
                                        except Exception as e:
                                            st.session_state[_cl_err_key] = f"Cover letter failed: {e}"
                                            st.rerun()
                        # PDF download button — shown once cover letter exists
                        if f"cl_pdf_{job.id}" in st.session_state:
                            st.download_button(
                                label="⬇️ Download Cover Letter PDF",
                                data=st.session_state[f"cl_pdf_{job.id}"],
                                file_name=f"cover_letter_{job.company.replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                key=f"cl_dl_{job.id}",
                                use_container_width=True,
                            )
                    else:
                        # Not yet tailored — show greyed-out button so layout is consistent
                        st.button(
                            "✉️ Cover Letter",
                            key=f"cl_{job.id}_disabled",
                            use_container_width=True,
                            disabled=True,
                            help="Tailor your resume first to unlock the cover letter.",
                        )

                with st.expander("View full description, Q&A & Cover Letter"):
                    st.write(job.job_description)
                    # Show AI-generated Q&A if tailoring has been run for this job
                    if f"qa_{job.id}" in st.session_state:
                        qa = st.session_state[f"qa_{job.id}"]
                        if qa:
                            st.markdown("---")
                            st.markdown("**📋 Application Q&A Answers**")
                            for question, answer in qa.items():
                                st.markdown(f"**Q: {question}**")
                                st.info(answer)
                    # Show cover letter if generated
                    if f"cl_{job.id}" in st.session_state:
                        st.markdown("---")
                        st.markdown("**✉️ Cover Letter**")
                        _cl_body = st.session_state[f"cl_{job.id}"]
                        # Handle both CoverLetterResult object and legacy plain strings
                        _cl_display = _cl_body.body if hasattr(_cl_body, "body") else _cl_body
                        st.text_area(
                            "Cover letter body (copy from here)",
                            value=_cl_display,
                            height=250,
                            key=f"cl_display_{job.id}",
                        )
                    if st.button("✅ Mark as Applied", key=f"mark_{job.id}"):
                        run_async(repo.update_status(job.id, JobStatus.SUBMITTED))
                        st.toast(f"{job.company} marked as submitted!", icon="🎯")
                        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: MY APPLICATIONS (Kanban)
# ═════════════════════════════════════════════════════════════════════════════
elif nav == "My Applications":
    st.markdown('<div class="main-header">My Applications</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subheader">Track every opportunity across your pipeline.</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Fetch all buckets
    buckets = {
        "Pending Review": run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW, user_id=_USER_ID)),
        "Applied":        run_async(repo.get_jobs_by_status(JobStatus.SUBMITTED, user_id=_USER_ID)),
        "Interview":      run_async(repo.get_jobs_by_status(JobStatus.INTERVIEW, user_id=_USER_ID)),
        "Rejected":       run_async(repo.get_jobs_by_status(JobStatus.REJECTED, user_id=_USER_ID)),
    }
    bucket_colors = {
        "Pending Review": "#f59e0b",
        "Applied":        "#6366f1",
        "Interview":      "#3b82f6",
        "Rejected":       "#f87171",
    }

    total_apps = sum(len(v) for v in buckets.values())
    if total_apps == 0:
        st.markdown("""
        <div style="text-align:center;padding:4rem 1rem;">
            <div style="font-size:3rem;">📭</div>
            <div style="font-size:1.1rem;font-weight:700;color:#0f172a;margin-top:0.75rem;">No applications yet</div>
            <div style="font-size:0.875rem;color:#64748b;margin-top:0.4rem;">
                Head to <strong>Job Feed</strong> and hit ⚡ Auto-Apply on a role to get started.
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        cols = st.columns(4)
        for col, (lane_name, jobs) in zip(cols, buckets.items()):
            color = bucket_colors[lane_name]
            with col:
                st.markdown(f"""
                <div class="kanban-col">
                    <div class="kanban-col-header">
                        <span style="color:{color};">{lane_name}</span>
                        <span class="kanban-count">{len(jobs)}</span>
                    </div>
                """, unsafe_allow_html=True)

                if not jobs:
                    st.markdown('<div style="font-size:0.78rem;color:#cbd5e1;text-align:center;padding:1rem 0;">Empty</div>', unsafe_allow_html=True)
                else:
                    for job in jobs[:10]:
                        st.markdown(f"""
                        <div class="kanban-card">
                            <div class="kc-company">{job.company}</div>
                            <div class="kc-role">{job.role}</div>
                            <div class="kc-url">
                                <a href="{job.url}" target="_blank" style="color:#94a3b8;text-decoration:none;">
                                    {job.url[:35]}…
                                </a>
                            </div>
                        </div>""", unsafe_allow_html=True)

                        if lane_name == "Pending Review":
                            bc1, bc2, bc3 = st.columns(3)
                            with bc1:
                                if st.button("✅ Submit", key=f"kanban_sub_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.SUBMITTED, user_id=_USER_ID))
                                    st.rerun()
                            with bc2:
                                if st.button("↩ Return", key=f"kanban_ret_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.DISCOVERED, user_id=_USER_ID))
                                    st.rerun()
                            with bc3:
                                if st.button("✗ Reject", key=f"kanban_rej_pr_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=_USER_ID))
                                    st.rerun()

                        elif lane_name == "Applied":
                            bc1, bc2 = st.columns(2)
                            with bc1:
                                if st.button("🎤 Interview", key=f"kanban_int_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.INTERVIEW, user_id=_USER_ID))
                                    st.rerun()
                            with bc2:
                                if st.button("✗ Reject", key=f"kanban_rej_ap_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=_USER_ID))
                                    st.rerun()

                        elif lane_name == "Interview":
                            if st.button("✗ Reject", key=f"kanban_rej_iv_{job.id}", use_container_width=True):
                                run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=_USER_ID))
                                st.rerun()

                        elif lane_name == "Rejected":
                            if st.button("↩ Restore", key=f"kanban_restore_{job.id}", use_container_width=True):
                                run_async(repo.update_status(job.id, JobStatus.DISCOVERED, user_id=_USER_ID))
                                st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Submitted list with download ──
    submitted_jobs = run_async(repo.get_jobs_by_status(JobStatus.SUBMITTED))
    if submitted_jobs:
        st.markdown("### Applied — Download Resumes")
        for job in submitted_jobs:
            rc1, rc2, rc3 = st.columns([4, 1, 1])
            with rc1:
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:0.75rem;padding:0.4rem 0;">
                    {avatar_html(job.company, size=36, radius=9)}
                    <div>
                        <div style="font-size:0.875rem;font-weight:700;color:#0f172a;">{job.company}</div>
                        <div style="font-size:0.78rem;color:#6366f1;">{job.role}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            with rc2:
                # Serve cached PDF — load from DB if not in session state
                if f"pdf_{job.id}" not in st.session_state:
                    _db_r = run_async(repo.get_tailored_result(job.id))
                    if _db_r:
                        st.session_state[f"pdf_{job.id}"] = _db_r[1]
                _cached = st.session_state.get(f"pdf_{job.id}")
                if _cached:
                    st.download_button("📄 PDF", data=_cached,
                                       file_name=f"{job.company}_Resume.pdf", mime="application/pdf",
                                       key=f"sub_dl_{job.id}", use_container_width=True)
                else:
                    st.button("📄 PDF", key=f"sub_dl_{job.id}", use_container_width=True, disabled=True)
            with rc3:
                if st.button("✗ Reject", key=f"rej_{job.id}", use_container_width=True):
                    run_async(repo.update_status(job.id, JobStatus.REJECTED))
                    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: PREFERENCES
# ═════════════════════════════════════════════════════════════════════════════
elif nav == "Preferences":
    # Re-seed form keys from saved profile when navigating TO this page.
    # This fixes data loss caused by Streamlit cleaning up / resetting widget
    # keys when those widgets were not rendered on a different page.
    # _prev_on_prefs was captured at the very top of this render, BEFORE the
    # sidebar set _on_prefs_page for the current run. If it was False then
    # the user just navigated here — re-seed all form keys from saved profile.
    if not _prev_on_prefs:
        _seed_profile_keys()

    # Flush any pending autofill values BEFORE any keyed widget is instantiated.
    # This avoids the "cannot be modified after widget is instantiated" error.
    if "_pf_pending" in st.session_state:
        for _k, _v in st.session_state.pop("_pf_pending").items():
            st.session_state[_k] = _v

    st.markdown('<div class="main-header">Preferences</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subheader">Configure your target parameters and personal profile. The RAG engine uses this to tailor every application.</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    pct = profile_completion(profile)
    st.markdown(f'<div style="font-size:0.82rem;font-weight:600;color:#374151;margin-bottom:4px;">Profile Completion · {int(pct*100)}%</div>', unsafe_allow_html=True)
    st.progress(pct)
    st.markdown("<br>", unsafe_allow_html=True)

    pc1, pc2 = st.columns([3, 2])

    with pc1:
        # ── Identity ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">Identity</div>', unsafe_allow_html=True)
            a1, a2 = st.columns(2)
            with a1:
                st.text_input("Full Name",  key="_pf_name",    placeholder="Jane Doe")
                st.text_input("Email",      key="_pf_email",   placeholder="jane@sfu.ca")
                st.text_input("Phone",      key="_pf_phone",   placeholder="+1 (604) 000-0000")
            with a2:
                st.text_input("GitHub",   key="_pf_github",   placeholder="github.com/janedoe")
                st.text_input("LinkedIn", key="_pf_linkedin", placeholder="linkedin.com/in/janedoe")
                st.text_input("Website",  key="_pf_website",  placeholder="yoursite.com")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Context ledger ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">Context Ledger — AI Ground Truth</div>', unsafe_allow_html=True)
            st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">The RAG engine uses ONLY these verified facts. No hallucinations.</div>', unsafe_allow_html=True)
            st.text_area(
                "Professional Summary",
                key="_pf_summary", height=110,
                placeholder="2nd-year Computing Science student at SFU, 3.74 GPA. Built a custom Raft consensus DB in Go…",
            )
            st.text_input(
                "Hard Skills (comma-separated)",
                key="_pf_skills",
                placeholder="Python, Go, PostgreSQL, FAISS, LangChain, Docker…",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("💾  Save Profile", type="primary"):
            _saved_profile = UserProfile(
                name=st.session_state.get("_pf_name", ""),
                email=st.session_state.get("_pf_email", ""),
                phone=st.session_state.get("_pf_phone", ""),
                github=st.session_state.get("_pf_github", ""),
                linkedin=st.session_state.get("_pf_linkedin", ""),
                website=st.session_state.get("_pf_website", ""),
                base_summary=st.session_state.get("_pf_summary", ""),
                skills=[s.strip() for s in st.session_state.get("_pf_skills", "").split(",") if s.strip()],
                pref_role=st.session_state.get("pref_role", ""),
                pref_location=st.session_state.get("pref_location", ""),
            )
            st.session_state.profile = _saved_profile
            run_async(repo.save_profile(_saved_profile, user_id=_USER_ID))
            st.toast("Profile saved!", icon="🔒")
            st.rerun()

    with pc2:
        # ── Job preferences ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">Job Preferences</div>', unsafe_allow_html=True)

            ROLE_OPTIONS = [
                "Software Engineer", "Software Engineer Intern",
                "Machine Learning Engineer", "Backend Engineer",
                "Frontend Engineer", "Data Engineer", "Other",
            ]
            pref_role = st.selectbox(
                "Target Role",
                options=ROLE_OPTIONS,
                index=ROLE_OPTIONS.index(st.session_state.pref_role)
                if st.session_state.pref_role in ROLE_OPTIONS else 0,
            )
            pref_loc = st.text_input("Preferred Location", value=st.session_state.pref_location,
                                     placeholder="Remote · Vancouver · San Francisco")

            work_mode = st.multiselect(
                "Work Mode",
                ["Remote", "Hybrid", "On-site"],
                default=["Remote", "Hybrid"],
            )

            job_type = st.multiselect(
                "Job Type",
                ["Internship / Co-op", "Full-time", "Contract"],
                default=["Internship / Co-op"],
            )

            if st.button("Save Preferences", type="primary", use_container_width=True):
                st.session_state.pref_role     = pref_role
                st.session_state.pref_location = pref_loc
                # Persist to DB via profile
                _cur_pf = st.session_state.profile
                _saved_pf = _cur_pf.model_copy(update={
                    "pref_role": pref_role,
                    "pref_location": pref_loc,
                })
                st.session_state.profile = _saved_pf
                run_async(repo.save_profile(_saved_pf, user_id=_USER_ID))

                # ── GitHub enrichment ────────────────────────────────────────
                _gh_handle = st.session_state.get("_pf_github", "").strip()
                if _gh_handle:
                    with st.spinner("Syncing GitHub repos into AI context..."):
                        from src.core.github_enricher import fetch_github_context
                        _gh_text = fetch_github_context(_gh_handle)
                    if _gh_text:
                        _ledger_path = os.path.join(
                            os.path.dirname(__file__), "..", "..", "data", "ledger.md"
                        )
                        _lm_gh = LedgerManager(ledger_path=_ledger_path, db_path="data/faiss.index")
                        _lm_gh.write_github_section(_gh_text)
                        # Rebuild the live tailor index so new repos are immediately searchable
                        if st.session_state.tailor:
                            st.session_state.tailor.ledger.build_index()
                        # Invalidate the resume text cache so tailor picks up new context
                        st.session_state.pop("resume_text_cache", None)
                        st.toast("GitHub repos synced into AI context!", icon="🐙")
                    else:
                        st.warning("Could not fetch GitHub repos — check the username in your profile.")

                st.toast("Preferences saved!", icon="✅")
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Daemon config ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">Daemon Config</div>', unsafe_allow_html=True)
            st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">Configure which roles and locations the background scraper targets. Uses <code>|</code> to separate values internally.</div>', unsafe_allow_html=True)

            _env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

            # Read current values from .env (not os.environ — daemon runs in a separate process)
            _cur_roles = read_env_var(_env_path, "SCRAPER_ROLES",
                read_env_var(_env_path, "SCRAPER_ROLE", "Software Engineer Intern"))
            _cur_locs  = read_env_var(_env_path, "SCRAPER_LOCATIONS",
                read_env_var(_env_path, "SCRAPER_LOCATION", "Vancouver, BC"))
            _cur_interval = read_env_var(_env_path, "SCRAPER_INTERVAL_HOURS", "12")
            _cur_results  = read_env_var(_env_path, "SCRAPER_RESULTS_WANTED", "25")

            # Display pipe-separated strings as one-per-line for readability
            _roles_default  = "\n".join(r.strip() for r in _cur_roles.split("|")  if r.strip())
            _locs_default   = "\n".join(l.strip() for l in _cur_locs.split("|")   if l.strip())

            _daemon_roles = st.text_area(
                "Roles to search (one per line)",
                value=_roles_default,
                height=100,
                key="_daemon_roles",
            )
            _daemon_locs = st.text_area(
                "Locations (one per line)",
                value=_locs_default,
                height=100,
                key="_daemon_locs",
            )
            _dc1, _dc2 = st.columns(2)
            with _dc1:
                _daemon_interval = st.number_input(
                    "Interval (hours)", min_value=1, max_value=168,
                    value=int(_cur_interval) if _cur_interval.isdigit() else 12,
                    key="_daemon_interval",
                )
            with _dc2:
                _daemon_results = st.number_input(
                    "Results per sweep", min_value=5, max_value=100,
                    value=int(_cur_results) if _cur_results.isdigit() else 25,
                    key="_daemon_results",
                )

            # Live sweep counter
            _n_roles = len([r for r in _daemon_roles.splitlines() if r.strip()])
            _n_locs  = len([l for l in _daemon_locs.splitlines()  if l.strip()])
            _n_sweeps = _n_roles * _n_locs
            if _n_sweeps > 0:
                st.caption(f"🔄 {_n_sweeps} concurrent sweep(s) per cycle ({_n_roles} role(s) × {_n_locs} location(s))")

            if st.button("💾  Save Daemon Config", use_container_width=True):
                _roles_pipe = "|".join(r.strip() for r in _daemon_roles.splitlines() if r.strip())
                _locs_pipe  = "|".join(l.strip() for l in _daemon_locs.splitlines()  if l.strip())
                if not _roles_pipe or not _locs_pipe:
                    st.warning("Enter at least one role and one location before saving.")
                else:
                    upsert_env_vars(_env_path, {
                        "SCRAPER_ROLES":          _roles_pipe,
                        "SCRAPER_LOCATIONS":      _locs_pipe,
                        "SCRAPER_INTERVAL_HOURS": str(int(_daemon_interval)),
                        "SCRAPER_RESULTS_WANTED": str(int(_daemon_results)),
                    })
                    st.toast("Daemon config saved! Restart the daemon process to apply.", icon="⚙️")
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ── GitHub context ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">GitHub Context</div>', unsafe_allow_html=True)
            st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">Fetches your public repos and writes them into the AI fact ledger so the tailor can reference your real projects.</div>', unsafe_allow_html=True)
            _gh_display = st.session_state.get("_pf_github", "").strip() or "(no GitHub username saved)"
            st.caption(f"Username: {_gh_display}")
            if st.button("🔄 Refresh GitHub Projects", use_container_width=True):
                _gh_handle = st.session_state.get("_pf_github", "").strip()
                if not _gh_handle:
                    st.warning("Add your GitHub username in the Identity card above and save your profile first.")
                else:
                    with st.spinner(f"Fetching repos for {_gh_handle}…"):
                        from src.core.github_enricher import fetch_github_context
                        _gh_text = fetch_github_context(_gh_handle)
                    if _gh_text:
                        _lp_gh = os.path.join(
                            os.path.dirname(__file__), "..", "..", "data", "ledger.md"
                        )
                        _lm_refresh = LedgerManager(ledger_path=_lp_gh, db_path="data/faiss.index")
                        _lm_refresh.write_github_section(_gh_text)
                        # Rebuild live tailor index so new repos are immediately searchable
                        if st.session_state.tailor:
                            st.session_state.tailor.ledger.build_index()
                        st.session_state.pop("resume_text_cache", None)
                        st.toast("GitHub projects refreshed!", icon="🐙")
                        st.rerun()
                    else:
                        st.warning("Could not fetch repos — check your GitHub username or try again later.")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Resume upload ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">Base Resume</div>', unsafe_allow_html=True)
            st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">Upload your PDF resume — text is extracted and added to the AI\'s fact ledger.</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
            if uploaded and st.button("📥 Ingest Resume into Ledger", use_container_width=True):
                try:
                    import pdfplumber, io, re
                    with pdfplumber.open(io.BytesIO(uploaded.read())) as pdf:
                        text = "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
                    if not text:
                        st.error("Could not extract text from this PDF. Make sure it is not a scanned image.")
                    else:
                        # ── Auto-fill profile fields from resume ────────────────
                        lines = [l.strip() for l in text.splitlines() if l.strip()]
                        email_m    = re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', text, re.IGNORECASE)
                        phone_m    = re.search(r'(\+?1[\s.-])?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}', text)
                        github_m   = re.search(r'github\.com/([\w-]+)', text, re.IGNORECASE)
                        linkedin_m = re.search(r'linkedin\.com/in/([\w-]+)', text, re.IGNORECASE)
                        # ── Stage extracted fields for the form (written before next widget render) ──
                        pf_cur = st.session_state.profile
                        new_name     = (lines[0] if lines else "") or pf_cur.name
                        new_email    = (email_m.group(0)    if email_m    else "") or pf_cur.email
                        new_phone    = (phone_m.group(0)    if phone_m    else "") or pf_cur.phone
                        new_github   = (f"github.com/{github_m.group(1)}"   if github_m   else "") or pf_cur.github
                        new_linkedin = (f"linkedin.com/in/{linkedin_m.group(1)}" if linkedin_m else "") or pf_cur.linkedin
                        # Use a staging key — the _pf_* keys are widget-owned and can't be
                        # written here (widgets already rendered above us on this page).
                        st.session_state["_pf_pending"] = {
                            "_pf_name":     new_name,
                            "_pf_email":    new_email,
                            "_pf_phone":    new_phone,
                            "_pf_github":   new_github,
                            "_pf_linkedin": new_linkedin,
                        }
                        # Persist to profile for PDF generation
                        _upload_profile = UserProfile(
                            name=new_name, email=new_email, phone=new_phone,
                            github=new_github, linkedin=new_linkedin,
                            base_summary=pf_cur.base_summary,
                            skills=pf_cur.skills,
                            pref_role=pf_cur.pref_role,
                            pref_location=pf_cur.pref_location,
                        )
                        st.session_state.profile = _upload_profile
                        run_async(repo.save_profile(_upload_profile, user_id=_USER_ID))
                        # ── Write to ledger (replace any previous import) ──────
                        ledger_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ledger.md")
                        existing = open(ledger_path, encoding="utf-8").read()
                        marker = "## Imported Resume:"
                        base = existing.split(marker)[0].rstrip()
                        with open(ledger_path, "w", encoding="utf-8") as f:
                            f.write(base + f"\n\n{marker} {uploaded.name}\n\n{text}")
                        if st.session_state.tailor:
                            st.session_state.tailor.ledger.build_index()
                        # Clear match-score cache so Job Feed reflects the new resume immediately
                        st.session_state.pop("resume_text_cache", None)
                        st.toast(f"{uploaded.name} ingested ✓  Profile fields auto-filled above.", icon="✅")
                        st.rerun()
                except Exception as e:
                    st.error(f"Resume ingestion failed: {e}")


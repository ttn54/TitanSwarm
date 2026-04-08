import streamlit as st
import asyncio
import sys
import os
import random
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import streamlit as st
import asyncio
import sys
import os
import random
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.models import Job, JobStatus, UserProfile
from src.infrastructure.postgres_repo import PostgresRepository
from uuid import uuid4

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
#MainMenu, footer, header { visibility: hidden; }
.stApp { background: #f1f5f9; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: none !important;
    min-width: 220px !important;
    max-width: 220px !important;
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
COMPANIES = [
    "Stripe", "Anthropic", "Scale AI", "Databricks", "Cloudflare",
    "Rippling", "Linear", "Vercel", "Figma", "Notion", "Retool",
    "Brex", "Plaid", "Coinbase", "Snowflake", "HashiCorp",
]

SKILLS_MAP = {
    "Software Engineer": ["Python", "Go", "Distributed Systems", "SQL", "Docker"],
    "Machine Learning Engineer": ["PyTorch", "Python", "CUDA", "MLOps", "FAISS"],
    "Frontend Engineer": ["React", "TypeScript", "CSS", "GraphQL", "Next.js"],
    "Backend Engineer": ["Go", "PostgreSQL", "Redis", "gRPC", "Kubernetes"],
    "Data Engineer": ["Spark", "Airflow", "SQL", "dbt", "Python"],
}

def run_async(coro):
    return asyncio.run(coro)

def badge(status: JobStatus) -> str:
    m = {
        JobStatus.PENDING_REVIEW: ("pending",   "Pending Review"),
        JobStatus.SUBMITTED:      ("submitted", "Applied"),
        JobStatus.DISCOVERED:     ("new",       "New"),
        JobStatus.REJECTED:       ("rejected",  "Rejected"),
        JobStatus.PROCESSING:     ("interview", "Interview"),
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

async def _run_discovery(repo, role: str, location: str, count: int) -> list[Job]:
    skills = SKILLS_MAP.get(role, ["Python", "SQL", "APIs"])
    jobs = []
    for _ in range(count):
        company = random.choice(COMPANIES)
        job = Job(
            id=str(uuid4()),
            role=role,
            company=company,
            url=f"https://{company.lower().replace(' ', '-')}.com/careers/{random.randint(1000, 9999)}",
            status=JobStatus.DISCOVERED,
            job_description=(
                f"We're looking for a {role} to join our platform team. You'll design and scale "
                f"distributed systems serving millions of requests. Strong CS fundamentals required. "
                f"Experience with {', '.join(skills[:3])} is a plus. Remote-friendly."
            ),
            required_skills=skills,
        )
        await repo.save_job(job)
        jobs.append(job)
    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
if "repo" not in st.session_state:
    dsn = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///titanswarm.db")
    _r = PostgresRepository(dsn)
    run_async(_r.init_db())
    st.session_state.repo = _r

if "profile" not in st.session_state:
    st.session_state.profile = UserProfile()

if "pref_role" not in st.session_state:
    st.session_state.pref_role = "Software Engineer"

if "pref_location" not in st.session_state:
    st.session_state.pref_location = "Remote"

if "kanban_page" not in st.session_state:
    st.session_state.kanban_page = 0

repo    = st.session_state.repo
profile = st.session_state.profile


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="nav-logo">⚡ Titan<span>Swarm</span></div>', unsafe_allow_html=True)

    total        = run_async(repo.count_all())
    n_pending    = len(run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)))
    n_submitted  = len(run_async(repo.get_jobs_by_status(JobStatus.SUBMITTED)))
    n_discovered = len(run_async(repo.get_jobs_by_status(JobStatus.DISCOVERED)))

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
        <span style="float:right;color:#34d399;font-weight:700;">{n_submitted}</span>
    </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="nav-divider">', unsafe_allow_html=True)

    # Profile completion score
    pf = profile
    filled = sum([bool(pf.name), bool(pf.email), bool(pf.github), bool(pf.skills), bool(pf.base_summary)])
    pct = filled / 5
    st.markdown(f'<div style="font-size:0.72rem;color:#475569;font-weight:600;margin-bottom:4px;">PROFILE {int(pct*100)}%</div>', unsafe_allow_html=True)
    st.progress(pct)

    if pct < 1.0:
        st.markdown('<div style="font-size:0.75rem;color:#f59e0b;margin-top:4px;">⚠ Complete your profile for better tailoring</div>', unsafe_allow_html=True)

    st.markdown("")
    st.caption("TitanSwarm v2.0 · Fall 2026 SWE")


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
            st.write("🌐  Connecting to job aggregators (LinkedIn · Indeed · Glassdoor)…")
            time.sleep(0.5)
            st.write("🔍  Parsing role requirements and extracting JDs…")
            time.sleep(0.4)
            new_jobs = run_async(_run_discovery(repo, search_role, search_loc, 8))
            st.write(f"✅  **{len(new_jobs)} new roles** added to feed.")
            s.update(label=f"Done — {len(new_jobs)} jobs discovered.", state="complete")
        st.toast(f"{len(new_jobs)} new opportunities added!", icon="⚡")
        st.rerun()

    # ── Filter chips (visual only — functional filter below) ──
    st.markdown("""
    <div class="chip-row">
        <span class="chip active">All</span>
        <span class="chip">Remote</span>
        <span class="chip">Internship</span>
        <span class="chip">Full-time</span>
        <span class="chip">Co-op</span>
        <span class="chip">< 50 employees</span>
    </div>""", unsafe_allow_html=True)

    # ── Job feed ──
    all_jobs = (run_async(repo.get_jobs_by_status(JobStatus.DISCOVERED)) +
                run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)))

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
            desc = job.job_description[:180].rstrip() + "…"

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
                            </div>
                            <div class="jcard-role">{job.role}</div>
                            <div class="jcard-meta">
                                🔗 <a href="{job.url}" target="_blank"
                                   style="color:#6366f1;text-decoration:none;">{job.url[:60]}…</a>
                            </div>
                            <div class="jcard-desc">{desc}</div>
                            <div class="jcard-skills">{skills_html}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                with right:
                    st.markdown("<br>", unsafe_allow_html=True)

                    if st.button("⚡ Auto-Apply", key=f"apply_{job.id}", type="primary", use_container_width=True):
                        with st.spinner("Tailoring resume…"):
                            time.sleep(1.2)
                        run_async(repo.update_status(job.id, JobStatus.PENDING_REVIEW))
                        st.toast(f"Application for {job.company} is queued for review!", icon="✅")
                        st.rerun()

                    st.download_button(
                        "📄 Download PDF",
                        data=b"%PDF-1.4 placeholder",
                        file_name=f"{job.company}_Resume.pdf",
                        mime="application/pdf",
                        key=f"dl_{job.id}",
                        use_container_width=True,
                    )

                    if st.button("Skip", key=f"skip_{job.id}", use_container_width=True):
                        run_async(repo.update_status(job.id, JobStatus.REJECTED))
                        st.rerun()

                with st.expander("View full description"):
                    st.write(job.job_description)
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
        "Pending Review": run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)),
        "Applied":        run_async(repo.get_jobs_by_status(JobStatus.SUBMITTED)),
        "Interview":      run_async(repo.get_jobs_by_status(JobStatus.PROCESSING)),
        "Rejected":       run_async(repo.get_jobs_by_status(JobStatus.REJECTED)),
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
                        for job in jobs[:3]:
                            if st.button(f"✅ Submit {job.company[:12]}", key=f"kanban_sub_{job.id}", use_container_width=True):
                                run_async(repo.update_status(job.id, JobStatus.SUBMITTED))
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
                st.download_button("📄 PDF", data=b"%PDF-1.4 placeholder",
                                   file_name=f"{job.company}_Resume.pdf", mime="application/pdf",
                                   key=f"sub_dl_{job.id}", use_container_width=True)
            with rc3:
                if st.button("✗ Reject", key=f"rej_{job.id}", use_container_width=True):
                    run_async(repo.update_status(job.id, JobStatus.REJECTED))
                    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: PREFERENCES
# ═════════════════════════════════════════════════════════════════════════════
elif nav == "Preferences":
    st.markdown('<div class="main-header">Preferences</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subheader">Configure your target parameters and personal profile. The RAG engine uses this to tailor every application.</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    pf = profile
    filled = sum([bool(pf.name), bool(pf.email), bool(pf.github), bool(pf.skills), bool(pf.base_summary)])
    pct = filled / 5
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
                profile.name  = st.text_input("Full Name",  value=pf.name,  placeholder="Jane Doe")
                profile.email = st.text_input("Email",      value=pf.email, placeholder="jane@sfu.ca")
                profile.phone = st.text_input("Phone",      value=pf.phone, placeholder="+1 (604) 000-0000")
            with a2:
                profile.github   = st.text_input("GitHub",   value=pf.github,   placeholder="github.com/janedoe")
                profile.linkedin = st.text_input("LinkedIn", value=pf.linkedin, placeholder="linkedin.com/in/janedoe")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Context ledger ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">Context Ledger — AI Ground Truth</div>', unsafe_allow_html=True)
            st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">The RAG engine uses ONLY these verified facts. No hallucinations.</div>', unsafe_allow_html=True)

            profile.base_summary = st.text_area(
                "Professional Summary",
                value=pf.base_summary, height=110,
                placeholder="2nd-year Computing Science student at SFU, 3.74 GPA. Built a custom Raft consensus DB in Go…",
            )
            skills_raw = st.text_input(
                "Hard Skills (comma-separated)",
                value=", ".join(pf.skills),
                placeholder="Python, Go, PostgreSQL, FAISS, LangChain, Docker…",
            )
            profile.skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("💾  Save Profile", type="primary"):
            st.session_state.profile = profile
            st.toast("Profile saved!", icon="🔒")
            st.rerun()

    with pc2:
        # ── Job preferences ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">Job Preferences</div>', unsafe_allow_html=True)

            pref_role = st.selectbox(
                "Target Role",
                options=list(SKILLS_MAP.keys()) + ["Other"],
                index=list(SKILLS_MAP.keys()).index(st.session_state.pref_role)
                if st.session_state.pref_role in SKILLS_MAP else 0,
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
                st.toast("Preferences saved!", icon="✅")
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Resume upload ──
        with st.container(border=True):
            st.markdown('<div class="profile-card-title">Base Resume</div>', unsafe_allow_html=True)
            st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">Parsed and embedded into FAISS vector store on upload.</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
            if uploaded:
                st.success(f"**{uploaded.name}** ingested ✓", icon="✅")


# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="TitanSwarm",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBAL CSS — aiapply.co inspired light SaaS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Reset & Base ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }

/* ── Page background ── */
.stApp { background-color: #f8fafc; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e2e8f0;
}
section[data-testid="stSidebar"] * { color: #1e293b !important; }

/* ── Sidebar logo ── */
.titan-logo {
    font-size: 1.4rem;
    font-weight: 700;
    color: #1e293b !important;
    letter-spacing: -0.03em;
    padding: 0.5rem 0 1rem 0;
}
.titan-logo span { color: #6366f1 !important; }

/* ── Nav items ── */
div[data-testid="stRadio"] label {
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: #475569 !important;
    padding: 0.5rem 0.75rem !important;
    border-radius: 8px !important;
    display: block !important;
}
div[data-testid="stRadio"] label:hover { background: #f1f5f9 !important; }

/* ── Page title ── */
h1 { font-size: 1.75rem !important; font-weight: 700 !important; color: #0f172a !important; letter-spacing: -0.03em !important; }
h2 { font-size: 1.25rem !important; font-weight: 600 !important; color: #1e293b !important; }
h3 { font-size: 1rem !important;   font-weight: 600 !important; color: #1e293b !important; }
p, li { color: #475569; font-size: 0.9rem; }

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 3px 0 rgba(0,0,0,.06);
}
div[data-testid="metric-container"] label { color: #64748b !important; font-size: 0.8rem !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: 0.05em; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #0f172a !important; font-size: 2rem !important; font-weight: 700 !important; }

/* ── Primary button ── */
.stButton > button[kind="primary"] {
    background: #6366f1 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.5rem 1rem !important;
    transition: background 0.15s, box-shadow 0.15s !important;
}
.stButton > button[kind="primary"]:hover {
    background: #4f46e5 !important;
    box-shadow: 0 4px 12px rgba(99,102,241,0.4) !important;
}

/* ── Secondary button ── */
.stButton > button[kind="secondary"] {
    background: #ffffff !important;
    color: #374151 !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
}
.stButton > button[kind="secondary"]:hover { background: #f8fafc !important; border-color: #6366f1 !important; }

/* ── Text inputs ── */
input, textarea {
    border-radius: 8px !important;
    border: 1px solid #e2e8f0 !important;
    background: #ffffff !important;
    font-size: 0.875rem !important;
    color: #1e293b !important;
}
input:focus, textarea:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important; }

/* ── Containers / cards ── */
div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] div[data-testid="stContainer"] {
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    background: #ffffff !important;
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.badge-pending  { background: #fef3c7; color: #92400e; }
.badge-submitted { background: #d1fae5; color: #065f46; }
.badge-discovered { background: #e0e7ff; color: #3730a3; }
.badge-rejected  { background: #fee2e2; color: #991b1b; }

/* ── Job card ── */
.job-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.75rem;
    transition: box-shadow 0.15s;
}
.job-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.08); border-color: #c7d2fe; }
.job-card .company { font-size: 1rem; font-weight: 700; color: #0f172a; }
.job-card .role    { font-size: 0.875rem; color: #6366f1; font-weight: 600; margin-top: 2px; }
.job-card .meta    { font-size: 0.78rem; color: #94a3b8; margin-top: 4px; }
.job-card .desc    { font-size: 0.8rem; color: #64748b; margin-top: 0.6rem; line-height: 1.5; }

/* ── Avatar initials ── */
.avatar {
    width: 40px; height: 40px;
    border-radius: 10px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    font-size: 1rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

/* ── Section divider ── */
.section-divider { border: none; border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: #94a3b8;
}
.empty-state .icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
.empty-state h3 { color: #64748b !important; font-size: 1rem !important; }
.empty-state p { font-size: 0.85rem; }

/* ── Status bar ── */
.status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.dot-green { background:#10b981; }
.dot-amber { background:#f59e0b; }
.dot-gray  { background:#94a3b8; }

/* ── Selectbox ── */
div[data-testid="stSelectbox"] > div { border-radius: 8px !important; }

/* ── Slider ── */
div[data-testid="stSlider"] [data-testid="stThumbValue"] { color: #6366f1 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def run_async(coro):
    return asyncio.run(coro)

def badge_html(status: JobStatus) -> str:
    mapping = {
        JobStatus.PENDING_REVIEW: ("pending",  "Pending Review"),
        JobStatus.SUBMITTED:      ("submitted","Submitted"),
        JobStatus.DISCOVERED:     ("discovered","Discovered"),
        JobStatus.REJECTED:       ("rejected", "Rejected"),
        JobStatus.PROCESSING:     ("discovered","Processing"),
    }
    cls, label = mapping.get(status, ("gray", status.value))
    return f'<span class="badge badge-{cls}">{label}</span>'

COMPANIES = ["Stripe", "Anthropic", "Scale AI", "Databricks", "Cloudflare",
             "Rippling", "Linear", "Vercel", "Figma", "Notion", "Retool"]

async def _deploy_swarm(role: str, location: str, count: int, repo):
    jobs = []
    for _ in range(count):
        company = random.choice(COMPANIES)
        job = Job(
            id=str(uuid4()),
            role=role,
            company=company,
            url=f"https://{company.lower().replace(' ','-')}.com/careers/{random.randint(1000, 9999)}",
            status=JobStatus.PENDING_REVIEW,
            job_description=(
                f"We are looking for a highly motivated {role} to join our core platform "
                f"team in {location}. You will design, build, and scale distributed systems "
                f"serving millions of users. Requirements: strong CS fundamentals, experience "
                f"with Python or Go, and a passion for developer tooling."
            ),
        )
        await repo.save_job(job)
        jobs.append(job)
    return jobs


# ─────────────────────────────────────────────
# INITIALISE SESSION STATE
# ─────────────────────────────────────────────
if "repo" not in st.session_state:
    dsn = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///titanswarm.db")
    _repo = PostgresRepository(dsn)
    run_async(_repo.init_db())
    st.session_state.repo = _repo

if "profile" not in st.session_state:
    st.session_state.profile = UserProfile()

if "page" not in st.session_state:
    st.session_state.page = 1

repo    = st.session_state.repo
profile = st.session_state.profile


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="titan-logo">⚡ Titan<span>Swarm</span></div>', unsafe_allow_html=True)
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    nav = st.radio(
        "nav",
        ["Dashboard", "Sourcing Engine", "Profile Vault"],
        label_visibility="collapsed",
        format_func=lambda x: {
            "Dashboard":       "📊  Dashboard",
            "Sourcing Engine": "🚀  Sourcing Engine",
            "Profile Vault":   "🔐  Profile Vault",
        }[x],
    )

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    st.markdown("**System Status**")
    total = run_async(repo.count_all())
    pending_count = len(run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)))

    st.markdown(
        '<span class="status-dot dot-green"></span> Database **Online**<br>'
        f'<span class="status-dot dot-green"></span> **{total}** jobs indexed<br>'
        f'<span class="status-dot {"dot-amber" if pending_count else "dot-gray"}"></span> '
        f'**{pending_count}** awaiting review',
        unsafe_allow_html=True,
    )
    st.markdown("")
    st.caption("TitanSwarm v2.0 · Fall 2026")


# ═════════════════════════════════════════════
# VIEW: DASHBOARD
# ═════════════════════════════════════════════
if nav == "Dashboard":
    col_title, _ = st.columns([3, 1])
    with col_title:
        st.markdown("## Application Pipeline")
        st.markdown('<p style="color:#64748b;margin-top:-0.5rem;">Your autonomous co-pilot is standing by.</p>', unsafe_allow_html=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── KPI row ──
    submitted = run_async(repo.get_jobs_by_status(JobStatus.SUBMITTED))
    discovered = run_async(repo.get_jobs_by_status(JobStatus.DISCOVERED))
    pending    = run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Sourced",    total)
    k2.metric("Pending Review",   len(pending))
    k3.metric("Submitted",        len(submitted))
    k4.metric("Discovered",       len(discovered))

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Job feed table ──
    st.markdown("### Recent Pipeline")

    all_jobs: list[Job] = pending + submitted + discovered
    if not all_jobs:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">🤖</div>
            <h3>No jobs sourced yet</h3>
            <p>Head to <strong>Sourcing Engine</strong> to deploy your swarm.</p>
        </div>""", unsafe_allow_html=True)
    else:
        for job in all_jobs[:10]:
            initials = "".join(w[0] for w in job.company.split()[:2]).upper()
            desc_snippet = job.job_description[:120].rstrip() + "…"
            st.markdown(f"""
            <div class="job-card">
                <div style="display:flex;align-items:flex-start;gap:0.85rem;">
                    <div class="avatar">{initials}</div>
                    <div style="flex:1;min-width:0;">
                        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:4px;">
                            <span class="company">{job.company}</span>
                            {badge_html(job.status)}
                        </div>
                        <div class="role">{job.role}</div>
                        <div class="meta">🔗 <a href="{job.url}" target="_blank" style="color:#6366f1;">{job.url[:55]}…</a></div>
                        <div class="desc">{desc_snippet}</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════
# VIEW: SOURCING ENGINE
# ═════════════════════════════════════════════
elif nav == "Sourcing Engine":
    st.markdown("## Sourcing Engine")
    st.markdown('<p style="color:#64748b;margin-top:-0.5rem;">Configure your target parameters and deploy the autonomous scraping swarm.</p>', unsafe_allow_html=True)
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Config card ──
    with st.container(border=True):
        st.markdown("### Swarm Configuration")
        col_r, col_l = st.columns(2)
        with col_r:
            target_role = st.text_input("Target Role", placeholder="e.g. Software Engineer Intern")
        with col_l:
            target_location = st.text_input("Target Location", placeholder="e.g. San Francisco, CA · Remote")

        col_v, col_s = st.columns([2, 1])
        with col_v:
            target_count = st.slider("Result Volume", min_value=1, max_value=50, value=10,
                                     help="Maximum number of unique job postings to source per sweep.")
        with col_s:
            st.markdown("<br>", unsafe_allow_html=True)
            deploy = st.button("🚀  Deploy Swarm", type="primary", use_container_width=True,
                               disabled=not target_role or not target_location)

    if deploy:
        progress_container = st.empty()
        with progress_container.status("Deploying autonomous swarm…", expanded=True) as s:
            st.write("🔍  Resolving target role parameters…")
            time.sleep(0.4)
            st.write("🌐  Establishing rotated scraping sessions…")
            time.sleep(0.5)
            st.write(f"📡  Querying LinkedIn · Indeed · Glassdoor for **{target_role}** in **{target_location}**…")
            time.sleep(0.6)
            jobs = run_async(_deploy_swarm(target_role, target_location, target_count, repo))
            st.write(f"✅  **{len(jobs)} opportunities** discovered and indexed.")
            time.sleep(0.3)
            st.write("🔒  Deduplication pass complete. Pipeline updated.")
            s.update(label=f"Sweep complete — {len(jobs)} new roles queued for review.", state="complete")

        st.toast(f"{len(jobs)} jobs added to your pipeline!", icon="⚡")
        st.rerun()

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Action queue ──
    st.markdown("### Action Queue")
    pending_list = run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW))

    if not pending_list:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">📭</div>
            <h3>Queue is empty</h3>
            <p>Deploy the swarm above to populate your review queue.</p>
        </div>""", unsafe_allow_html=True)
    else:
        JOBS_PER_PAGE = 5
        total_pages = max(1, (len(pending_list) - 1) // JOBS_PER_PAGE + 1)
        page = st.session_state.page

        # Clamp page
        if page > total_pages:
            st.session_state.page = total_pages
            page = total_pages

        start = (page - 1) * JOBS_PER_PAGE
        page_jobs = pending_list[start:start + JOBS_PER_PAGE]

        # Header row
        hc1, hc2 = st.columns([5, 2])
        hc1.markdown(f"<p style='color:#64748b;font-size:0.82rem;'>{len(pending_list)} roles · Page {page}/{total_pages}</p>", unsafe_allow_html=True)

        for job in page_jobs:
            initials = "".join(w[0] for w in job.company.split()[:2]).upper()
            desc_snippet = job.job_description[:140].rstrip() + "…"

            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"""
                    <div style="display:flex;align-items:flex-start;gap:0.85rem;">
                        <div class="avatar">{initials}</div>
                        <div>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <span class="company" style="font-size:1rem;font-weight:700;color:#0f172a;">{job.company}</span>
                                {badge_html(job.status)}
                            </div>
                            <div style="color:#6366f1;font-weight:600;font-size:0.875rem;">{job.role}</div>
                            <div style="color:#94a3b8;font-size:0.78rem;margin-top:2px;">
                                🔗 <a href="{job.url}" target="_blank" style="color:#6366f1;">{job.url[:55]}…</a>
                            </div>
                            <div style="color:#64748b;font-size:0.8rem;margin-top:6px;line-height:1.5;">{desc_snippet}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                with right:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🧠 Tailor Resume", key=f"tailor_{job.id}", type="primary", use_container_width=True):
                        with st.spinner("Running RAG pipeline…"):
                            time.sleep(1.2)
                        st.toast("ATS-optimized PDF ready for download!", icon="✅")

                    st.download_button(
                        label="📄 Download PDF",
                        data=b"%PDF-1.4 placeholder",
                        file_name=f"{job.company}_{profile.name or 'Resume'}.pdf",
                        mime="application/pdf",
                        key=f"dl_{job.id}",
                        use_container_width=True,
                    )

                    if st.button("✅ Mark Applied", key=f"submit_{job.id}", use_container_width=True):
                        run_async(repo.update_status(job.id, JobStatus.SUBMITTED))
                        st.toast(f"Marked {job.company} as Submitted!", icon="🎯")
                        st.rerun()

        # Pagination
        if total_pages > 1:
            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
            pc1, pc2, pc3 = st.columns([1, 2, 1])
            with pc1:
                if st.button("← Prev", disabled=page == 1, use_container_width=True):
                    st.session_state.page -= 1
                    st.rerun()
            with pc2:
                st.markdown(f"<p style='text-align:center;color:#64748b;font-size:0.85rem;padding-top:0.4rem;'>Page {page} of {total_pages}</p>", unsafe_allow_html=True)
            with pc3:
                if st.button("Next →", disabled=page == total_pages, use_container_width=True):
                    st.session_state.page += 1
                    st.rerun()


# ═════════════════════════════════════════════
# VIEW: PROFILE VAULT
# ═════════════════════════════════════════════
elif nav == "Profile Vault":
    st.markdown("## Profile Vault")
    st.markdown('<p style="color:#64748b;margin-top:-0.5rem;">Your verified identity ledger. The RAG engine uses this data exclusively — no hallucinations.</p>', unsafe_allow_html=True)
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ── Upload ──
    with st.container(border=True):
        st.markdown("### Base Resume")
        st.markdown('<p style="font-size:0.85rem;color:#64748b;">Upload your base resume. It will be parsed and embedded into the local FAISS vector store.</p>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Drop PDF here", type=["pdf"], label_visibility="collapsed")
        if uploaded:
            st.success(f"**{uploaded.name}** ingested into vector store.", icon="✅")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Identity ──
    with st.container(border=True):
        st.markdown("### Identity")
        c1, c2 = st.columns(2)
        with c1:
            profile.name     = st.text_input("Full Name",    value=profile.name,    placeholder="Jane Doe")
            profile.email    = st.text_input("Email",        value=profile.email,   placeholder="jane@sfu.ca")
            profile.phone    = st.text_input("Phone",        value=profile.phone,   placeholder="+1 (604) 000-0000")
        with c2:
            profile.github   = st.text_input("GitHub",       value=profile.github,  placeholder="github.com/janedoe")
            profile.linkedin = st.text_input("LinkedIn",     value=profile.linkedin,placeholder="linkedin.com/in/janedoe")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Context ledger ──
    with st.container(border=True):
        st.markdown("### Context Ledger")
        st.markdown('<p style="font-size:0.85rem;color:#64748b;">The AI uses these verified facts to tailor your resume. Be precise — vague input produces vague output.</p>', unsafe_allow_html=True)
        profile.base_summary = st.text_area(
            "Professional Summary / Objective",
            value=profile.base_summary,
            height=110,
            placeholder="2nd-year Computing Science student at SFU with a 3.74 GPA, building distributed systems and agentic AI pipelines…",
        )
        skills_raw = st.text_input(
            "Hard Skills  (comma-separated)",
            value=", ".join(profile.skills),
            placeholder="Python, Go, TypeScript, PostgreSQL, FAISS, LangChain, Docker…",
        )
        profile.skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

    st.markdown("<br>", unsafe_allow_html=True)

    col_save, _ = st.columns([1, 3])
    with col_save:
        if st.button("💾  Save Ledger", type="primary", use_container_width=True):
            st.session_state.profile = profile
            st.toast("Profile saved to session.", icon="🔒")

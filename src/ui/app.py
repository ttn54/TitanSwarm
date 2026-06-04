"""
TitanSwarm — Dispatch Terminal

Thin entry point that wires together:
  - Global styles
  - Auth gate (login/register)
  - Session state initialization
  - Sidebar navigation
  - Page routing (Job Feed | My Applications | Preferences)

All page rendering logic lives in ``src.ui.pages.*``.
All shared helpers live in ``src.ui.components``.
All auth logic lives in ``src.ui.auth``.
"""
import asyncio
import os
import sys
import time as _time
import html as _html

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.models import JobStatus
from src.ui.styles import inject_styles
from src.ui.auth import render_auth_page, delete_session_cookie
from src.ui.state import (
    init_repository, restore_session_from_cookie,
    init_user_profile, init_form_state, init_ai_stack, init_resume_cache,
)
from src.ui.components import run_async, profile_completion


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
# GLOBAL STYLES
# ─────────────────────────────────────────────────────────────────────────────
inject_styles()

# ─────────────────────────────────────────────────────────────────────────────
# INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
init_repository()
restore_session_from_cookie()

# ─────────────────────────────────────────────────────────────────────────────
# AUTH GATE
# ─────────────────────────────────────────────────────────────────────────────
if "user_id" not in st.session_state:
    render_auth_page()
    st.stop()

# From here down, the user is authenticated.
_USER_ID: int = st.session_state.get("user_id", 1)

# ─────────────────────────────────────────────────────────────────────────────
# POST-AUTH SESSION SETUP
# ─────────────────────────────────────────────────────────────────────────────
init_user_profile(_USER_ID)

# Capture navigation state from the PREVIOUS render before anything updates it.
_prev_on_prefs = st.session_state.get("_on_prefs_page", False)

init_form_state()
init_ai_stack(_USER_ID)
init_resume_cache(_USER_ID)

repo    = st.session_state.repo
profile = st.session_state.profile
tailor  = st.session_state.tailor
pdf_gen = st.session_state.pdf_gen
st_model = st.session_state.st_model


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="nav-logo">⚡ Titan<span>Swarm</span></div>', unsafe_allow_html=True)

    # Cache sidebar pipeline counts — re-query at most every 30 seconds
    _now = int(_time.time())
    _side_ts = st.session_state.get("_side_ts", 0)
    if _now - _side_ts > 30 or "_side_data" not in st.session_state:
        async def _sidebar_counts():
            _pend, _subm, _disc, _intv, _rej = await asyncio.gather(
                repo.get_jobs_by_status(JobStatus.PENDING_REVIEW, user_id=_USER_ID),
                repo.get_jobs_by_status(JobStatus.SUBMITTED, user_id=_USER_ID),
                repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=_USER_ID),
                repo.get_jobs_by_status(JobStatus.INTERVIEW, user_id=_USER_ID),
                repo.get_jobs_by_status(JobStatus.REJECTED, user_id=_USER_ID),
            )
            _active = len(_pend) + len(_subm) + len(_disc) + len(_intv)
            return _active, len(_pend), len(_subm), len(_disc), len(_intv)
        st.session_state["_side_data"] = run_async(_sidebar_counts())
        st.session_state["_side_ts"] = _now
    total, n_pending, n_submitted, n_discovered, n_interview = st.session_state["_side_data"]

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

    pct = profile_completion(profile)
    st.markdown(f'<div style="font-size:0.72rem;color:#475569;font-weight:600;margin-bottom:4px;">PROFILE {int(pct*100)}%</div>', unsafe_allow_html=True)
    st.progress(pct)

    if pct < 1.0:
        st.markdown('<div style="font-size:0.75rem;color:#f59e0b;margin-top:4px;">⚠ Complete your profile for better tailoring</div>', unsafe_allow_html=True)

    st.markdown("")
    st.caption("TitanSwarm v2.0")

    st.markdown('<hr class="nav-divider">', unsafe_allow_html=True)
    _uname = st.session_state.get("username", "")
    st.markdown(f'<div style="font-size:0.75rem;color:#64748b;margin-bottom:0.5rem;">Logged in as <strong style="color:#94a3b8;">{_html.escape(_uname)}</strong></div>', unsafe_allow_html=True)
    if st.button("🚪 Log Out", use_container_width=True):
        delete_session_cookie()
        st.session_state.clear()
        st.session_state["_force_logout"] = True
        st.stop()

# Track which page we're on for Preferences page state management
st.session_state["_on_prefs_page"] = (nav == "Preferences")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE ROUTING
# ─────────────────────────────────────────────────────────────────────────────
if nav == "Job Feed":
    from src.ui.views.job_feed import render as render_job_feed
    render_job_feed(repo, profile, tailor, pdf_gen, st_model, _USER_ID)

elif nav == "My Applications":
    from src.ui.views.applications import render as render_applications
    render_applications(repo, _USER_ID)

elif nav == "Preferences":
    from src.ui.views.preferences import render as render_preferences
    render_preferences(repo, profile, tailor, _USER_ID, _prev_on_prefs)

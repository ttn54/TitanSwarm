"""
Session state initialization for TitanSwarm.

Handles:
- Repository initialization
- Cookie-based session restoration
- AI tailor + PDF generator warm-up
- Resume text caching
"""
from __future__ import annotations

import os
import streamlit as st

from src.core.models import UserProfile
from src.core.ledger import LedgerManager
from src.core.ai import AITailor
from src.core.pdf_generator import PDFGenerator
from src.infrastructure.postgres_repo import PostgresRepository
from src.ui.components import run_async
from src.ui.auth import verify_cookie, get_cookie_name


def init_repository():
    """Initialize the database repository (once per session)."""
    if "repo" not in st.session_state:
        dsn = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///titanswarm.db")
        _r = PostgresRepository(dsn)
        run_async(_r.init_db())
        st.session_state.repo = _r


def restore_session_from_cookie():
    """Attempt to restore user session from a signed cookie."""
    if st.session_state.pop("_force_logout", False):
        # Logout was just triggered — cookie JS is deleting it client-side.
        # Skip restoration so we show the login page immediately.
        return

    if "user_id" not in st.session_state:
        _cv = st.context.cookies.get(get_cookie_name())
        if _cv:
            _restored = verify_cookie(_cv)
            if _restored:
                st.session_state["user_id"], st.session_state["username"] = _restored


def init_user_profile(user_id: int):
    """Load user profile from DB or create a blank one."""
    if "profile" not in st.session_state:
        _db_profile = run_async(st.session_state.repo.get_profile(user_id=user_id))
        st.session_state.profile = _db_profile if _db_profile else UserProfile()


def seed_profile_keys():
    """Populate _pf_* session-state keys from the saved profile only."""
    _pf0 = st.session_state.profile
    st.session_state["_pf_name"]    = _pf0.name    or ""
    st.session_state["_pf_email"]   = _pf0.email   or ""
    st.session_state["_pf_phone"]   = _pf0.phone   or ""
    st.session_state["_pf_github"]  = _pf0.github  or ""
    st.session_state["_pf_linkedin"]= _pf0.linkedin or ""
    st.session_state["_pf_website"] = _pf0.website or ""
    st.session_state["_pf_summary"] = _pf0.base_summary
    st.session_state["_pf_skills"]  = ", ".join(_pf0.skills)


def init_form_state():
    """Initialize form widget keys from the saved profile on first load."""
    if "_pf_name" not in st.session_state:
        seed_profile_keys()

    if "_edu_entries" not in st.session_state:
        _pf_init = st.session_state.profile
        st.session_state["_edu_entries"] = list(_pf_init.education) if _pf_init.education else [{}]

    if "_exp_entries" not in st.session_state:
        _pf_init = st.session_state.profile
        st.session_state["_exp_entries"] = list(_pf_init.experience) if _pf_init.experience else [{}]

    if "pref_role" not in st.session_state:
        _pf_prefs = st.session_state.profile
        st.session_state.pref_role = _pf_prefs.pref_role or "Software Engineer"

    if "pref_location" not in st.session_state:
        _pf_prefs = st.session_state.profile
        st.session_state.pref_location = _pf_prefs.pref_location or "Remote"

    if "kanban_page" not in st.session_state:
        st.session_state.kanban_page = 0


def init_ai_stack(user_id: int):
    """Initialize the sentence-transformer model, AI tailor, and PDF generator.

    These are expensive to create so they are only initialized once per session.
    """
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
        _ledger_content = run_async(st.session_state.repo.get_ledger(user_id))
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


def init_resume_cache(user_id: int):
    """Cache resume text for match scoring (avoids re-reading DB every rerun)."""
    if "resume_text_cache" not in st.session_state:
        from src.core.ai import _parse_ledger_as_resume
        _ledger_content_for_cache = run_async(st.session_state.repo.get_ledger(user_id))
        if _ledger_content_for_cache:
            st.session_state.resume_text_cache = _parse_ledger_as_resume(content=_ledger_content_for_cache)
        else:
            # Fallback to file for first-run before any ledger saved
            _lp_match = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ledger.md")
            st.session_state.resume_text_cache = _parse_ledger_as_resume(_lp_match) if os.path.exists(_lp_match) else ""
        # Also cache raw ledger so other pages can read it without an extra DB round-trip
        st.session_state["_ledger_raw"] = _ledger_content_for_cache or ""

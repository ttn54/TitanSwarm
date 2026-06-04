"""
Preferences page — user profile, daemon config, GitHub enrichment, resume upload.

The most complex page in the application, handling:
- Identity (name, email, phone, github, linkedin, website)
- Context Ledger (professional summary, skills)
- Job Preferences (role, location, work mode, job type)
- Daemon Config (scraper roles/locations/interval)
- GitHub Context refresh
- Resume PDF upload + auto-fill
- Education entries
- Work Experience entries
"""
from __future__ import annotations

import os
import re

import streamlit as st

from src.core.models import UserProfile
from src.core.ledger import LedgerManager
from src.core.env_writer import upsert_env_vars, read_env_var
from src.ui.components import (
    run_async, profile_completion, build_manual_ledger_section,
)
from src.ui.state import seed_profile_keys


def render(repo, profile: UserProfile, tailor, user_id: int, prev_on_prefs: bool):
    """Render the complete Preferences page."""
    # Re-seed form keys from saved profile when navigating TO this page.
    if not prev_on_prefs:
        seed_profile_keys()
        _pf_seed = st.session_state.profile
        st.session_state["_edu_entries"] = list(_pf_seed.education) if _pf_seed.education else [{}]
        st.session_state["_exp_entries"] = list(_pf_seed.experience) if _pf_seed.experience else [{}]

    # Flush any pending autofill values BEFORE any keyed widget is instantiated.
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
        _render_identity_section()
        _render_context_ledger_section()
        _render_save_profile_button(repo, user_id)

    with pc2:
        _render_job_preferences(repo, profile, user_id)
        _render_daemon_config()
        _render_github_context(repo, tailor, user_id)
        _render_resume_upload(repo, tailor, profile, user_id)

    _render_education_section()
    _render_experience_section()
    _render_save_edu_exp_button(repo, tailor, user_id)


# ── Sub-renderers ──────────────────────────────────────────────────────────


def _render_identity_section():
    st.markdown("<br>", unsafe_allow_html=True)
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


def _render_context_ledger_section():
    st.markdown("<br>", unsafe_allow_html=True)
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


def _render_save_profile_button(repo, user_id):
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
        _save_ok = run_async(repo.save_profile(_saved_profile, user_id=user_id))
        if _save_ok:
            st.session_state.profile = _saved_profile
            st.toast("Profile saved!", icon="🔒")
        else:
            st.error("Profile save failed — please try again.")
        st.rerun()


def _render_job_preferences(repo, profile, user_id):
    with st.container(border=True):
        st.markdown('<div class="profile-card-title">Job Preferences</div>', unsafe_allow_html=True)
        ROLE_OPTIONS = [
            "Software Engineer", "Software Engineer Intern",
            "Machine Learning Engineer", "Backend Engineer",
            "Frontend Engineer", "Data Engineer", "Other",
        ]
        pref_role = st.selectbox(
            "Target Role", options=ROLE_OPTIONS,
            index=ROLE_OPTIONS.index(st.session_state.pref_role)
            if st.session_state.pref_role in ROLE_OPTIONS else 0,
        )
        pref_loc = st.text_input("Preferred Location", value=st.session_state.pref_location,
                                  placeholder="Remote · Vancouver · San Francisco")
        work_mode = st.multiselect("Work Mode", ["Remote", "Hybrid", "On-site"], default=["Remote", "Hybrid"])
        job_type = st.multiselect("Job Type", ["Internship / Co-op", "Full-time", "Contract"], default=["Internship / Co-op"])

        if st.button("Save Preferences", type="primary", use_container_width=True):
            st.session_state.pref_role     = pref_role
            st.session_state.pref_location = pref_loc
            _cur_pf = st.session_state.profile
            _saved_pf = _cur_pf.model_copy(update={"pref_role": pref_role, "pref_location": pref_loc})
            st.session_state.profile = _saved_pf
            run_async(repo.save_profile(_saved_pf, user_id=user_id))
            st.toast("Preferences saved!", icon="✅")
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)


def _render_daemon_config():
    with st.container(border=True):
        st.markdown('<div class="profile-card-title">Daemon Config</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">Configure which roles and locations the background scraper targets. Uses <code>|</code> to separate values internally.</div>', unsafe_allow_html=True)

        _env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        _cur_roles = read_env_var(_env_path, "SCRAPER_ROLES",
            read_env_var(_env_path, "SCRAPER_ROLE", "Software Engineer Intern"))
        _cur_locs  = read_env_var(_env_path, "SCRAPER_LOCATIONS",
            read_env_var(_env_path, "SCRAPER_LOCATION", "Vancouver, BC"))
        _cur_interval = read_env_var(_env_path, "SCRAPER_INTERVAL_HOURS", "12")
        _cur_results  = read_env_var(_env_path, "SCRAPER_RESULTS_WANTED", "25")

        _roles_default  = "\n".join(r.strip() for r in _cur_roles.split("|")  if r.strip())
        _locs_default   = "\n".join(l.strip() for l in _cur_locs.split("|")   if l.strip())

        _daemon_roles = st.text_area("Roles to search (one per line)", value=_roles_default, height=100, key="_daemon_roles")
        _daemon_locs = st.text_area("Locations (one per line)", value=_locs_default, height=100, key="_daemon_locs")
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


def _render_github_context(repo, tailor, user_id):
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
                    _cur_ledger_gh = run_async(repo.get_ledger(user_id)) or ""
                    _gh_marker = "## GitHub Projects:"
                    _resume_marker = "## Imported Resume:"
                    _resume_block = ""
                    if _resume_marker in _cur_ledger_gh:
                        _resume_block = "\n\n" + _resume_marker + _cur_ledger_gh.split(_resume_marker, 1)[1].rstrip()
                    _gh_base = _cur_ledger_gh
                    if _gh_marker in _gh_base:
                        _gh_base = _gh_base.split(_gh_marker)[0]
                    if _resume_marker in _gh_base:
                        _gh_base = _gh_base.split(_resume_marker)[0]
                    _gh_base = _gh_base.rstrip()
                    _new_gh_ledger = _gh_base + f"\n\n{_gh_marker}\n\n{_gh_text}" + _resume_block
                    run_async(repo.save_ledger(user_id, _new_gh_ledger))
                    if tailor:
                        _lm_gh = LedgerManager.from_content(_new_gh_ledger, db_path="data/faiss.index")
                        _lm_gh.model = st.session_state.st_model
                        _lm_gh.build_index()
                        st.session_state.tailor.ledger = _lm_gh
                    _invalidate_caches()
                    st.toast("GitHub projects refreshed!", icon="🐙")
                    st.rerun()
                else:
                    st.warning("Could not fetch repos — check your GitHub username or try again later.")

    st.markdown("<br>", unsafe_allow_html=True)


def _render_resume_upload(repo, tailor, profile, user_id):
    with st.container(border=True):
        st.markdown('<div class="profile-card-title">Base Resume</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">Upload your PDF resume — text is extracted and added to the AI\'s fact ledger.</div>', unsafe_allow_html=True)
        _saved_ledger_for_badge = run_async(repo.get_ledger(user_id))
        _resume_marker = "## Imported Resume:"
        if _saved_ledger_for_badge and _resume_marker in _saved_ledger_for_badge:
            _saved_fname = _saved_ledger_for_badge.split(_resume_marker)[1].split("\n")[0].strip()
            st.success(f"✅ Resume on file: **{_saved_fname}**  — upload a new one to replace it.")
        else:
            st.info("No resume uploaded yet.")
        uploaded = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded and st.button("📥 Ingest Resume into Ledger", use_container_width=True):
            # ── Size + format validation ──────────────────────────────────
            MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB
            if uploaded.size > MAX_PDF_BYTES:
                st.error(f"File too large ({uploaded.size / 1024 / 1024:.1f} MB). Maximum is 10 MB.")
            elif uploaded.size < 4:
                st.error("File is empty or too small to be a valid PDF.")
            else:
                _first_bytes = uploaded.read(4)
                uploaded.seek(0)  # reset for pdfplumber
                if not _first_bytes.startswith(b'%PDF'):
                    st.error("Not a valid PDF file. Please upload a real PDF resume.")
                else:
                    try:
                        import pdfplumber, io
                        with pdfplumber.open(io.BytesIO(uploaded.read())) as pdf:
                            text = "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
                        if not text:
                            st.error("Could not extract text from this PDF. Make sure it is not a scanned image.")
                        else:
                            lines = [l.strip() for l in text.splitlines() if l.strip()]
                            email_m    = re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', text, re.IGNORECASE)
                            phone_m    = re.search(r'(\+?1[\s.-])?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}', text)
                            github_m   = re.search(r'github\.com/([\w-]+)', text, re.IGNORECASE)
                            linkedin_m = re.search(r'linkedin\.com/in/([\w-]+)', text, re.IGNORECASE)
                            pf_cur = st.session_state.profile
                            new_name     = (lines[0] if lines else "") or pf_cur.name
                            new_email    = (email_m.group(0)    if email_m    else "") or pf_cur.email
                            new_phone    = (phone_m.group(0)    if phone_m    else "") or pf_cur.phone
                            new_github   = (f"github.com/{github_m.group(1)}"   if github_m   else "") or ""
                            new_linkedin = (f"linkedin.com/in/{linkedin_m.group(1)}" if linkedin_m else "") or ""
                            st.session_state["_pf_pending"] = {
                                "_pf_name":     new_name,
                                "_pf_email":    new_email,
                                "_pf_phone":    new_phone,
                                "_pf_github":   new_github,
                                "_pf_linkedin": new_linkedin,
                            }
                            _upload_profile = UserProfile(
                                name=new_name, email=new_email, phone=new_phone,
                                github=new_github, linkedin=new_linkedin,
                                base_summary=pf_cur.base_summary,
                                skills=pf_cur.skills,
                                pref_role=pf_cur.pref_role,
                                pref_location=pf_cur.pref_location,
                            )
                            st.session_state.profile = _upload_profile
                            run_async(repo.save_profile(_upload_profile, user_id=user_id))
                            _existing_ledger = run_async(repo.get_ledger(user_id))
                            _marker = "## Imported Resume:"
                            _base = _existing_ledger.split(_marker)[0].rstrip() if _existing_ledger else ""
                            # ═══ Strip legacy '## Technical Skills' only ═══
                            _legacy_marker = "## Technical Skills"
                            if _legacy_marker in _base:
                                _base = _base.split(_legacy_marker)[0]
                            _base = _base.rstrip()
                            # Always include Manual Profile if the user explicitly saved one.
                            _mp_block = ""
                            _mp_marker = "## Manual Profile:"
                            if _mp_marker in _existing_ledger:
                                _mp_block = "\n\n" + _mp_marker + _existing_ledger.split(_mp_marker, 1)[1].split("\n## ")[0].rstrip()
                            _new_ledger = _base + _mp_block + f"\n\n{_marker} {uploaded.name}\n\n{text}"
                            run_async(repo.save_ledger(user_id, _new_ledger))
                            if tailor:
                                _lm_new = LedgerManager.from_content(_new_ledger, db_path="data/faiss.index")
                                _lm_new.model = st.session_state.st_model
                                _lm_new.build_index()
                                st.session_state.tailor.ledger = _lm_new
                            _invalidate_caches()
                            st.toast(f"{uploaded.name} ingested ✓  Profile fields auto-filled above.", icon="✅")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Resume ingestion failed: {e}")


def _render_education_section():
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="profile-card-title">Education</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">Added here, your degrees appear in every generated resume PDF.</div>', unsafe_allow_html=True)
        _edu_list = st.session_state.get("_edu_entries", [{}])
        for _ei, _edu in enumerate(_edu_list):
            with st.expander(
                _edu.get("degree") or f"Degree {_ei + 1}",
                expanded=not bool(_edu.get("degree"))
            ):
                _ec1, _ec2 = st.columns(2)
                with _ec1:
                    st.text_input("Degree / Programme", value=_edu.get("degree", ""), placeholder="BSc Computer Science", key=f"_edu_degree_{_ei}")
                    st.text_input("Start Date", value=_edu.get("start_date", ""), placeholder="Sep 2022", key=f"_edu_start_{_ei}")
                with _ec2:
                    st.text_input("Institution", value=_edu.get("institution", ""), placeholder="University of British Columbia", key=f"_edu_inst_{_ei}")
                    st.text_input("End Date", value=_edu.get("end_date", ""), placeholder="Apr 2026 or Present", key=f"_edu_end_{_ei}")
                st.text_input("Location (optional)", value=_edu.get("location", ""), placeholder="Vancouver, BC", key=f"_edu_loc_{_ei}")
                if st.button("🗑 Remove", key=f"_edu_rm_{_ei}", use_container_width=False):
                    st.session_state["_edu_entries"].pop(_ei)
                    st.rerun()
        if st.button("➕ Add Degree", use_container_width=False):
            st.session_state["_edu_entries"].append({})
            st.rerun()


def _render_experience_section():
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="profile-card-title">Work Experience</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.8rem;color:#64748b;margin-bottom:0.75rem;">Added here, your roles and bullet points appear in every generated resume PDF.</div>', unsafe_allow_html=True)
        _exp_list = st.session_state.get("_exp_entries", [{}])
        for _xi, _exp in enumerate(_exp_list):
            with st.expander(
                ((_exp.get("title") or "") + (" @ " + _exp.get("company", "") if _exp.get("company") else "")) or f"Role {_xi + 1}",
                expanded=not bool(_exp.get("title"))
            ):
                _xc1, _xc2 = st.columns(2)
                with _xc1:
                    st.text_input("Job Title", value=_exp.get("title", ""), placeholder="Software Engineer Intern", key=f"_exp_title_{_xi}")
                    st.text_input("Start Date", value=_exp.get("start_date", ""), placeholder="May 2025", key=f"_exp_start_{_xi}")
                with _xc2:
                    st.text_input("Company", value=_exp.get("company", ""), placeholder="Shopify", key=f"_exp_company_{_xi}")
                    st.text_input("End Date", value=_exp.get("end_date", "Present"), placeholder="Aug 2025 or Present", key=f"_exp_end_{_xi}")
                st.text_input("Location (optional)", value=_exp.get("location", ""), placeholder="Vancouver, BC or Remote", key=f"_exp_loc_{_xi}")
                st.text_area("Bullet Points (one per line)",
                    value="\n".join(_exp.get("bullets", [])),
                    placeholder="• Reduced deploy time by 40% with automated CI/CD pipelines.",
                    height=110, key=f"_exp_bullets_{_xi}")
                if st.button("🗑 Remove", key=f"_exp_rm_{_xi}", use_container_width=False):
                    st.session_state["_exp_entries"].pop(_xi)
                    st.rerun()
        if st.button("➕ Add Role", use_container_width=False):
            st.session_state["_exp_entries"].append({})
            st.rerun()


def _render_save_edu_exp_button(repo, tailor, user_id):
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾  Save Education & Experience", type="primary", use_container_width=True):
        _new_edu: list[dict] = []
        for _ei in range(len(st.session_state.get("_edu_entries", []))):
            _d = st.session_state.get(f"_edu_degree_{_ei}", "").strip()
            _i = st.session_state.get(f"_edu_inst_{_ei}", "").strip()
            if _d or _i:
                _new_edu.append({
                    "degree": _d, "institution": _i,
                    "start_date": st.session_state.get(f"_edu_start_{_ei}", "").strip(),
                    "end_date":   st.session_state.get(f"_edu_end_{_ei}", "").strip(),
                    "location":   st.session_state.get(f"_edu_loc_{_ei}", "").strip(),
                    "bullets":    [],
                })

        _new_exp: list[dict] = []
        for _xi in range(len(st.session_state.get("_exp_entries", []))):
            _t = st.session_state.get(f"_exp_title_{_xi}", "").strip()
            _c = st.session_state.get(f"_exp_company_{_xi}", "").strip()
            if _t or _c:
                _bullets_raw = st.session_state.get(f"_exp_bullets_{_xi}", "")
                _bullets = [b.lstrip("•").strip() for b in _bullets_raw.splitlines() if b.strip()]
                _new_exp.append({
                    "title": _t, "company": _c,
                    "start_date": st.session_state.get(f"_exp_start_{_xi}", "").strip(),
                    "end_date":   st.session_state.get(f"_exp_end_{_xi}", "Present").strip(),
                    "location":   st.session_state.get(f"_exp_loc_{_xi}", "").strip(),
                    "bullets":    _bullets,
                })

        _cur_pf2 = st.session_state.profile
        _saved_pf2 = _cur_pf2.model_copy(update={"education": _new_edu, "experience": _new_exp})
        _save_ok2 = run_async(repo.save_profile(_saved_pf2, user_id=user_id))
        if _save_ok2:
            st.session_state.profile = _saved_pf2
            st.session_state["_edu_entries"] = _new_edu if _new_edu else [{}]
            st.session_state["_exp_entries"] = _new_exp if _new_exp else [{}]
            _manual_block = build_manual_ledger_section(_new_edu, _new_exp)
            if _manual_block:
                _cur_ledger_m = run_async(repo.get_ledger(user_id))
                _m_marker = "## Manual Profile:"
                _base_m = _cur_ledger_m.split(_m_marker)[0].rstrip() if _cur_ledger_m else ""
                # Strip legacy sections from other users (same guard as resume upload).
                for _bad_marker in ("## GitHub Projects:", "## Technical Skills"):
                    if _bad_marker in _base_m:
                        _base_m = _base_m.split(_bad_marker)[0]
                _base_m = _base_m.rstrip()
                _new_ledger_m = _base_m + f"\n\n{_m_marker}\n\n{_manual_block}"
                run_async(repo.save_ledger(user_id, _new_ledger_m))
                if tailor:
                    _lm_m = LedgerManager.from_content(_new_ledger_m, db_path="data/faiss.index")
                    _lm_m.model = st.session_state.st_model
                    _lm_m.build_index()
                    st.session_state.tailor.ledger = _lm_m
                _invalidate_caches()
            st.toast("Education & Experience saved!", icon="🎓")
        else:
            st.error("Save failed — please try again.")
        st.rerun()


def _invalidate_caches():
    """Clear all caches that depend on ledger content."""
    st.session_state.pop("resume_text_cache", None)
    st.session_state.pop("_match_score_key", None)
    st.session_state.pop("_ledger_raw", None)
    st.session_state.pop("_tailored_cache_key", None)

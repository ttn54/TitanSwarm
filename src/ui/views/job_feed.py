"""
Job Feed page — the primary discovery and tailoring interface.

Renders the job search bar, KPI strip, filter chips, job cards with
tailor/download/cover-letter actions, and match scoring.
"""
from __future__ import annotations

import asyncio
import os
import time
import html as _html
import base64 as _b64

import streamlit as st

from src.core.models import Job, JobStatus, TailoredApplication, UserProfile, format_salary
from src.core.matching import compute_match_score
from src.ui.components import (
    run_async, filter_jobs, filter_by_date, search_jobs,
    badge, avatar_html, merge_structured, parse_ledger_for_pdf,
    run_discovery, _FNAME_SANITIZE_RE, profile_completion,
)


def render(repo, profile: UserProfile, tailor, pdf_gen, st_model, user_id: int):
    """Render the complete Job Feed page."""

    # ── Top header ──
    hc, bc = st.columns([4, 1])
    with hc:
        st.markdown('<div class="main-header">Job Feed</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="main-subheader">Showing opportunities for <strong>{st.session_state.pref_role}</strong> · {st.session_state.pref_location}</div>', unsafe_allow_html=True)
        _feed_ledger = st.session_state.get("_ledger_raw", "")
        if _feed_ledger and "## Imported Resume:" in _feed_ledger:
            _feed_resume_name = _feed_ledger.split("## Imported Resume:")[1].split("\n")[0].strip()
            st.caption(f"📄 Resume loaded: {_feed_resume_name}")
        else:
            st.caption("⚠️ No resume uploaded — go to Preferences → Base Resume to upload one for AI match scoring.")

    # ── KPI strip ──
    _total = run_async(repo.count_all(user_id=user_id))
    async def _kpi_counts():
        _pend, _subm, _disc = await asyncio.gather(
            repo.get_jobs_by_status(JobStatus.PENDING_REVIEW, user_id=user_id),
            repo.get_jobs_by_status(JobStatus.SUBMITTED, user_id=user_id),
            repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=user_id),
        )
        return len(_pend), len(_subm), len(_disc)
    n_pending, n_submitted, n_discovered = run_async(_kpi_counts())

    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    _n_interview_feed = len(run_async(repo.get_jobs_by_status(JobStatus.INTERVIEW, user_id=user_id)))
    kpi_data = [
        (_total,       "Total Sourced",  f"+{n_discovered} new"),
        (n_pending,   "Pending Review", "Needs action"),
        (n_submitted, "Applications",   "Sent"),
        (_n_interview_feed, "Interviews", "Real data"),
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
            _LOC_SUGGESTIONS = [
                "Remote", "Vancouver, BC", "Toronto, ON", "Calgary, AB",
                "Edmonton, AB", "Ottawa, ON", "Montreal, QC", "Waterloo, ON",
                "Victoria, BC", "Seattle, WA", "San Francisco, CA",
                "New York, NY", "Austin, TX", "Boston, MA",
                "Los Angeles, CA", "London, UK", "Singapore",
            ]
            _loc_pref = st.session_state.get("pref_location", "Vancouver, BC")
            _loc_opts = list(_LOC_SUGGESTIONS)
            if _loc_pref and _loc_pref not in _loc_opts:
                _loc_opts.insert(0, _loc_pref)
            _loc_idx = _loc_opts.index(_loc_pref) if _loc_pref in _loc_opts else 0
            search_loc = st.selectbox(
                "Location", options=_loc_opts, index=_loc_idx,
                label_visibility="collapsed",
            )
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
            found_ids = run_async(run_discovery(repo, search_role, search_loc, 50, user_id=user_id))
            st.session_state.feed_job_ids = found_ids
            st.write(f"✅  **{len(found_ids)} roles** found for this search.")
            s.update(label=f"Done — {len(found_ids)} jobs in feed.", state="complete")
        st.toast(f"{len(found_ids)} opportunities loaded!", icon="⚡")
        st.rerun()

    # ── Filter chips ──
    if "filter_chip" not in st.session_state:
        st.session_state.filter_chip = "All"
    selected_chip = st.pills(
        "Filter",
        options=["All", "Remote", "Internship", "Full-time", "Co-op"],
        key="filter_chip",
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
    _feed_ids: list[str] = st.session_state.get("feed_job_ids", [])
    async def _fetch_feed():
        _disc, _pend = await asyncio.gather(
            repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=user_id),
            repo.get_jobs_by_status(JobStatus.PENDING_REVIEW, user_id=user_id),
        )
        return _disc + _pend
    _all_repo_jobs = run_async(_fetch_feed())
    if _feed_ids:
        _id_set = set(_feed_ids)
        _raw_jobs = [j for j in _all_repo_jobs if j.id in _id_set]
    else:
        _raw_jobs = _all_repo_jobs
    all_jobs = filter_jobs(_raw_jobs, selected_chip)
    all_jobs = filter_by_date(all_jobs, _date_opt)
    all_jobs = search_jobs(all_jobs, _search_q)

    # Compute match scores — cached by job-list fingerprint
    _resume_cache = st.session_state.resume_text_cache
    _all_ids_key = frozenset(j.id for j in _all_repo_jobs)
    if st.session_state.get("_match_score_key") != _all_ids_key:
        st.session_state["_match_score_cache"] = {
            j.id: compute_match_score(_resume_cache, j.job_description, st_model)
            for j in _all_repo_jobs
        }
        st.session_state["_match_score_key"] = _all_ids_key
    _match_scores = st.session_state["_match_score_cache"]

    # Batch-load all tailored results
    if st.session_state.get("_tailored_cache_key") != _all_ids_key:
        async def _batch_tailored(_jobs):
            _results = await asyncio.gather(
                *[repo.get_tailored_result(j.id, user_id=user_id) for j in _jobs],
                return_exceptions=True,
            )
            return {j.id: (r if r and not isinstance(r, Exception) else None)
                    for j, r in zip(_jobs, _results)}
        st.session_state["_tailored_results_cache"] = run_async(_batch_tailored(_all_repo_jobs))
        st.session_state["_tailored_cache_key"] = _all_ids_key

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
            _render_job_card(job, repo, profile, tailor, pdf_gen, _match_scores, user_id)


def _render_job_card(job: Job, repo, profile, tailor, pdf_gen, _match_scores, user_id: int):
    """Render a single job card with all its action buttons."""
    skills_html = "".join(f'<span class="skill-pill">{s}</span>' for s in (job.required_skills or [])[:5])
    import textwrap as _tw
    _raw = job.job_description.strip()
    desc = _html.escape(_tw.shorten(_raw, width=180, placeholder="…")) if len(_raw) > 180 else _html.escape(_raw)
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
                        {' '.join(filter(None, [
                            f"📍 {job.location} &nbsp;·&nbsp;" if job.location else "",
                            f"🕐 {job.date_posted} &nbsp;·&nbsp;" if job.date_posted else "",
                            f"💰 {format_salary(job)} &nbsp;·&nbsp;" if format_salary(job) else "💰 No salary posted &nbsp;·&nbsp;",
                            f'🔗 <a href="{job.url}" target="_blank" style="color:#6366f1;text-decoration:none;">{job.url[:60]}…</a>'
                        ]))}
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

            _dl_fname = (f"{_FNAME_SANITIZE_RE.sub('', job.company).strip().replace(' ', '_')}_"
                         f"{_FNAME_SANITIZE_RE.sub('', job.role).strip().replace(' ', '_')}_Resume.pdf")

            if st.button("📄 Tailor Resume", key=f"apply_{job.id}", type="primary", use_container_width=True):
                _handle_tailor(job, repo, profile, tailor, pdf_gen, err_key, _dl_fname, user_id)

            # Show download button if PDF is already generated for this job
            if f"pdf_{job.id}" not in st.session_state:
                _db_result = st.session_state.get("_tailored_results_cache", {}).get(job.id)
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
                _b64_pdf = _b64.b64encode(st.session_state[f"pdf_{job.id}"]).decode()
                _auto = st.session_state.pop(f"autodownload_{job.id}", False)
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
                _gaps = st.session_state.get(f"gaps_{job.id}", [])
                if _gaps:
                    with st.expander(f"Skill Gaps ({len(_gaps)})", expanded=False):
                        st.caption("These skills appear in the JD but are not in your ledger. Consider adding them.")
                        for _g in _gaps:
                            st.markdown(f"- {_g}")

            if st.button("Skip", key=f"skip_{job.id}", use_container_width=True):
                run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=user_id))
                st.rerun()

            # Cover letter button
            _has_pdf = f"pdf_{job.id}" in st.session_state
            if _has_pdf:
                _render_cover_letter_section(job, repo, profile, tailor, pdf_gen, user_id)
            else:
                st.button(
                    "✉️ Cover Letter", key=f"cl_{job.id}_disabled",
                    use_container_width=True, disabled=True,
                    help="Tailor your resume first to unlock the cover letter.",
                )

        with st.expander("View full description, Q&A & Cover Letter"):
            st.write(job.job_description)
            if f"qa_{job.id}" in st.session_state:
                qa = st.session_state[f"qa_{job.id}"]
                if qa:
                    st.markdown("---")
                    st.markdown("**📋 Application Q&A Answers**")
                    for question, answer in qa.items():
                        st.markdown(f"**Q: {question}**")
                        st.info(answer)
            if f"cl_{job.id}" in st.session_state:
                st.markdown("---")
                st.markdown("**✉️ Cover Letter**")
                _cl_body = st.session_state[f"cl_{job.id}"]
                _cl_display = _cl_body.body if hasattr(_cl_body, "body") else _cl_body
                st.text_area(
                    "Cover letter body (copy from here)",
                    value=_cl_display, height=250,
                    key=f"cl_display_{job.id}",
                )
            if st.button("✅ Mark as Applied", key=f"mark_{job.id}"):
                run_async(repo.update_status(job.id, JobStatus.SUBMITTED, user_id=user_id))
                st.toast(f"{job.company} marked as submitted!", icon="🎯")
                st.rerun()


def _handle_tailor(job, repo, profile, tailor, pdf_gen, err_key, _dl_fname, user_id):
    """Handle the Tailor Resume button click."""
    if tailor is None:
        st.session_state[err_key] = (
            "AI engine is not configured. "
            "Make sure GEMINI_API_KEY (or OPENAI_API_KEY) is set in your .env file."
        )
        st.rerun()
    if not job.job_description.strip():
        st.session_state[err_key] = (
            "This job has no description available. "
            "Visit the job URL, copy the full description, and paste it into the job card to enable tailoring."
        )
        st.rerun()
    _db_ledger_content = st.session_state.get("_ledger_raw", "")
    with st.spinner(f"Tailoring resume for {job.company}… (may retry if Gemini is busy)"):
        try:
            result: TailoredApplication = run_async(tailor.tailor_application(job))
            if _db_ledger_content:
                _structured = parse_ledger_for_pdf(content=_db_ledger_content)
            else:
                # No ledger saved for this user yet — rely on profile fields only.
                _structured = {"education": [], "experience": []}
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
                "education":  merge_structured(_pi.education, _structured["education"]),
                "experience": merge_structured(_pi.experience, _structured["experience"]),
            }
            output_path = os.path.join("output", _dl_fname)
            os.makedirs("output", exist_ok=True)
            run_async(pdf_gen.generate_resume_pdf(user_ledger, result, output_path=output_path))
            with open(output_path, "rb") as fh:
                pdf_bytes = fh.read()
            st.session_state[f"pdf_{job.id}"] = pdf_bytes
            st.session_state[f"qa_{job.id}"]  = result.q_and_a_responses
            st.session_state[f"gaps_{job.id}"] = result.missing_skills
            st.session_state[f"autodownload_{job.id}"] = True
            run_async(repo.save_tailored_result(
                job.id, result.model_dump_json(), pdf_bytes, user_id=user_id
            ))
            st.session_state.pop("_tailored_results_cache", None)
            st.session_state.pop("_tailored_cache_key", None)
            run_async(repo.update_status(job.id, JobStatus.PENDING_REVIEW, user_id=user_id))
            st.toast(f"Resume for {job.company} is ready!", icon="✅")
            st.rerun()
        except Exception as e:
            import traceback
            st.session_state[err_key] = f"Tailoring failed: {e}\n\n{traceback.format_exc()}"
            st.rerun()


def _render_cover_letter_section(job, repo, profile, tailor, pdf_gen, user_id):
    """Render cover letter generation button and download."""
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
                        _cl_result = run_async(tailor.generate_cover_letter(job))
                        st.session_state[f"cl_{job.id}"] = _cl_result
                        _cl_output = f"output/cover_letter_{job.id[:8]}.pdf"
                        _cl_pdf = run_async(pdf_gen.generate_cover_letter_pdf(
                            profile=profile,
                            company=job.company,
                            role=job.role,
                            cover_letter=_cl_result,
                            output_path=_cl_output,
                        ))
                        st.session_state[f"cl_pdf_{job.id}"] = _cl_pdf
                        run_async(repo.save_tailored_result(
                            job.id,
                            st.session_state.get(f"qa_{job.id}", "{}"),
                            st.session_state[f"pdf_{job.id}"],
                            cover_letter=_cl_result.body,
                            user_id=user_id,
                        ))
                        st.rerun()
                    except Exception as e:
                        st.session_state[_cl_err_key] = f"Cover letter failed: {e}"
                        st.rerun()
    if f"cl_pdf_{job.id}" in st.session_state:
        st.download_button(
            label="⬇️ Download Cover Letter PDF",
            data=st.session_state[f"cl_pdf_{job.id}"],
            file_name=f"cover_letter_{job.company.replace(' ', '_')}.pdf",
            mime="application/pdf",
            key=f"cl_dl_{job.id}",
            use_container_width=True,
        )

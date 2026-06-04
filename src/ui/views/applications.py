"""
My Applications page — Kanban board for tracking job application pipeline.

Renders a 4-column Kanban board (Pending Review → Applied → Interview → Rejected)
with status transition buttons and a submitted-jobs download section.
"""
from __future__ import annotations

import asyncio

import streamlit as st

from src.core.models import JobStatus
from src.ui.components import run_async, avatar_html


def render(repo, user_id: int):
    """Render the complete My Applications (Kanban) page."""
    st.markdown('<div class="main-header">My Applications</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subheader">Track every opportunity across your pipeline.</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Fetch all buckets concurrently using asyncio.gather
    async def fetch_all_buckets():
        return await asyncio.gather(
            repo.get_jobs_by_status(JobStatus.PENDING_REVIEW, user_id=user_id),
            repo.get_jobs_by_status(JobStatus.SUBMITTED, user_id=user_id),
            repo.get_jobs_by_status(JobStatus.INTERVIEW, user_id=user_id),
            repo.get_jobs_by_status(JobStatus.REJECTED, user_id=user_id),
        )

    _pr, _app, _int, _rej = run_async(fetch_all_buckets())

    buckets = {
        "Pending Review": _pr,
        "Applied":        _app,
        "Interview":      _int,
        "Rejected":       _rej,
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
                Head to <strong>Job Feed</strong> and hit 📄 Tailor Resume on a role to get started.
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
                    for job in jobs:
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
                                    run_async(repo.update_status(job.id, JobStatus.SUBMITTED, user_id=user_id))
                                    st.rerun()
                            with bc2:
                                if st.button("↩ Return", key=f"kanban_ret_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.DISCOVERED, user_id=user_id))
                                    st.rerun()
                            with bc3:
                                if st.button("✗ Reject", key=f"kanban_rej_pr_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=user_id))
                                    st.rerun()

                        elif lane_name == "Applied":
                            bc1, bc2 = st.columns(2)
                            with bc1:
                                if st.button("🎤 Interview", key=f"kanban_int_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.INTERVIEW, user_id=user_id))
                                    st.rerun()
                            with bc2:
                                if st.button("✗ Reject", key=f"kanban_rej_ap_{job.id}", use_container_width=True):
                                    run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=user_id))
                                    st.rerun()

                        elif lane_name == "Interview":
                            if st.button("✗ Reject", key=f"kanban_rej_iv_{job.id}", use_container_width=True):
                                run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=user_id))
                                st.rerun()

                        elif lane_name == "Rejected":
                            if st.button("↩ Restore", key=f"kanban_restore_{job.id}", use_container_width=True):
                                run_async(repo.update_status(job.id, JobStatus.DISCOVERED, user_id=user_id))
                                st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Submitted list with download ──
    submitted_jobs = _app
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
                    try:
                        _db_r = run_async(repo.get_tailored_result(job.id, user_id=user_id))
                    except Exception:
                        _db_r = None
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
                    run_async(repo.update_status(job.id, JobStatus.REJECTED, user_id=user_id))
                    st.rerun()

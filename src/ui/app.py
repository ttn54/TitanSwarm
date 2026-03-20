import streamlit as st
import asyncio
import sys
import os
import time
import random

# Ensure the root directory is on the path so we can import src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.models import Job, JobStatus, UserProfile
from src.ui.mock_repo import MockUIRepository
from uuid import uuid4

# ==========================================
# PAGE CONFIGURATION & THEMING
# ==========================================
st.set_page_config(page_title="TitanSwarm | Copilot", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# Inject Custom CSS for SaaS styling
st.markdown("""
    <style>
        /* Hide default Streamlit ornaments */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Dashboard Metric Cards */
        div[data-testid="metric-container"] {
            background-color: #1e293b;
            border: 1px solid #334155;
            padding: 5% 5% 5% 10%;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        
        /* Button Styling Overrides */
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
        
        /* Section Headers */
        h1, h2, h3 {
            font-family: 'Inter', sans-serif;
            letter-spacing: -0.025em;
        }
        
        hr {
            margin-top: 1rem;
            margin-bottom: 2rem;
            border: 0;
            border-top: 1px solid #334155;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# SESSION STATE & REPOSITORY INITIALIZATION
# ==========================================
if "repo" not in st.session_state:
    st.session_state.repo = MockUIRepository()
    st.session_state.repo.jobs = {} # Start empty for a fresh UI experience

if "profile" not in st.session_state:
    st.session_state.profile = UserProfile()

repo = st.session_state.repo
profile = st.session_state.profile

def run_async(coro):
    return asyncio.run(coro)

def update_job_status(job_id, status):
    run_async(repo.update_status(job_id, status))
    st.toast(f"Status updated to: {status.value}", icon="✅")

# Mock Swarm Generator (Pure UI/UX focus, bypassing jobspy totally)
async def mock_deploy_swarm(role, location, count):
    companies = ["Stripe", "Anthropic", "Scale AI", "Databricks", "Cloudflare", "Rippling"]
    found = []
    
    # Simulate network delay for UI feel
    await asyncio.sleep(1.5)
    
    for i in range(count):
        company = random.choice(companies)
        job = Job(
            id=str(uuid4()),
            role=role,
            company=company,
            url=f"https://{company.lower()}.com/careers/{random.randint(1000, 9999)}",
            status=JobStatus.PENDING_REVIEW, # Instantly put in review queue
            job_description=f"We are looking for a highly motivated {role} to join our core infrastructure team in {location}... (simulated description)",
        )
        await repo.save_job(job)
        found.append(job)
        
    return found

# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
with st.sidebar:
    st.markdown("## ⚡ Titan**Swarm**")
    st.markdown("---")
    
    menu_selection = st.radio(
        "Navigation",
        ["📊 Dashboard", "📂 The Vault", "🎯 Job Hunter UI"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### System Status")
    st.markdown("🟢 Base Registry: **Online**")
    st.markdown("🟢 Swarm Network: **Mock Engine**")
    st.markdown("🟢 RAG Tailor: **Standby**")

# ==========================================
# VIEW: DASHBOARD
# ==========================================
if menu_selection == "📊 Dashboard":
    st.title("Command Center")
    st.markdown("Welcome back. Here is the operational status of your autonomous swarm.")
    
    total_jobs = run_async(repo.count_all())
    pending_jobs = len(run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)))
    submitted_jobs = len(run_async(repo.get_jobs_by_status(JobStatus.SUBMITTED)))
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Opportunities Sourced", total_jobs, delta=f"+{total_jobs} this week" if total_jobs > 0 else None)
    col2.metric("Pending Review", pending_jobs, delta_color="off")
    col3.metric("Successfully Submitted", submitted_jobs, delta="Auto-Applied" if submitted_jobs > 0 else None)
    
    st.markdown("---")
    st.subheader("Recent Activity")
    if total_jobs == 0:
        st.info("No activity yet. Navigate to 'The Vault' to configure your profile, then use 'Job Hunter' to deploy the swarm.")
    else:
        all_pending = run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW))
        for j in all_pending[:3]: # Show top 3
            st.markdown(f"**{j.company}** - {j.role} `(Just Discovered)`")

# ==========================================
# VIEW: THE VAULT
# ==========================================
elif menu_selection == "📂 The Vault":
    st.title("The Context Vault")
    st.markdown("Upload your baseline resume. The Swarm will securely vector-encode this document to dynamically tailor your applications via the RAG pipeline.")
    
    uploaded_pdf = st.file_uploader("Drop your Base Resume (PDF)", type=["pdf"])
    if uploaded_pdf is not None:
        st.success(f"File **{uploaded_pdf.name}** successfully parsed and encoded into local FAISS Vector store.", icon="✅")
    
    st.markdown("---")
    st.subheader("Parsed Profile Ledger")
    st.markdown("Verify the extracted ground-truths. The AI uses this data strictly to prevent hallucinations.")
    
    with st.container(border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            profile.name = st.text_input("Full Legal Name", value=profile.name, placeholder="Jane Doe")
            profile.email = st.text_input("Primary Email", value=profile.email, placeholder="jane@example.com")
            profile.phone = st.text_input("Phone Number", value=profile.phone, placeholder="(555) 123-4567")
        with col_b:
            profile.github = st.text_input("GitHub URL", value=profile.github, placeholder="github.com/janedoe")
            profile.linkedin = st.text_input("LinkedIn URL", value=profile.linkedin, placeholder="linkedin.com/in/janedoe")
            
        profile.base_summary = st.text_area("Core Objective / Background", value=profile.base_summary, height=100)
        skills_csv = st.text_input("Hard Skills (Comma Separated)", value=",".join(profile.skills))
        profile.skills = [s.strip() for s in skills_csv.split(',')] if skills_csv else []
        
        if st.button("💾 Save Ledger to TitanStore", type="primary"):
            st.toast("Ledger successfully synchronized to database.", icon="🔒")

# ==========================================
# VIEW: JOB HUNTER UI (Search + Queue)
# ==========================================
elif menu_selection == "🎯 Job Hunter UI":
    st.title("Swarm Sourcing Engine")
    st.markdown("Configure your telemetry. The swarm will bypass Cloudflare protections to aggregate high-fidelity roles directly off primary platforms.")
    
    with st.container(border=True):
        col_job, col_loc = st.columns(2)
        with col_job:
            target_role = st.text_input("Target Role", "Machine Learning Engineer")
        with col_loc:
            target_location = st.text_input("Target Location", "San Francisco, CA (or Remote)")
            
        target_count = st.slider("Maximum Discovery Count", 1, 50, 10)
        
        if st.button("🚀 Deploy Autonomous Swarm", type="primary", use_container_width=True):
            with st.spinner("Initializing headless browsers & evading bot-detection..."):
                jobs = run_async(mock_deploy_swarm(target_role, target_location, target_count))
                st.session_state.repo = repo
            st.rerun() # Refresh to instantly show new jobs below

    st.markdown("---")
    st.title("Action & Dispatch Queue")
    
    pending_list = run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW))
    
    if not pending_list:
        st.info("Your queue is empty. Deploy the Swarm above to find opportunities.")
    else:
        # PAGINATION LOGIC
        jobs_per_page = 5
        total_pages = (len(pending_list) - 1) // jobs_per_page + 1
        
        if "current_page" not in st.session_state:
            st.session_state.current_page = 1
            
        st.write(f"**{len(pending_list)} Roles Pending Review**")
        
        # Paginate the list
        start_idx = (st.session_state.current_page - 1) * jobs_per_page
        end_idx = start_idx + jobs_per_page
        current_jobs = pending_list[start_idx:end_idx]
        
        for job in current_jobs:
            with st.container(border=True):
                col_info, col_actions = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"### {job.company}")
                    st.markdown(f"**{job.role}** | 📍 Location match | 🔗 [Original Source]({job.url})")
                    st.caption("Auto-Extracted Description Snippet:")
                    st.text(job.job_description[:150] + "...")
                
                with col_actions:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🧠 Tailor Application", key=f"tailor_{job.id}", type="primary", use_container_width=True):
                        with st.spinner("Compiling ATS-Optimized PDF using your Vault Ledger..."):
                            time.sleep(1) # Fake Generation Time
                            st.toast("PDF Generated Successfully", icon="🖨️")
                            
                    fake_pdf_bytes = b"%PDF-1.4 Mock PDF Stream"
                    st.download_button(
                        label="📄 Download PDF",
                        data=fake_pdf_bytes,
                        file_name=f"{job.company}_{profile.name or 'User'}_Resume.pdf",
                        mime="application/pdf",
                        key=f"dl_{job.id}",
                        use_container_width=True
                    )
                    
                    st.button(
                        "✅ Mark as Applied",
                        key=f"submit_{job.id}",
                        on_click=update_job_status,
                        args=(job.id, JobStatus.SUBMITTED),
                        use_container_width=True
                    )
                    
        # Pagination Controls
        if total_pages > 1:
            st.markdown("---")
            col_prev, col_page, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("⬅️ Previous " if st.session_state.current_page > 1 else " " * 10, disabled=st.session_state.current_page == 1):
                    st.session_state.current_page -= 1
                    st.rerun()
            with col_page:
                st.markdown(f"<p style='text-align: center;'>Page {st.session_state.current_page} of {total_pages}</p>", unsafe_allow_html=True)
            with col_next:
                if st.button("Next ➡️" if st.session_state.current_page < total_pages else " " * 10, disabled=st.session_state.current_page == total_pages):
                    st.session_state.current_page += 1
                    st.rerun()
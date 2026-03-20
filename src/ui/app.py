import streamlit as st
import asyncio
import sys
import os

# Ensure the root directory is on the path so we can import src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.models import JobStatus
from src.ui.mock_repo import MockUIRepository

# Page Config
st.set_page_config(page_title="TitanSwarm Dispatch", page_icon="🚀", layout="wide")

# Initialize the Mock Repo in Session State to prevent resetting on button clicks
if "repo" not in st.session_state:
    st.session_state.repo = MockUIRepository()

repo = st.session_state.repo

def run_async(coro):
    return asyncio.run(coro)

def update_job_status(job_id, status):
    run_async(repo.update_status(job_id, status))
    st.success(f"Job {job_id} marked as {status.name}!")

st.title("TitanSwarm Dispatch Terminal 🚀")

# Tabs
tab1, tab2 = st.tabs(["📊 Metrics", "📥 Action Queue"])

with tab1:
    st.header("System Overview")
    col1, col2, col3 = st.columns(3)
    
    total_jobs = run_async(repo.count_all())
    pending_jobs = len(run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW)))
    submitted_jobs = len(run_async(repo.get_jobs_by_status(JobStatus.SUBMITTED)))
    
    col1.metric("Total Jobs Scraped", total_jobs)
    col2.metric("Pending Review", pending_jobs)
    col3.metric("Successfully Submitted", submitted_jobs)

with tab2:
    st.header("Jobs Pending Action")
    
    pending_list = run_async(repo.get_jobs_by_status(JobStatus.PENDING_REVIEW))
    
    if not pending_list:
        st.info("No jobs pending review! The Swarm needs to scrape more data.")
    else:
        for job in pending_list:
            with st.expander(f"{job.role} at {job.company}"):
                col_left, col_right = st.columns([2, 1])
                
                with col_left:
                    st.markdown(f"**URL:** [Apply Here]({job.url})")
                    
                    # Mocking the AI generated summary and Q&A corresponding to the 'TailoredApplication' mapping
                    st.markdown("**AI Context Generation:**")
                    st.write(f"Tailored application bullet points matching {job.company}'s internal tech stack and constraints.")
                    
                    st.markdown("**AI Recommended Portal Answers:**")
                    st.json({"Are you legally authorized to work in the US?": "Yes", "Will you now or in the future require sponsorship?": "No"})
                
                with col_right:
                    # Mock PDF Download Button
                    fake_pdf_bytes = b"%PDF-1.4 Mock PDF Content"
                    st.download_button(
                        label="📄 Download Tailored PDF",
                        data=fake_pdf_bytes,
                        file_name=f"{job.company}_Resume.pdf",
                        mime="application/pdf",
                        key=f"dl_{job.id}"
                    )
                    
                    st.button(
                        "✅ Mark as Submitted",
                        key=f"submit_{job.id}",
                        on_click=update_job_status,
                        args=(job.id, JobStatus.SUBMITTED),
                        type="primary"
                    )
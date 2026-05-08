# Phase 4 Design: Dispatch Terminal (Streamlit UI)

## Architecture and Data Flow
- **Framework:** Streamlit (Single-Page Application using `st.tabs`).
- **Data Layer:** `MockUIRepository` that fulfills the `JobRepository` interface but runs completely in-memory. This acts as our temporary backend until the Go Raft application is fully online over port 6001.
- **State Management:** Overriding Streamlit's default re-run behavior using `st.session_state` to ensure the mock repository persists across button clicks.

## Interfaces and Data Structures
- Relies on the already existing `Job` Pydantic model (`src.core.models.Job`) and `JobStatus` enums.
- **Tab 1: Metrics:** Aggregates totals based on the `JobStatus`.
- **Tab 2: Action Queue:** Iterates through jobs where `status == JobStatus.PENDING_REVIEW`.

## Edge Cases Mitigated
- **Re-run wipes:** Caching the Mock DB inside `session_state` prevents it from emptying when a user clicks "Download PDF".
- **Empty Datasets:** Displaying graceful warnings ("No jobs pending review!") instead of crashing rendering loops.
- **Missing PDFs:** Mock logic to provide a raw bytes stream so browser download buttons don't `404` error if an ATS template hasn't successfully compiled. 

## TDD Plan
1. Create `tests/test_mock_ui_repo.py`
2. Assert initialization instantiates exactly 3 mock pending jobs and 1 submitted job.
3. Assert that calling `update_status()` shifts the job and reflects correctly in `get_jobs_by_status()`.
# Lazy Loading LinkedIn Descriptions Design
**Date:** 2026-04-23
**Status:** Under Review

## 1. The Core Architecture Problem
Currently, the UI sends `results_wanted=50` to JobSpy. 
Because `linkedin_fetch_description=True` is globally enabled in `worker.py`, JobSpy makes 1 massive search request, and then **50 individual HTTP requests** sequentially to fetch the full text for each LinkedIn job before returning the DataFrame to the UI.

This takes ~30–45 seconds, making the app feel frozen.

## 2. The Architecture Solution: Deferred (Lazy) Text Enrichment
Instead of fetching the full heavy text for ALL 50 jobs at discovery time (when you might only apply to 5 of them), we decouple discovery from enrichment.

1. **Discovery Phase (O(1) network calls):** We set `linkedin_fetch_description=False` in `SourcingEngine.run_sweep()`. JobSpy will fetch 50 jobs instantly (1–2 seconds) because it only grabs the metadata from the search page HTML (Title, URL, Company, Date).
2. **Tailoring Phase (JIT Heavy Fetch):** We modify `AITailor.tailor_application()`:
   - When the user clicks "📄 Tailor Resume" on a specific job, we intercept.
   - If the job's `job_description` is dangerously short (e.g., `< 100 characters`), we make a **single localized network call** using `async_playwright` (or a direct request) to fetch the full JD text *only for that one job*.
   - We update the database with the rich text, and then pass it to the RAG LLM.

## 3. Trade-offs
- **Pros:** The "Find Jobs" button becomes near-instant (fetching 50–100 jobs in ~2 seconds). You can scroll the feed immediately.
- **Cons:** Clicking "Tailor Resume" takes an extra ~1.5 seconds while it fetches the text just-in-time, but this is hidden behind the existing "Gemini is thinking..." loading spinner, so it feels organic.

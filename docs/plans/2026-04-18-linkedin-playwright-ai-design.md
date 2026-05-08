# LinkedIn Playwright & AI Parser Design

**Date:** 2026-04-18
**Phase:** Core Sourcing Engine & UI
**Status:** Approved

## 1. Architecture and Data Flow
- **Dependencies:** Playwright (already installed for PDF generation) and the existing AI providers (`google-genai` or `openai`).
- **Authentication:** `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` session cookies are passed to Playwright's browser context to verify human identity.
- **Scraping Layer (Headless Browser):** Uses `async_playwright` to open the URL, inject cookies, scroll down to load lazy-rendered sections (Experience/Education), and rip the raw `innerText` of the page.
- **AI Extraction Layer:** Passes the raw extracted text to the AI (Gemini/OpenAI) using a strict system prompt to structure it into the required JSON array of `Experience` and `Education`.
- **Repository Integration:** Extracted `experience` and `education` data is verified, formatted, and saved to the DB (`postgres_repo`).

## 2. Data Structures (Pydantic Mapping)
The AI is instructed to output a strict JSON layout:
- **Experience:** `{ "company": "...", "title": "...", "start_date": "YYYY-MM", "end_date": "YYYY-MM", "description": "...", "location": "..." }`
- **Education:** `{ "institution": "...", "degree": "...", "start_date": "...", "end_date": "...", "location": "..." }`

## 3. Edge Cases & Failure Modes (Critical)
- **Bad Cookies:** Fails fast using `ValueError` before spending compute or AI tokens if cookies are missing.
- **Network / DOM Changes:** By relying on `innerText` and an LLM, we are completely immune to LinkedIn changing their CSS class names or DOM structure (a common breakage in traditional scraping).
- **AI Hallucinations:** The system prompt aggressively mandates strict JSON parsing and explicitly forbids inventing jobs or dates not found in the raw text.

## 4. Integration with Existing Stack
- Upgrades `src/core/linkedin_enricher.py` to use an `async def fetch_profile()` method.
- Tweaks `src/ui/app.py` to `run_async()` the fetch.
- Retains `test_linkedin_enricher.py` testing the logic by mocking Playwright and the AI call to ensure offline CI builds remain unbroken.

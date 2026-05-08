# Phase C.2 — Cover Letter + Match Score + Search/Sort

**Date:** 2026-04-08  
**Status:** Approved  

---

## Scope

Three high-impact features that close the gap with aiapply.co / jobcopilot.com.

## Feature 1: Job Match Score (M2)

- New module `src/core/matching.py` with `compute_match_score(resume_text, jd_text, model) -> int`
- Uses existing `all-MiniLM-L6-v2` from `LedgerManager`
- Cosine similarity → scaled 0–100: `min(100, max(0, int((raw - 0.2) / 0.6 * 100)))`
- No API calls — local ~20ms/job
- Colored pill on job cards: green ≥70, yellow 40–69, red <40

## Feature 2: Cover Letter Generation (M1)

- New `AITailor.generate_cover_letter(job) -> str` async method
- 3-paragraph format: Why this role → What I bring → Call to action
- Strict no-hallucination, uses same resume text
- 1 Gemini call per job (user-triggered)
- Stored in `TailoredResultModel.cover_letter_text` column
- Displayed in expander with copy button

## Feature 3: Search & Sort (M3)

- `st.text_input` search bar: filters by company/role substring
- `st.selectbox` sort: Best Match / Company A→Z / Company Z→A
- Pure Python list operations, no DB changes

## Schema Changes

- `TailoredResultModel`: add `cover_letter_text: Text` (nullable)
- `save_tailored_result` / `get_tailored_result`: add optional `cover_letter` param

## New Files

- `src/core/matching.py`
- `tests/test_phase_c2.py`

## Modified Files

- `src/core/ai.py`, `src/core/repository.py`, `src/infrastructure/postgres_repo.py`
- `src/ui/mock_repo.py`, `src/ui/app.py`

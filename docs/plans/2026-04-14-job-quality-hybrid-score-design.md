# Phase E.1 — Job Quality: Hybrid Match Score + No-Description Filter

**Date:** 2026-04-14  
**Status:** Implemented  

---

## Scope

Two targeted improvements to the quality of jobs surfaced in the feed:
1. Make the match score reflect both *semantic similarity* and *keyword overlap* — not just vector cosine.
2. Silently drop scraped jobs that have no description, because they are un-tailorable and waste space in the feed.

---

## Problem Statement

**Match score was too permissive.** Pure cosine similarity scores two resumes the same against a JD even when one explicitly lists all the required tools and the other does not. A Python developer and a Node.js developer both scored ~40% against a Python JD, which is wrong.

**No-description jobs polluted the feed.** LinkedIn frequently returns job cards with `"Description not provided."` or empty strings. The RAG tailor cannot produce useful output from them; they just confuse the user.

---

## Feature 1: Hybrid Match Score

**Module:** `src/core/matching.py`

**Formula:**
$$\text{score} = 0.5 \times \text{semantic} + 0.5 \times \text{keyword\_overlap}$$

**Semantic component** (unchanged from before):
- SentenceTransformer cosine similarity
- Rescaled: `(raw_sim - 0.2) / 0.6 × 100`, clamped 0–100

**Keyword overlap component** (new):
```python
def _keyword_overlap_score(resume_text: str, jd_text: str) -> int:
    # Extract alphanumeric tokens ≥3 chars from JD
    jd_tokens = {t.lower() for t in re.findall(r'[A-Za-z0-9#+]+', jd_text) if len(t) >= 3}
    if not jd_tokens:
        return 0
    resume_tokens = {t.lower() for t in re.findall(r'[A-Za-z0-9#+]+', resume_text) if len(t) >= 3}
    overlap = len(jd_tokens & resume_tokens)
    return int(overlap / len(jd_tokens) * 100)
```

**Effect:** A resume listing "Python Django PostgreSQL Redis" against a matching JD will score ~20 points higher than a semantically similar resume that uses different terminology.

**Edge cases:**
- Empty resume or JD → returns 0 immediately (no model call)
- Empty JD token set → keyword component = 0, falls back to semantic only

---

## Feature 2: No-Description Filter

**Module:** `src/scrapers/worker.py`

Applied *before* deduplication and before `save_job`, so bad jobs are never stored at all:

```python
_BAD_DESC = {"", "Description not provided.", "None", "nan"}
_desc_str = "" if not description or pd.isna(description) else str(description).strip()
if _desc_str in _BAD_DESC:
    logger.debug(f"Skipping job {job_id}: no description")
    continue   # do not save, do not add to all_found_ids
```

**Design decision:** Filter at scrape time (not display time) so the DB stays clean. A job with no description has no value in the system.

---

## `_scrape_df` extraction

`run_sweep`'s blocking JobSpy call was extracted into a dedicated `_scrape_df(role, location, results_wanted)` async method. This makes the scraper mockable in unit tests via `patch.object(engine, '_scrape_df', return_value=df)`.

---

## New Files

- `tests/test_job_quality.py` — 9 tests for both features

## Modified Files

- `src/core/matching.py` — hybrid score + `_keyword_overlap_score` helper
- `src/scrapers/worker.py` — `_scrape_df` extraction + no-description filter
- `tests/test_phase_c2.py` — `test_related_texts_score_moderate` lower bound updated (20→30 was too strict for hybrid which correctly penalises keyword mismatch)

---

## Tests: 9 new in `test_job_quality.py`

**Hybrid score (Q1):**
- `test_keyword_overlap_boosts_score_vs_pure_semantic`
- `test_no_keyword_overlap_still_uses_semantic`
- `test_keyword_overlap_score_all_match` → 100
- `test_keyword_overlap_score_no_match` → 0
- `test_keyword_overlap_score_partial` → 40–60
- `test_score_always_0_to_100`
- `test_empty_inputs_return_zero`

**No-description filter (Q2):**
- `test_no_description_job_not_saved` — covers `""`, `None`, `"Description not provided."`
- `test_real_description_job_is_saved` — valid description still goes through

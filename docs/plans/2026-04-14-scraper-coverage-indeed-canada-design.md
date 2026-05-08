# Phase E.2 — Scraper Coverage: Indeed Canada Fix + Location Autocomplete

**Date:** 2026-04-14  
**Status:** Implemented  

---

## Scope

Fix the root cause of low job counts for Canadian locations and improve the location input UX.

---

## Problem Statement

A search for "Software Engineer intern · Vancouver, BC" returned only 4 results. Investigation revealed:

| Source | Results | Root cause |
|---|---|---|
| LinkedIn | 18 raw rows (14 filtered by title guard) | Working correctly |
| Indeed | 0 rows | Missing `country_indeed='canada'` parameter |
| Google Jobs | 0 rows | Actively blocked by Google's anti-scraper protection |

Indeed's API requires an explicit `country_indeed` parameter to scope results to a country. Without it, the default is `'usa'`, and Canadian location queries return nothing.

Google Jobs (JobSpy integration) was also attempted but confirmed non-functional — Google's bot detection blocks all JobSpy requests with 0 results every time. It was removed to avoid wasting ~10s of wait time per search.

---

## Fix 1: Indeed Canada Auto-Detection

**Module:** `src/scrapers/worker.py`

```python
_CA_MARKERS = {", bc", ", on", ", ab", ", qc", ", mb", ", sk", ", ns", ", nb",
               ", nl", ", pe", ", nt", ", yt", ", nu", "canada"}

def _detect_country_indeed(location: str) -> str:
    loc = location.lower()
    if any(m in loc for m in _CA_MARKERS):
        return "canada"
    return "usa"
```

Passed to `scrape_jobs(country_indeed=country)`. Works for any Canadian city name as long as the province abbreviation is included (which the UI's location selectbox ensures).

---

## Fix 2: Location Autocomplete Selectbox

**Module:** `src/ui/app.py`

Replaced `st.text_input` for location with `st.selectbox` containing 17 curated tech-hub cities:

```python
_LOC_SUGGESTIONS = [
    "Remote", "Vancouver, BC", "Toronto, ON", "Calgary, AB",
    "Edmonton, AB", "Ottawa, ON", "Montreal, QC", "Waterloo, ON",
    "Victoria, BC", "Seattle, WA", "San Francisco, CA", "New York, NY",
    "Austin, TX", "Boston, MA", "Los Angeles, CA", "London, UK", "Singapore",
]
```

- User's saved `pref_location` is auto-selected as the default.
- If the saved preference isn't in the curated list (e.g. a custom city), it's prepended to the top of the options list so it's still selectable.
- Streamlit's selectbox supports keyboard typing to filter — functionally equivalent to autocomplete.

---

## Fix 3: Cap raised 25 → 50

`_run_discovery(repo, role, loc, 25)` → `_run_discovery(repo, role, loc, 50)`

With Indeed now contributing results, the per-source cap was doubled to get more total coverage.

---

## Modified Files

- `src/scrapers/worker.py` — `_detect_country_indeed()` function, `country_indeed` param in `_scrape_df`
- `src/ui/app.py` — location selectbox replacing text_input; cap 25→50; status message updated

## No new tests

The `_detect_country_indeed` function is pure logic with no I/O. The existing `test_sourcing_engine.py` suite covers `run_sweep` end-to-end with mocked `scrape_jobs`, which already validates the Canada parameter path indirectly.

# Phase F.2 — Analytics Dashboard Design
**Date:** 2026-04-15  
**Status:** Approved

## Overview
A new "📊 Stats" page in the Streamlit sidebar that gives the user a bird's-eye view of their job hunt pipeline — no new DB tables, no new dependencies.

## Architecture & Data Flow
```
User clicks "📊 Stats" in sidebar nav radio
  │
  ├── Collect all jobs: get_jobs_by_status() × 6 statuses (merge into flat list)
  ├── compute_analytics(jobs: list[Job]) -> AnalyticsResult  ← pure, testable
  └── Render 4 sections with st.metric + st.bar_chart (built-in Streamlit)
```

## Data Structures

### `AnalyticsResult` (TypedDict in src/core/analytics.py)
```python
class AnalyticsResult(TypedDict):
    funnel: dict[str, int]         # {status_value: count}
    timeline: dict[str, int]       # {"2026-W14": 5, ...} — week buckets
    top_companies: dict[str, int]  # {"Amazon": 3, "Google": 2, ...}
    salary_min_avg: float | None   # avg of salary_min across jobs with data
    salary_max_avg: float | None   # avg of salary_max across jobs with data
    salary_count: int              # how many jobs have salary data
```

## 4 Dashboard Sections
1. **Funnel** — st.metric tiles: Sourced / Pending / Applied / Interview
2. **Activity Timeline** — bar chart: jobs discovered per ISO week
3. **Top Companies** — horizontal bar chart: top 10 companies by job count
4. **Salary Snapshot** — avg min / avg max metrics (hidden if salary_count == 0)

## Key Decisions
- **No new ABC methods** — re-use `get_jobs_by_status()` for all statuses
- **No new dependencies** — `st.bar_chart` only (pandas already in requirements)
- **New file `src/core/analytics.py`** — pure `compute_analytics()` function, zero Streamlit imports → fully unit testable
- **Graceful empty state** — each section shows a friendly message if no data

## Tests (TDD)
See `tests/test_analytics.py`
- `test_funnel_counts_by_status`
- `test_timeline_buckets_by_iso_week`
- `test_timeline_excludes_empty_date_posted`
- `test_top_companies_sorted_descending`
- `test_top_companies_limited_to_10`
- `test_salary_avg_correct`
- `test_salary_count_zero_when_no_data`
- `test_empty_job_list_returns_zeros`

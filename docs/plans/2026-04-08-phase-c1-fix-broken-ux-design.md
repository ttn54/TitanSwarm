# Phase C.1 — Fix All Broken UX + Kanban Actions

**Date:** 2026-04-08  
**Status:** Approved  

---

## Scope

Fix 6 broken/non-functional items in the Streamlit UI and add missing Kanban action buttons.

## Changes

### B1: Functional Filter Chips
- Replace static HTML `<span>` chips with `st.pills()` (native Streamlit component)
- Options: All, Remote, Internship, Full-time, Co-op
- Filter logic: substring match on `job.role + job.job_description` (case-insensitive)
- Drop "< 50 employees" (no company-size data available)

### B2 + B3: Profile Completion + Website Field
- Add `st.text_input("Website", key="_pf_website")` to Preferences Identity section
- Update profile completion: count `website` field → divide by 6 (sidebar + Preferences page)

### B4: Sidebar Interview Count
- Query `n_interview = count(JobStatus.INTERVIEW)`
- Add "Interview" line to sidebar pipeline stats

### B5 + M4: Kanban Action Buttons per Lane
| Lane            | Buttons               |
|-----------------|-----------------------|
| Pending Review  | ✅ Submit, ✗ Reject   |
| Applied         | 🎤 Interview, ✗ Reject|
| Interview       | ✗ Reject              |
| Rejected        | (none)                |

### B6: Persist Job Preferences
- Add `pref_role: str`, `pref_location: str` to `UserProfile` model + DB table
- Load from DB on startup, persist on "Save Preferences" click
- Requires DB reset (dev-only, no migration needed)

## Files Modified
- `src/core/models.py` — 2 new fields on UserProfile
- `src/infrastructure/postgres_repo.py` — 2 new columns on UserProfileModel
- `src/ui/app.py` — 6 targeted edits
- `tests/test_phase_c1.py` — new test file

## No New Dependencies

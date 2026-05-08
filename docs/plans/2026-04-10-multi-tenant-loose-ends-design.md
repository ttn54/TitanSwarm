# Phase D.2 — Multi-Tenant Loose Ends: Ledger & Profile Fully DB-Backed

**Date:** 2026-04-10  
**Status:** Implemented  

---

## Scope

After multi-tenant auth landed, four code paths were still reading from / writing to `data/ledger.md` on disk instead of the per-user DB ledger. This caused data leakage: any user's resume upload or GitHub enrichment would overwrite the shared file and bleed into every other user's account.

---

## Problem Statement

| Code path | Pre-fix behaviour | Risk |
|---|---|---|
| `resume_text_cache` init | Read `data/ledger.md` | All users share same base resume text for match scoring |
| Resume upload | Write `data/ledger.md` | Upload by user A overwrites user B's file |
| GitHub enrichment | Read + write `data/ledger.md` | Same cross-user contamination |
| Tailor resume PDF | Read `data/ledger.md` for structured parsing | PDF uses wrong user's education/experience |

---

## Fix 1: `resume_text_cache` — DB-backed

```python
# OLD
with open("data/ledger.md") as f:
    resume_text_cache = f.read()

# NEW
_db_content = run_async(repo.get_ledger(_USER_ID))
if _db_content:
    # write to temp file → parse → delete
else:
    # fall back to data/ledger.md for fresh installs
```

---

## Fix 2: Resume Upload — writes to DB

```python
# OLD
with open("data/ledger.md", "w") as f:
    f.write(new_content)

# NEW
run_async(repo.save_ledger(_USER_ID, new_content))
tailor = AITailor(LedgerManager.from_content(new_content))
```

`LedgerManager.from_content(content)` is a new classmethod that writes content to a temp file, builds the FAISS index from it, and cleans up — without touching `data/ledger.md`.

---

## Fix 3: GitHub Enrichment — reads + writes DB

```python
# OLD
with open("data/ledger.md", "r") as f: current = f.read()
# ... append GitHub section ...
with open("data/ledger.md", "w") as f: f.write(updated)

# NEW
current = run_async(repo.get_ledger(_USER_ID))
# ... append GitHub section ...
run_async(repo.save_ledger(_USER_ID, updated))
tailor = AITailor(LedgerManager.from_content(updated))
```

---

## Fix 4: Tailor Resume PDF — reads DB ledger

```python
# OLD
_structured = _parse_ledger_for_pdf("data/ledger.md")

# NEW
_db_content = run_async(repo.get_ledger(_USER_ID))
if _db_content:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    tmp.write(_db_content); tmp.close()
    _structured = _parse_ledger_for_pdf(tmp.name)
    os.unlink(tmp.name)
else:
    _structured = _parse_ledger_for_pdf("data/ledger.md")  # fallback
```

---

## Fix 5: Sidebar CSS — collapse toggle was hidden

The `header { visibility: hidden }` CSS rule was hiding the Streamlit sidebar collapse button. Fixed to only hide non-button children:

```css
/* OLD — hid everything including the collapse toggle */
header { visibility: hidden; }

/* NEW — hides decoration but keeps buttons accessible */
header[data-testid="stHeader"] > * { visibility: hidden; }
header[data-testid="stHeader"] button { visibility: visible !important; }
```

---

## New Files / Changes

- `src/core/ledger.py` — `LedgerManager.from_content(content, db_path)` classmethod
- `src/ui/app.py` — all four code paths patched; sidebar CSS fix

## No schema changes
All data already exists in `user_ledgers` table from D.1.

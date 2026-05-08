# Phase D.1 — Multi-Tenant Authentication & Per-User Data Isolation

**Date:** 2026-04-09  
**Status:** Implemented  

---

## Scope

Transform TitanSwarm from a single-user local tool into a proper multi-tenant SaaS where every user has their own isolated account, job feed, ledger, and tailored results.

---

## Problem Statement

The original system hardcoded `user_id=1` everywhere. A second person opening the app would share the same jobs, profile, and ledger — making the system unusable as a shared service.

---

## Feature 1: User Authentication

**New DB table: `users`**
```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL   -- bcrypt hash, never plaintext
);
```

**New methods on `PostgresRepository`:**
- `create_user(username, password) -> int` — hashes password with bcrypt, inserts row, returns new `user_id`. Raises `ValueError` on duplicate username.
- `get_user_by_username(username) -> dict | None` — returns `{id, username, password_hash}`.
- `verify_user(username, password) -> int | None` — bcrypt check; returns `user_id` on success, `None` on failure.

**Security decisions:**
- `bcrypt==5.0.0` with auto-generated salt per user.
- Password is never stored or logged in plaintext.
- No JWT/session tokens — Streamlit session state holds `user_id` after login.

---

## Feature 2: Per-User Ledger

**New DB table: `user_ledgers`**
```sql
CREATE TABLE user_ledgers (
    user_id INTEGER PRIMARY KEY,
    content TEXT DEFAULT ''
);
```

- On first register: seed ledger content from `data/ledger.md` (the base template).
- All subsequent reads/writes go through `get_ledger(user_id)` / `save_ledger(user_id, content)`.

---

## Feature 3: Per-User Data Scoping

`user_id` column (default=1 for backward compat) added to:
- `jobs` table
- `user_profile` table
- `tailored_results` table

All repository methods updated with `user_id: int = 1` parameter:
`save_job`, `get_job`, `update_status`, `get_jobs_by_status`, `count_all`, `delete_jobs_by_status`, `save_profile`, `get_profile`, `save_tailored_result`, `get_tailored_result`.

Migration handled by `_ensure_columns()` at `init_db()` time — safe to run against existing DBs.

---

## Feature 4: Login/Register Gate in UI

`src/ui/app.py` — auth gate renders before any other content:

```python
if "user_id" not in st.session_state:
    _render_auth_page()   # shows Login / Register tabs
    st.stop()

_USER_ID: int = st.session_state["user_id"]
```

- **Login tab:** `verify_user` → set `session_state.user_id` + `session_state.username`.
- **Register tab:** `create_user` → seed ledger from `data/ledger.md` → set session.
- **Logout button** in sidebar bottom: clears all session state keys → `st.rerun()`.

---

## Data Flow

```
Browser → Streamlit → _render_auth_page()
                            │
               ┌────────────┴────────────┐
               │ Login                   │ Register
               ▼                         ▼
    verify_user(u, p)           create_user(u, p)
               │                         │
               └────────────┬────────────┘
                            ▼
              session_state["user_id"] = uid
              session_state["username"] = u
              st.rerun() → full UI renders
```

---

## New Files

- `tests/test_auth_repo.py` — 11 tests covering all auth + ledger methods

## Modified Files

- `src/infrastructure/postgres_repo.py` — UserModel, UserLedgerModel, all scoped methods
- `src/core/repository.py` — all method signatures updated with `user_id: int = 1`
- `src/core/models.py` — new `User(BaseModel)` with `id: int`, `username: str`
- `src/core/ledger.py` — `LedgerManager.from_content()` classmethod
- `src/ui/mock_repo.py` — all signatures updated
- `src/ui/app.py` — auth gate, logout, `_USER_ID` constant
- `requirements.txt` — added `bcrypt==5.0.0`

---

## Tests: 11 new in `test_auth_repo.py`

- `test_create_user_returns_id`
- `test_create_duplicate_username_raises`
- `test_password_is_hashed_not_stored_plaintext`
- `test_verify_correct_password_returns_user_id`
- `test_verify_wrong_password_returns_none`
- `test_verify_unknown_username_returns_none`
- `test_save_and_get_ledger`
- `test_ledger_isolated_between_users`
- `test_get_ledger_returns_empty_string_for_new_user`
- `test_jobs_isolated_between_users`
- `test_default_user_id_1_backward_compatible`

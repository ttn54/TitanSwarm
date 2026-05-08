# Performance & Stability Optimizations Design
**Date:** 2026-04-23
**Status:** Approved

## 1. Architecture and Data Flow
- **Backend:** Upgrade `PostgresRepository` to use explicit DB connection pooling (`pool_size` and `max_overflow`). Apply B-Tree indexes on heavily queried columns (`status`, `user_id`, `company`, `role`) to prevent full table scans.
- **Frontend (Streamlit):** Refactor sequential `run_async()` I/O calls into concurrent fetches using `asyncio.gather()`, particularly on the Kanban board which currently blocks multiple times to load different columns.
- **Memory Management:** Ensure Streamlit session state is cleanly caching ML models and computationally heavy data (like resume text parsing) and not redundantly loading them per interaction.

## 2. Data Structures & Schema Changes
- Upgrade `JobModel` in SQLAlchemy to add `index=True` on:
  - `status`
  - `user_id`
  - `company`
  - `role`

## 3. Edge Cases & Resilience
- **Connection Leakage:** Ensure `asyncio.gather()` fetches don't exhaust the connection pool by correctly setting `pool_size` properly relative to max expected concurrent UI tasks.
- **Async Loop Safety:** Ensure Streamlit's implicit threading interactions with `asyncio.run` during `gather` gracefully handle the underlying event loops without throwing `RuntimeError`.

## 4. Testing Strategy
- Write failing tests validating that the SQLAlchemy engine is created with correct `pool_size` options.
- Inspect the schema metadata within tests to verify `index=True` was applied to the necessary columns.

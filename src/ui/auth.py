"""
Authentication layer for TitanSwarm.

Handles:
- HMAC-signed cookie-based sessions
- Login / register page rendering
- Rate limiting for brute-force protection

Extracted from the monolith app.py.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as _components

from src.ui.components import run_async

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# COOKIE AUTH HELPERS
# ─────────────────────────────────────────────────────────────────────────────
_COOKIE_NAME = "ts_session"
_COOKIE_DAYS = 7  # reduced from 30 — shorter window for credential abuse

# SESSION_SECRET must be set in production.  If it is missing we generate a
# random per-process secret and log a loud warning — sessions will not survive
# restarts, but at least they cannot be forged with a well-known default.
_cookie_secret_env = os.getenv("SESSION_SECRET", "")
if _cookie_secret_env:
    _COOKIE_SECRET: str = _cookie_secret_env
else:
    import secrets as _secrets
    _COOKIE_SECRET = _secrets.token_hex(32)
    logger.warning(
        "SESSION_SECRET not set — using a random per-process secret. "
        "All sessions will be invalidated on restart. "
        "Set SESSION_SECRET in your .env for production."
    )


def _sign(payload: str) -> str:
    return hmac.new(_COOKIE_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def set_session_cookie(uid: int, username: str) -> None:
    """Set a signed session cookie and reload the page."""
    value = _make_cookie_value(uid, username)
    expiry = (datetime.now() + timedelta(days=_COOKIE_DAYS)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    # NOTE: HttpOnly cannot be set from JavaScript — use a reverse proxy
    # (nginx) to add the HttpOnly flag in production:
    #   proxy_cookie_flags ts_session HttpOnly Secure;
    _components.html(
        f'<script>document.cookie="{_COOKIE_NAME}={value}; path=/; expires={expiry}; SameSite=Lax; Secure"; window.parent.location.reload();</script>',
        height=0,
    )


def delete_session_cookie() -> None:
    """Delete the session cookie and reload."""
    _components.html(
        f'<script>document.cookie="{_COOKIE_NAME}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax; Secure"; window.parent.location.reload();</script>',
        height=0,
    )


def _make_cookie_value(uid: int, username: str) -> str:
    payload = f"{uid}:{username}"
    return f"{payload}:{_sign(payload)}"


def verify_cookie(value: str):
    """Returns (user_id, username) if signature valid, else None."""
    try:
        last_colon = value.rfind(":")
        if last_colon == -1:
            return None
        payload, sig = value[:last_colon], value[last_colon + 1:]
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        uid_str, username = payload.split(":", 1)
        return int(uid_str), username
    except Exception:
        return None


def get_cookie_name() -> str:
    """Return the session cookie name (for restore logic)."""
    return _COOKIE_NAME


# ─────────────────────────────────────────────────────────────────────────────
# AUTH RATE LIMITER — simple in-memory tracker with exponential backoff
# ─────────────────────────────────────────────────────────────────────────────
_MAX_ATTEMPTS = 5           # allow 5 failed attempts before throttling
_WINDOW_SECS = 300          # 5-minute tracking window
_BACKOFF_BASE = 2           # exponential: 2s, 4s, 8s, 16s, 32s


class AuthRateLimiter:
    """Tracks failed login attempts per username per time window.

    After _MAX_ATTEMPTS failures, imposes an exponentially-growing cooldown
    (base _BACKOFF_BASE).  Successful login clears the record.

    NOT thread-safe — Streamlit runs single-threaded per session, so this is
    safe for its use case.  Replace with a Redis-backed limiter for multi-worker.
    """
    def __init__(self):
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - _WINDOW_SECS
        self._attempts[key] = [t for t in self._attempts.get(key, []) if t > cutoff]

    def check(self, username: str) -> tuple[bool, int]:
        """Return (allowed, wait_seconds).  allowed=False means the user must wait."""
        key = f"login:{username.lower().strip()}"
        now = time.time()
        self._prune(key, now)
        failures = len(self._attempts[key])
        if failures < _MAX_ATTEMPTS:
            return True, 0
        # Exponential backoff: attempt #6 = 32s, #7 = 64s, cap at 5 min
        wait = min(_BACKOFF_BASE ** (failures - _MAX_ATTEMPTS + 1), _WINDOW_SECS)
        return False, int(wait)

    def record_failure(self, username: str) -> None:
        key = f"login:{username.lower().strip()}"
        self._attempts[key].append(time.time())

    def clear(self, username: str) -> None:
        key = f"login:{username.lower().strip()}"
        self._attempts.pop(key, None)


# Module-level singleton
AUTH_RATE_LIMITER = AuthRateLimiter()


# ─────────────────────────────────────────────────────────────────────────────
# AUTH GATE — must be satisfied before any other UI renders
# ─────────────────────────────────────────────────────────────────────────────
def render_auth_page():
    """Renders the login / register page and halts app rendering until authenticated."""
    st.markdown("""
    <style>
    .auth-wrap { max-width: 420px; margin: 6rem auto 0 auto; }
    .auth-title { font-size: 2rem; font-weight: 800; color: #0f172a;
                  letter-spacing: -0.04em; text-align: center; margin-bottom: 0.25rem; }
    .auth-sub   { font-size: 0.9rem; color: #64748b; text-align: center; margin-bottom: 2rem; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="auth-title">⚡ TitanSwarm</div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-sub">Your autonomous job application Co-Pilot</div>', unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Log In", "Register"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")
        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                # Rate-limit check before touching the database
                allowed, wait_sec = AUTH_RATE_LIMITER.check(username)
                if not allowed:
                    st.error(f"Too many failed attempts. Please wait {wait_sec} seconds before trying again.")
                else:
                    uid = run_async(st.session_state.repo.verify_user(username, password))
                    if uid is None:
                        AUTH_RATE_LIMITER.record_failure(username)
                        st.error("Invalid username or password.")
                    else:
                        AUTH_RATE_LIMITER.clear(username)
                        st.session_state["user_id"] = uid
                        st.session_state["username"] = username
                        set_session_cookie(uid, username)
                        st.stop()

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_password = st.text_input("Choose a password", type="password")
            confirm_pw   = st.text_input("Confirm password", type="password")
            reg_submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")
        if reg_submitted:
            if not new_username or not new_password:
                st.error("Username and password are required.")
            elif not re.match(r'^[a-zA-Z0-9_.-]{3,32}$', new_username):
                st.error("Username must be 3–32 characters: letters, numbers, dots, hyphens, underscores only.")
            elif new_password != confirm_pw:
                st.error("Passwords do not match.")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif not re.search(r'[A-Z]', new_password) or not re.search(r'[0-9]', new_password):
                st.error("Password must contain at least one uppercase letter and one number.")
            else:
                try:
                    uid = run_async(st.session_state.repo.create_user(new_username, new_password))
                    st.session_state["user_id"] = uid
                    st.session_state["username"] = new_username
                    set_session_cookie(uid, new_username)
                    st.success(f"Account created! Welcome, {new_username}.")
                    st.stop()
                except ValueError as e:
                    st.error(str(e))

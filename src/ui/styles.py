"""
Global CSS styles injected into every Streamlit page.

Extracted from the monolith app.py so each page module can call
``inject_styles()`` without duplicating the CSS.
"""

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }
/* Make header transparent (hides Streamlit branding) but keep toggle button clickable */
header[data-testid="stHeader"] { background: transparent !important; }
header[data-testid="stHeader"] > * { visibility: hidden; }
header[data-testid="stHeader"] button { visibility: visible !important; }
.stApp { background: #f1f5f9; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] * { color: #94a3b8 !important; }
/* Ensure radio inputs remain fully interactive — the wildcard above can suppress pointer events */
section[data-testid="stSidebar"] input[type="radio"] { pointer-events: auto !important; opacity: 0 !important; }
section[data-testid="stSidebar"] .stRadio label { font-size: 0.88rem !important; pointer-events: auto !important; }

.nav-logo {
    font-size: 1.3rem; font-weight: 800; color: #fff !important;
    letter-spacing: -0.04em; padding: 0.5rem 0 1.5rem 0;
}
.nav-logo span { color: #818cf8 !important; }

.nav-divider { border: none; border-top: 1px solid #1e293b; margin: 0.75rem 0; }

.nav-section-label {
    font-size: 0.68rem !important; font-weight: 600 !important;
    text-transform: uppercase; letter-spacing: 0.08em;
    color: #475569 !important; padding: 0.4rem 0 0.2rem 0;
}

div[data-testid="stRadio"] label {
    display: flex !important; align-items: center !important;
    padding: 0.5rem 0.75rem !important; border-radius: 8px !important;
    font-weight: 500 !important; font-size: 0.875rem !important;
    color: #94a3b8 !important; cursor: pointer;
    transition: background 0.1s;
}
div[data-testid="stRadio"] label:hover { background: #1e293b !important; color: #e2e8f0 !important; }

/* Active nav item: Streamlit marks selected radio differently in DOM */
div[data-testid="stRadio"] label[data-checked="true"],
div[data-testid="stRadio"] div[aria-checked="true"] label {
    background: #1e293b !important; color: #ffffff !important;
}

/* ── Main area ── */
.main-header {
    font-size: 1.6rem; font-weight: 800; color: #0f172a;
    letter-spacing: -0.04em; line-height: 1.2;
}
.main-subheader { font-size: 0.88rem; color: #64748b; margin-top: 2px; }

/* ── KPI strip ── */
.kpi-card {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 1.1rem 1.4rem; box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.kpi-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.07em; color: #94a3b8; font-weight: 600; }
.kpi-value { font-size: 1.9rem; font-weight: 800; color: #0f172a; line-height: 1.1; margin-top: 2px; }
.kpi-sub   { font-size: 0.78rem; color: #10b981; font-weight: 500; margin-top: 2px; }

/* ── Search bar ── */
.search-wrap {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 1rem 1.25rem; margin-bottom: 1rem; box-shadow: 0 1px 4px rgba(0,0,0,.04);
}

/* ── Filter chips ── */
.chip-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 0.5rem 0 1rem 0; }
.chip {
    padding: 4px 14px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
    cursor: pointer; border: 1.5px solid #e2e8f0; background: #fff; color: #64748b;
    transition: all 0.12s;
}
.chip.active { background: #ede9fe; border-color: #818cf8; color: #4f46e5; }

/* ── Job card ── */
.jcard {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 1.1rem 1.3rem 1rem 1.3rem; margin-bottom: 0.65rem;
    transition: box-shadow 0.15s, border-color 0.15s;
}
.jcard:hover { box-shadow: 0 6px 24px rgba(0,0,0,.08); border-color: #c7d2fe; }
.jcard-top { display: flex; align-items: flex-start; gap: 0.85rem; }
.jcard-avatar {
    width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
    background: linear-gradient(135deg,#6366f1,#8b5cf6);
    color: #fff; font-size: 1.05rem; font-weight: 800;
    display: flex; align-items: center; justify-content: center;
}
.jcard-company { font-size: 1rem; font-weight: 700; color: #0f172a; }
.jcard-role    { font-size: 0.875rem; font-weight: 600; color: #6366f1; margin-top: 1px; }
.jcard-meta    { font-size: 0.76rem; color: #94a3b8; margin-top: 3px; }
.jcard-desc    { font-size: 0.82rem; color: #64748b; margin-top: 0.55rem; line-height: 1.55; }
.jcard-skills  { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 0.5rem; }
.skill-pill {
    background: #f1f5f9; color: #475569; font-size: 0.72rem; font-weight: 500;
    padding: 2px 9px; border-radius: 6px;
}

/* ── Status badges ── */
.badge { display:inline-flex; align-items:center; gap:4px; padding:3px 10px; border-radius:999px; font-size:0.72rem; font-weight:600; letter-spacing:0.03em; }
.badge::before { content:''; width:6px; height:6px; border-radius:50%; }
.badge-pending   { background:#fef3c7; color:#92400e; } .badge-pending::before   { background:#f59e0b; }
.badge-submitted { background:#d1fae5; color:#065f46; } .badge-submitted::before { background:#10b981; }
.badge-new       { background:#ede9fe; color:#4338ca; } .badge-new::before       { background:#818cf8; }
.badge-rejected  { background:#fee2e2; color:#991b1b; } .badge-rejected::before  { background:#f87171; }
.badge-interview { background:#dbeafe; color:#1d4ed8; } .badge-interview::before { background:#60a5fa; }

/* ── Primary / secondary buttons ── */
.stButton > button[kind="primary"] {
    background: #6366f1 !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: 0.855rem !important;
    padding: 0.45rem 1rem !important;
    transition: background 0.15s !important;
}
.stButton > button[kind="primary"]:hover { background: #4f46e5 !important; }
.stButton > button[kind="secondary"] {
    background: #fff !important; color: #374151 !important;
    border: 1.5px solid #e2e8f0 !important; border-radius: 8px !important;
    font-weight: 500 !important; font-size: 0.855rem !important;
}
.stButton > button[kind="secondary"]:hover { border-color: #818cf8 !important; color: #4f46e5 !important; }

/* ── Inputs ── */
input, textarea, .stSelectbox > div {
    border-radius: 8px !important; border: 1.5px solid #e2e8f0 !important;
    font-size: 0.875rem !important; color: #1e293b !important;
}
input:focus, textarea:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,.12) !important; outline: none !important; }
label { font-size: 0.8rem !important; font-weight: 600 !important; color: #374151 !important; }

/* ── Kanban columns ── */
.kanban-col {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 14px; padding: 0.85rem;
}
.kanban-col-header {
    font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #64748b; margin-bottom: 0.75rem;
    display: flex; align-items: center; justify-content: space-between;
}
.kanban-count {
    background: #e2e8f0; color: #64748b; border-radius: 999px;
    font-size: 0.72rem; font-weight: 700; padding: 1px 7px;
}
.kanban-card {
    background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 0.75rem 0.85rem; margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.kanban-card .kc-company { font-size: 0.82rem; font-weight: 700; color: #0f172a; }
.kanban-card .kc-role    { font-size: 0.78rem; color: #6366f1; font-weight: 500; margin-top:1px; }
.kanban-card .kc-url     { font-size: 0.72rem; color: #94a3b8; margin-top:3px; }

/* ── Profile page ── */
.profile-card {
    background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 1.4rem 1.6rem; margin-bottom: 1rem;
}
.profile-card-title { font-size: 0.875rem; font-weight: 700; color: #0f172a; margin-bottom: 0.85rem; }

/* ── Divider ── */
.divider { border: none; border-top: 1px solid #e2e8f0; margin: 1rem 0; }

/* ── Progress ── */
div[data-testid="stProgress"] > div { background: #ede9fe !important; border-radius: 999px !important; }
div[data-testid="stProgress"] > div > div { background: #6366f1 !important; border-radius: 999px !important; }

/* ── Expander ── */
details summary { font-size: 0.82rem !important; font-weight: 600 !important; color: #475569 !important; }
</style>
"""


def inject_styles():
    """Inject global CSS into the Streamlit page."""
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

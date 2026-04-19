"""
Tests for src/core/website_enricher.py

Covers:
  1. fetch_website_context returns a non-empty ledger block when given valid HTML
  2. Education and Work Experience sections appear in the output
  3. Empty string returned on network errors (not a crash)
  4. Empty string returned for an empty / JavaScript-only page
  5. URL is sanitised (http or https) before fetching
"""
import pytest
from unittest.mock import patch, MagicMock


# ── helpers ──────────────────────────────────────────────────────────────────

SAMPLE_HTML = """
<html>
<body>
<h1>John Smith — Software Engineer</h1>
<section id="education">
  <h2>Education</h2>
  <p>Bachelor of Science, Computer Science — University of British Columbia — Sep 2022 – Apr 2026</p>
</section>
<section id="experience">
  <h2>Work Experience</h2>
  <p>Software Engineer Intern — Shopify — May 2025 – Aug 2025</p>
  <p>Automated internal tools in Python, reducing deployment time by 40%.</p>
</section>
<section id="skills">
  <h2>Skills</h2>
  <p>Python, Go, React, Docker, PostgreSQL</p>
</section>
</body>
</html>
"""

FAKE_AI_RESPONSE = """\
## Website:

EDUCATION
Bachelor of Science, Computer Science  May 2022 – Apr 2026
University of British Columbia

WORK EXPERIENCE
Software Engineer Intern  May 2025 – Aug 2025
Shopify
• Automated internal tools in Python, reducing deployment time by 40%.
"""


# ── tests ─────────────────────────────────────────────────────────────────────

def test_fetch_website_context_returns_string():
    """Module is importable and fetch_website_context is callable."""
    from src.core.website_enricher import fetch_website_context
    assert callable(fetch_website_context)


def test_fetch_website_context_returns_ai_output_on_success():
    """
    When httpx.get succeeds and Gemini returns a structured response,
    fetch_website_context should return the AI's text verbatim.
    """
    from src.core.website_enricher import fetch_website_context

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_HTML
    mock_response.raise_for_status = MagicMock()

    mock_ai_response = MagicMock()
    mock_ai_response.text = FAKE_AI_RESPONSE

    with patch("httpx.get", return_value=mock_response) as _mock_get, \
         patch("src.core.website_enricher._call_gemini", return_value=FAKE_AI_RESPONSE) as _mock_ai:
        result = fetch_website_context("https://johnsmith.dev")

    assert "## Website:" in result
    assert "EDUCATION" in result
    assert "WORK EXPERIENCE" in result


def test_fetch_website_context_returns_empty_on_http_error():
    """
    If httpx raises an exception (timeout, DNS failure, HTTP 4xx/5xx),
    the function must return "" rather than propagating the error.
    """
    import httpx
    from src.core.website_enricher import fetch_website_context

    with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
        result = fetch_website_context("https://doesnotexist.example.com")

    assert result == ""


def test_fetch_website_context_returns_empty_on_empty_page():
    """
    If the scraped page has no meaningful text (JS-only / blank),
    the function should return "" without calling the AI.
    """
    from src.core.website_enricher import fetch_website_context

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>  </p></body></html>"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        result = fetch_website_context("https://blank.example.com")

    assert result == ""


def test_fetch_website_context_strips_script_tags():
    """
    Script / style content must not reach the AI prompt.
    We verify that _extract_text removes them before calling Gemini.
    """
    from src.core.website_enricher import _extract_text

    dirty_html = """
    <html><head><script>var x = 1;</script><style>.a{color:red}</style></head>
    <body><p>Hello World Education</p></body></html>
    """
    text = _extract_text(dirty_html)
    assert "var x" not in text
    assert "color:red" not in text
    assert "Hello World" in text


def test_fetch_website_context_normalises_url():
    """
    A bare domain like 'johnsmith.dev' should be treated as 'https://johnsmith.dev'.
    """
    from src.core.website_enricher import _normalise_url

    assert _normalise_url("johnsmith.dev").startswith("https://")
    assert _normalise_url("http://johnsmith.dev") == "http://johnsmith.dev"
    assert _normalise_url("https://johnsmith.dev") == "https://johnsmith.dev"

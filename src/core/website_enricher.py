"""
Website Enricher — fetches a personal/portfolio website, strips HTML,
and uses Gemini to extract structured Education and Work Experience blocks
formatted as ledger-compatible text.

Dependencies: httpx (already in requirements), beautifulsoup4 (already in
requirements), google-genai (already in requirements via GEMINI_API_KEY).

Falls back to "" on any network error or missing API key — never raises.
"""
import os
import re

import httpx
from bs4 import BeautifulSoup

_MAX_TEXT_CHARS = 8_000   # cap sent to Gemini to stay well inside token limit
_REQUEST_TIMEOUT = 15     # seconds


def _normalise_url(url: str) -> str:
    """Prepend https:// to bare domains that lack a scheme."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


def _extract_text(html: str) -> str:
    """
    Strip <script>, <style>, and nav/footer noise from HTML and return
    plain-text content suitable for an LLM prompt.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Remove elements that carry no meaningful biography content
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "meta", "link"]):
        tag.decompose()
    # Collect visible text, collapsing whitespace
    text = soup.get_text(separator="\n")
    # Collapse 3+ consecutive blank lines into 2
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


def _call_gemini(text: str) -> str:
    """
    Send the scraped page text to Gemini Flash and ask it to extract
    Education and Work Experience in a ledger-compatible format.

    Returns the raw model text, or "" if the API key is missing / call fails.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return ""

    prompt = (
        "You are a resume data extractor. Below is the plain text of someone's "
        "personal/portfolio website. Extract ONLY factual information — do NOT "
        "invent or infer anything not explicitly stated.\n\n"
        "Return EXACTLY this format (omit any section that has no data):\n\n"
        "## Website:\n\n"
        "EDUCATION\n"
        "<Degree Name>  <start> – <end>\n"
        "<Institution Name>\n"
        "(repeat for each degree)\n\n"
        "WORK EXPERIENCE\n"
        "<Job Title>  <start> – <end>\n"
        "<Company Name>\n"
        "• <one achievement bullet per line>\n"
        "(repeat for each role)\n\n"
        "Rules for dates:\n"
        "- Use three-letter month + year when known (e.g. Jan 2024)\n"
        "- Use year only when month is unknown (e.g. 2024)\n"
        "- Use 'Present' for current roles\n"
        "- If NO date info at all is available for a current role, write '– Present'\n\n"
        "If none of these sections can be found, reply with exactly: NO_DATA\n\n"
        "--- WEBSITE TEXT ---\n"
        f"{text[:_MAX_TEXT_CHARS]}"
    )

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text.strip() if response.text else ""
    except Exception:
        return ""


def fetch_website_context(url: str) -> str:
    """
    Public API — fetch *url*, extract text, ask Gemini to structure it.

    Returns a formatted ledger block (string) ready to be written under a
    ``## Website:`` heading, or "" on any failure.
    """
    url = _normalise_url(url)

    try:
        resp = httpx.get(
            url,
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "TitanSwarm/2.0 (portfolio-enricher)"},
        )
        resp.raise_for_status()
        html = resp.text
    except Exception:
        return ""

    text = _extract_text(html)
    if len(text) < 20:  # page is effectively empty (JS-only, blank, etc.)
        return ""

    result = _call_gemini(text)
    if not result or result.strip() == "NO_DATA":
        return ""

    return result

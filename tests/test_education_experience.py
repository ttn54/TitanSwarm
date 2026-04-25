"""
Tests for the manual Education & Work Experience feature.

Covers:
  1. UserProfile has an `education` field (list of dicts) — not just `experience`
  2. PostgresRepository round-trips education data (save → get)
  3. _build_manual_ledger_section() produces parser-compatible EDUCATION /
     WORK EXPERIENCE text blocks
  4. _merge_structured() correctly merges profile entries with ledger-parsed entries,
     preferring profile data
  5. website_enricher prompt handles entries without dates (Part A)
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import UserProfile


# ─────────────────────────────────────────────────────────────────────────────
# 1. UserProfile model
# ─────────────────────────────────────────────────────────────────────────────

def test_user_profile_has_education_field():
    """UserProfile must accept an `education` list of dicts."""
    pf = UserProfile(
        name="Alex Ng",
        education=[
            {
                "degree": "Bachelor of Science, Computer Science",
                "institution": "UBC",
                "start_date": "Sep 2022",
                "end_date": "Apr 2026",
                "location": "Vancouver, BC",
                "bullets": [],
            }
        ],
    )
    assert len(pf.education) == 1
    assert pf.education[0]["degree"] == "Bachelor of Science, Computer Science"


def test_user_profile_education_defaults_empty():
    """UserProfile education field defaults to []."""
    pf = UserProfile(name="Test User")
    assert pf.education == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. Repository round-trip
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_repository_saves_and_returns_education():
    """save_profile persists education; get_profile returns it."""
    from src.infrastructure.postgres_repo import PostgresRepository

    repo = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await repo.init_db()

    edu = [
        {
            "degree": "BSc Computer Science",
            "institution": "UBC",
            "start_date": "Sep 2022",
            "end_date": "Apr 2026",
            "location": "Vancouver, BC",
            "bullets": [],
        }
    ]
    exp = [
        {
            "title": "Founding Software Engineer",
            "company": "Futurity",
            "start_date": "Jan 2024",
            "end_date": "Present",
            "location": "Remote",
            "bullets": ["Built enterprise AI integrations."],
        }
    ]

    pf = UserProfile(name="Alex Ng", education=edu, experience=exp)
    await repo.save_profile(pf, user_id=1)

    loaded = await repo.get_profile(user_id=1)
    assert loaded is not None
    assert len(loaded.education) == 1
    assert loaded.education[0]["degree"] == "BSc Computer Science"
    assert len(loaded.experience) == 1
    assert loaded.experience[0]["company"] == "Futurity"


# ─────────────────────────────────────────────────────────────────────────────
# 3. _build_manual_ledger_section helper
# ─────────────────────────────────────────────────────────────────────────────

def test_build_manual_ledger_section_produces_education_block():
    """The helper must produce a parseable EDUCATION block with dates."""
    from src.ui.app import _build_manual_ledger_section

    edu = [
        {
            "degree": "BSc Computer Science",
            "institution": "UBC",
            "start_date": "Sep 2022",
            "end_date": "Apr 2026",
            "location": "Vancouver, BC",
            "bullets": [],
        }
    ]
    text = _build_manual_ledger_section(education=edu, experience=[])
    assert "EDUCATION" in text
    assert "BSc Computer Science" in text
    assert "Sep 2022" in text


def test_build_manual_ledger_section_produces_experience_block():
    """The helper must produce a parseable WORK EXPERIENCE block with bullets."""
    from src.ui.app import _build_manual_ledger_section

    exp = [
        {
            "title": "Founding Software Engineer",
            "company": "Futurity",
            "start_date": "Jan 2024",
            "end_date": "Present",
            "location": "Remote",
            "bullets": ["Built enterprise AI integrations.", "Led a team of 3 engineers."],
        }
    ]
    text = _build_manual_ledger_section(education=[], experience=exp)
    assert "WORK EXPERIENCE" in text
    assert "Founding Software Engineer" in text
    assert "Futurity" in text
    assert "• Built enterprise AI" in text


def test_build_manual_ledger_section_empty_inputs():
    """Empty lists produce an empty string — no phantom sections."""
    from src.ui.app import _build_manual_ledger_section

    text = _build_manual_ledger_section(education=[], experience=[])
    assert text.strip() == ""


def test_parse_ledger_two_line_education_keeps_degree_and_institution(tmp_path):
    """2-line education format should parse degree from line 1 and school/date from line 2."""
    from src.ui.app import _parse_ledger_for_pdf

    ledger_text = (
        "EDUCATION\n"
        "Computing Science\n"
        "SFU Sep 2022 - Present\n"
    )
    p = tmp_path / "ledger.md"
    p.write_text(ledger_text, encoding="utf-8")

    parsed = _parse_ledger_for_pdf(str(p))
    assert len(parsed["education"]) == 1
    assert parsed["education"][0]["degree"] == "Computing Science"
    assert parsed["education"][0]["institution"] == "SFU"
    assert parsed["education"][0]["start_date"] == "Sep 2022"
    assert parsed["education"][0]["end_date"] == "Present"


# ─────────────────────────────────────────────────────────────────────────────
# 4. _merge_structured helper
# ─────────────────────────────────────────────────────────────────────────────

def test_merge_structured_profile_takes_priority():
    """Profile entries must come first; ledger entries fill gaps only."""
    from src.ui.app import _merge_structured

    profile_edu = [{"degree": "BSc CS", "institution": "UBC", "start_date": "Sep 2022",
                    "end_date": "Apr 2026", "location": "", "bullets": []}]
    ledger_edu  = [{"degree": "BSc CS", "institution": "UBC", "start_date": "Sep 2022",
                    "end_date": "Apr 2026", "location": "", "bullets": []}]

    result = _merge_structured(profile_edu, ledger_edu)
    # Should deduplicate — only one entry
    assert len(result) == 1


def test_merge_structured_appends_ledger_extras():
    """Ledger entries not in profile should be appended."""
    from src.ui.app import _merge_structured

    profile_edu = [{"degree": "BSc CS", "institution": "UBC", "start_date": "Sep 2022",
                    "end_date": "Apr 2026", "location": "", "bullets": []}]
    ledger_edu  = [{"degree": "Diploma, Web Dev", "institution": "BCIT", "start_date": "Jan 2021",
                    "end_date": "Dec 2021", "location": "", "bullets": []}]

    result = _merge_structured(profile_edu, ledger_edu)
    assert len(result) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 5. website_enricher — undated entries (Part A)
# ─────────────────────────────────────────────────────────────────────────────

def test_website_enricher_handles_undated_response():
    """
    When Gemini returns a WORK EXPERIENCE entry without month dates,
    fetch_website_context should still return the block (not discard it).
    """
    from src.core.website_enricher import fetch_website_context

    UNDATED_RESPONSE = (
        "## Website:\n\n"
        "WORK EXPERIENCE\n"
        "Founding Software Engineer  2024 – Present\n"
        "Futurity\n"
        "• Built enterprise AI deployment pipelines.\n"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><body><p>Founding Software Engineer at Futurity since 2024</p></body></html>"
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_resp), \
         patch("src.core.website_enricher._call_gemini", return_value=UNDATED_RESPONSE):
        result = fetch_website_context("https://example.dev")

    assert "WORK EXPERIENCE" in result
    assert "Futurity" in result

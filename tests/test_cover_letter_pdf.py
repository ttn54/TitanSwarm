"""
TDD tests for structured cover letter generation and PDF rendering.

Tests:
  1. CoverLetterResult model accepts body + address
  2. CoverLetterResult model accepts body with no address (None)
  3. compose_cover_letter_html() renders all formal sections
  4. compose_cover_letter_html() omits address block when address is None
"""
import unittest
from datetime import date

from src.core.models import CoverLetterResult, UserProfile
from src.core.pdf_generator import compose_cover_letter_html


_PROFILE = UserProfile(
    name="Zen Nguyen",
    email="ttn54@sfu.ca",
    phone="(672) 673-2613",
    github="github.com/ttn54",
    linkedin="linkedin.com/in/zennguyen1305",
    website="zennguyen.me",
)

_JOB_COMPANY  = "Absolute Software"
_JOB_ROLE     = "Associate Software Developer, Co-op"
_BODY         = "Dear Hiring Manager,\n\nI am excited to apply.\n\nSincerely,\nZen"
_ADDRESS      = "1055 Dunsmuir St #1400\nVancouver, BC  V7X 1K8"


class TestCoverLetterResultModel(unittest.TestCase):

    def test_accepts_body_and_address(self):
        result = CoverLetterResult(body=_BODY, company_address=_ADDRESS)
        self.assertEqual(result.body, _BODY)
        self.assertEqual(result.company_address, _ADDRESS)

    def test_accepts_body_without_address(self):
        result = CoverLetterResult(body=_BODY, company_address=None)
        self.assertEqual(result.body, _BODY)
        self.assertIsNone(result.company_address)


class TestComposeCoverLetterHtml(unittest.TestCase):

    def test_html_contains_all_formal_sections(self):
        result = CoverLetterResult(body=_BODY, company_address=_ADDRESS)
        html = compose_cover_letter_html(
            profile=_PROFILE,
            company=_JOB_COMPANY,
            role=_JOB_ROLE,
            cover_letter=result,
            letter_date=date(2026, 4, 8),
        )
        self.assertIn("Zen Nguyen",              html)   # candidate name header
        self.assertIn("ttn54@sfu.ca",            html)   # contact line
        self.assertIn("April 8, 2026",           html)   # formatted date
        self.assertIn("Hiring Manager",          html)   # salutation target
        self.assertIn("Absolute Software",       html)   # recipient company
        self.assertIn("1055 Dunsmuir",           html)   # address line
        self.assertIn("Associate Software Developer", html)  # Re: subject
        self.assertIn("I am excited to apply",   html)   # body text

    def test_html_omits_address_block_when_none(self):
        result = CoverLetterResult(body=_BODY, company_address=None)
        html = compose_cover_letter_html(
            profile=_PROFILE,
            company=_JOB_COMPANY,
            role=_JOB_ROLE,
            cover_letter=result,
            letter_date=date(2026, 4, 8),
        )
        # Address placeholders must not be present
        self.assertNotIn("1055 Dunsmuir", html)
        # But company name and other sections should still be there
        self.assertIn("Absolute Software", html)
        self.assertIn("Zen Nguyen",        html)


if __name__ == "__main__":
    unittest.main()

"""
Tests for Phase A resume template fixes:
1. h2 headings must NOT use font-variant: small-caps or letter-spacing > 0.05em
2. Skills lines must have bullet (•) prefix before each category
3. Contact line must include website when provided
4. Langara College renders as inline bullet (already works — regression guard)
"""
import pytest
import os
from jinja2 import Environment, FileSystemLoader
from src.core.models import TailoredApplication, TailoredProject, TailoredExperience
from src.core.pdf_generator import _md_bold


@pytest.fixture
def template_env():
    """Real Jinja2 environment pointing at the actual resume template."""
    tmpl_dir = os.path.join(os.path.dirname(__file__), "..", "src", "core", "templates")
    env = Environment(loader=FileSystemLoader(tmpl_dir))
    env.filters["mdbold"] = _md_bold
    return env


@pytest.fixture
def sample_personal_info():
    return {
        "name": "Zen Nguyen",
        "email": "ttn54@sfu.ca",
        "phone": "(672) 673-2613",
        "linkedin": "linkedin.com/in/zennguyen1305",
        "github": "github.com/ttn54",
        "website": "zennguyen.me",
    }


@pytest.fixture
def sample_personal_info_no_website():
    return {
        "name": "Zen Nguyen",
        "email": "ttn54@sfu.ca",
        "phone": "(672) 673-2613",
        "linkedin": "linkedin.com/in/zennguyen1305",
        "github": "github.com/ttn54",
    }


@pytest.fixture
def sample_ai_data():
    return TailoredApplication(
        job_id="test123",
        skills_to_highlight={
            "Languages": ["Python", "Go", "Java"],
            "Backend & Systems": ["FastAPI", "gRPC"],
        },
        tailored_projects=[
            TailoredProject(
                title="TitanSwarm",
                tech="Python, Go",
                date="Jan 2026 – Present",
                project_type="Personal Project",
                bullets=["Built an **autonomous** AI co-pilot."],
            )
        ],
        tailored_experience=[
            TailoredExperience(
                title="Server",
                company="Pho Goodness",
                start_date="Jan 2024",
                end_date="Present",
                location="Burnaby, BC",
                bullets=["Maintained 3.74 GPA."],
            )
        ],
    )


@pytest.fixture
def sample_ledger_with_langara():
    return {
        "personal_info": {
            "name": "Zen Nguyen",
            "email": "ttn54@sfu.ca",
            "phone": "(672) 673-2613",
            "linkedin": "linkedin.com/in/zennguyen1305",
            "github": "github.com/ttn54",
            "website": "zennguyen.me",
        },
        "education": [
            {
                "institution": "Simon Fraser University",
                "degree": "Bachelor of Science, Computing Science",
                "start_date": "May 2025",
                "end_date": "Present",
                "location": "",
                "bullets": [
                    "CGPA: 3.74 / 4.33",
                    "Langara College | Associate of Science, Computer Science Jan 2024 – Apr 2025",
                ],
            }
        ],
        "experience": [],
    }


def _render(env, personal_info, ai_data, ledger_extra=None):
    """Helper to render the resume template and return HTML string."""
    template = env.get_template("resume.html")
    ledger = {"personal_info": personal_info, "education": [], "experience": []}
    if ledger_extra:
        ledger.update(ledger_extra)
    return template.render(personal_info=personal_info, ledger=ledger, ai_data=ai_data)


# ── Test 1: h2 CSS must not have font-variant: small-caps ──
class TestHeadingCSS:
    def test_no_small_caps_in_css(self, template_env, sample_personal_info, sample_ai_data):
        html = _render(template_env, sample_personal_info, sample_ai_data)
        assert "font-variant: small-caps" not in html, (
            "h2 must not use font-variant: small-caps — Playwright renders it as garbled text"
        )

    def test_letter_spacing_not_excessive(self, template_env, sample_personal_info, sample_ai_data):
        html = _render(template_env, sample_personal_info, sample_ai_data)
        assert "letter-spacing: 0.12em" not in html, (
            "h2 letter-spacing must not be 0.12em — causes 'T e c h n i c a l' garbled output"
        )


# ── Test 2: Skills lines must have • bullet prefix ──
class TestSkillsBulletPrefix:
    def test_skills_lines_have_bullet_marker(self, template_env, sample_personal_info, sample_ai_data):
        html = _render(template_env, sample_personal_info, sample_ai_data)
        # Each skills category line should have a bullet marker
        assert "•" in html or "&#8226;" in html or "&bull;" in html, (
            "Skills lines must include • bullet prefix before category name"
        )
        # Specifically: "• Languages:" should appear
        has_bullet_prefix = (
            "•&nbsp;<strong>Languages</strong>" in html
            or "• <strong>Languages</strong>" in html
            or "&bull;&nbsp;<strong>Languages</strong>" in html
            or "•&nbsp;<strong>Languages:</strong>" in html
            or "• <strong>Languages:</strong>" in html
        )
        assert has_bullet_prefix, (
            "Each skills category must be prefixed with • bullet marker"
        )


# ── Test 3: Contact line must include website when provided ──
class TestContactLineWebsite:
    def test_website_appears_in_contact(self, template_env, sample_personal_info, sample_ai_data):
        html = _render(template_env, sample_personal_info, sample_ai_data)
        assert "zennguyen.me" in html, (
            "Website must appear in the contact line when personal_info.website is set"
        )

    def test_no_crash_without_website(self, template_env, sample_personal_info_no_website, sample_ai_data):
        """Template must not crash if website is not provided."""
        html = _render(template_env, sample_personal_info_no_website, sample_ai_data)
        assert "Zen Nguyen" in html  # basic render check


# ── Test 4: Langara renders as inline bullet under SFU (regression guard) ──
class TestLangaraInlineBullet:
    def test_langara_as_bullet_not_separate_entry(self, template_env, sample_ai_data, sample_ledger_with_langara):
        template = template_env.get_template("resume.html")
        html = template.render(
            personal_info=sample_ledger_with_langara["personal_info"],
            ledger=sample_ledger_with_langara,
            ai_data=sample_ai_data,
        )
        # Langara should appear exactly once, inside a <li> (a bullet point), NOT as a top-level entry-title
        assert "Langara College" in html
        # It should NOT be in an entry-title span (meaning it's a separate section)
        assert '<span class="entry-title">Langara' not in html, (
            "Langara must not be a separate education entry — it should be an inline bullet"
        )


class TestEducationRenderPriority:
    def test_template_prefers_ai_tailored_education(self, template_env, sample_personal_info, sample_ai_data):
        ai_with_edu = sample_ai_data.model_copy(update={
            "tailored_education": [
                {
                    "degree": "Computer Science",
                    "institution": "SFU",
                    "start_date": "Sep 2022",
                    "end_date": "Present",
                    "location": "",
                    "bullets": ["Completed systems and algorithms coursework relevant to backend roles."],
                }
            ]
        })
        ledger = {
            "education": [
                {
                    "degree": "Old Degree",
                    "institution": "Old School",
                    "start_date": "Jan 2020",
                    "end_date": "Jan 2021",
                    "location": "",
                    "bullets": [],
                }
            ],
            "experience": [],
        }
        html = _render(template_env, sample_personal_info, ai_with_edu, ledger_extra=ledger)
        assert "Computer Science" in html
        assert "SFU" in html
        assert "Old Degree" not in html

    def test_template_falls_back_to_ledger_education_when_ai_empty(self, template_env, sample_personal_info, sample_ai_data):
        ai_no_edu = sample_ai_data.model_copy(update={"tailored_education": []})
        ledger = {
            "education": [
                {
                    "degree": "Computer Science",
                    "institution": "SFU",
                    "start_date": "Sep 2022",
                    "end_date": "Present",
                    "location": "",
                    "bullets": [],
                }
            ],
            "experience": [],
        }
        html = _render(template_env, sample_personal_info, ai_no_edu, ledger_extra=ledger)
        assert "Computer Science" in html
        assert "SFU" in html


class TestResumeStructureOrder:
    def test_section_order_is_skills_work_projects_education(self, template_env, sample_personal_info, sample_ai_data):
        ai_with_edu = sample_ai_data.model_copy(update={
            "tailored_education": [
                {
                    "degree": "Computer Science",
                    "institution": "SFU",
                    "start_date": "Sep 2022",
                    "end_date": "Present",
                    "location": "",
                    "bullets": [],
                }
            ]
        })
        html = _render(template_env, sample_personal_info, ai_with_edu)

        i_skills = html.index("Technical Skills")
        i_work = html.index("Work Experience")
        i_projects = html.index("Technical Projects")
        i_edu = html.index("Education")

        assert i_skills < i_work < i_projects < i_edu


class TestHeaderRows:
    def test_contact_is_split_across_two_rows(self, template_env, sample_personal_info, sample_ai_data):
        html = _render(template_env, sample_personal_info, sample_ai_data)
        assert 'class="contact-row contact-row-1"' in html
        assert 'class="contact-row contact-row-2"' in html

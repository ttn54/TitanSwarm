"""
Tests for Part B — Work Experience section in the resume PDF.

Covers:
  1. The resume.html template renders a "Work Experience" section when
     ai_data.tailored_experience is non-empty
  2. The template renders Work Experience from ledger.experience when
     ai_data.tailored_experience is empty (fallback)
  3. No Work Experience section is rendered when both are empty
  4. Bullet points from tailored_experience appear in the rendered HTML
  5. AI system prompt no longer hard-codes "leave tailored_experience empty"
"""
import pytest
from jinja2 import Environment, FileSystemLoader, BaseLoader, DictLoader
import os

from src.core.models import TailoredApplication, TailoredProject, TailoredExperience
from src.core.pdf_generator import _md_bold


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_resume_template() -> str:
    """Read the real resume.html from disk."""
    template_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "core", "templates", "resume.html"
    )
    with open(template_path, encoding="utf-8") as f:
        return f.read()


def _render(personal_info: dict, ledger: dict, ai_data: TailoredApplication) -> str:
    """Render resume.html with the given context and return HTML string."""
    template_dir = os.path.join(
        os.path.dirname(__file__), "..", "src", "core", "templates"
    )
    env = Environment(loader=FileSystemLoader(template_dir))
    env.filters["mdbold"] = _md_bold
    tmpl = env.get_template("resume.html")
    return tmpl.render(personal_info=personal_info, ledger=ledger, ai_data=ai_data)


_BASE_PI = {"name": "Alex Ng", "email": "alex@example.com",
            "phone": "", "linkedin": "", "github": "", "website": ""}

_BASE_AI = TailoredApplication(
    job_id="j1",
    skills_to_highlight={"Languages": ["Go", "TypeScript"]},
    tailored_projects=[],
    tailored_experience=[],
    q_and_a_responses={},
)

_EXP_ENTRY = TailoredExperience(
    title="Founding Software Engineer",
    company="Futurity",
    start_date="Jan 2024",
    end_date="Present",
    location="Remote",
    bullets=["Built enterprise AI deployment pipelines using **gRPC** and Docker."],
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. tailored_experience renders Work Experience section
# ─────────────────────────────────────────────────────────────────────────────

def test_template_renders_work_experience_from_ai_data():
    """When tailored_experience is non-empty, Work Experience section must appear."""
    ai = _BASE_AI.model_copy(update={"tailored_experience": [_EXP_ENTRY]})
    html = _render(_BASE_PI, {"education": [], "experience": []}, ai)

    assert "Work Experience" in html
    assert "Founding Software Engineer" in html
    assert "Futurity" in html


# ─────────────────────────────────────────────────────────────────────────────
# 2. ledger.experience fallback when tailored_experience is empty
# ─────────────────────────────────────────────────────────────────────────────

def test_template_renders_work_experience_from_ledger_fallback():
    """
    When tailored_experience is empty but ledger.experience has entries,
    the template should still render the Work Experience section.
    """
    ledger_exp = [
        {
            "title": "Founding Software Engineer",
            "company": "Futurity",
            "start_date": "Jan 2024",
            "end_date": "Present",
            "location": "Remote",
            "bullets": ["Built enterprise AI deployment pipelines."],
        }
    ]
    html = _render(_BASE_PI, {"education": [], "experience": ledger_exp}, _BASE_AI)

    assert "Work Experience" in html
    assert "Founding Software Engineer" in html
    assert "Futurity" in html


# ─────────────────────────────────────────────────────────────────────────────
# 3. No section when both sources are empty
# ─────────────────────────────────────────────────────────────────────────────

def test_template_omits_work_experience_when_both_empty():
    """No Work Experience heading should appear when there is no experience data."""
    html = _render(_BASE_PI, {"education": [], "experience": []}, _BASE_AI)
    assert "Work Experience" not in html


# ─────────────────────────────────────────────────────────────────────────────
# 4. Bullet points appear in rendered HTML
# ─────────────────────────────────────────────────────────────────────────────

def test_template_renders_experience_bullets():
    """Bullet text from tailored_experience must appear in the HTML."""
    ai = _BASE_AI.model_copy(update={"tailored_experience": [_EXP_ENTRY]})
    html = _render(_BASE_PI, {"education": [], "experience": []}, ai)
    assert "Built enterprise AI deployment pipelines" in html


# ─────────────────────────────────────────────────────────────────────────────
# 5. AI prompt no longer hard-codes "leave tailored_experience empty"
# ─────────────────────────────────────────────────────────────────────────────

def test_ai_prompt_does_not_force_empty_tailored_experience():
    """
    The AITailor system prompt must not contain the instruction that hard-codes
    tailored_experience as always empty. The old phrase was
    'leave this array empty — work experience is not included on this resume'.
    """
    import inspect
    from src.core import ai as ai_module
    source = inspect.getsource(ai_module)
    assert "leave this array empty" not in source, (
        "The AI prompt still hard-codes tailored_experience to empty. "
        "Remove that instruction so real experience entries are tailored."
    )

import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from src.core.models import Job, JobStatus, TailoredApplication, TailoredProject, TailoredExperience
from src.core.ai import AITailor
from src.core.ledger import LedgerManager

@pytest.fixture
def sample_job():
    return Job(
        id="job_999",
        company="Google",
        role="Software Engineer Intern",
        status=JobStatus.DISCOVERED,
        job_description="We are looking for Python and Distributed Systems experience.",
        required_skills=["Python", "Go"],
        custom_questions=["Why do you want to work here?"],
        url="https://google.com/jobs/999"
    )

def test_missing_api_key_raises_error():
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=True):
        mock_ledger = MagicMock(spec=LedgerManager)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            AITailor(ledger_manager=mock_ledger)

@pytest.mark.asyncio
async def test_ai_tailor_returns_structured_output(sample_job):
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake_test_key"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = "data/ledger.md"
        mock_ledger.search_facts.return_value = [
            "Zen wrote TitanSwarm in Python.",
            "Zen built TitanStore with Go."
        ]

        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

        mock_response = TailoredApplication(
            job_id="job_999",
            skills_to_highlight={
                "Languages": ["Python", "Go"],
                "Backend & Systems": ["Distributed Systems", "FAISS"],
            },
            tailored_projects=[
                TailoredProject(
                    title="TitanStore",
                    tech="Go, SQL, Docker",
                    date="Jan 2026 – Present",
                    project_type="Personal Project",
                    bullets=[
                        "Built distributed KV store in Go using Raft consensus.",
                        "Applied TDD with go test -race for thread safety.",
                    ]
                )
            ],
            tailored_experience=[
                TailoredExperience(
                    title="Server",
                    company="Pho Goodness Restaurant",
                    start_date="Jan 2024",
                    end_date="Present",
                    location="Burnaby, BC",
                    bullets=["Demonstrated high work ethic maintaining 3.74 GPA while working 20+ hrs/week."],
                )
            ],
            q_and_a_responses={"Why do you want to work here?": "I love distributed systems."}
        )

        with patch.object(tailor, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            result = await tailor.tailor_application(sample_job)

            assert isinstance(result, TailoredApplication)
            assert result.job_id == "job_999"
            assert len(result.tailored_projects) == 1
            assert result.tailored_projects[0].title == "TitanStore"
            assert result.tailored_projects[0].project_type == "Personal Project"
            assert isinstance(result.skills_to_highlight, dict)
            assert len(result.skills_to_highlight) >= 1
            assert len(result.tailored_experience) == 1
            assert result.tailored_experience[0].title == "Server"
            assert "summary" not in TailoredApplication.model_fields
            mock_call.assert_called_once()


# ── Prompt-content tests ─────────────────────────────────────────────────────

def _make_tailor(tmp_path):
    """Helper: build an AITailor with all external calls mocked out."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            return AITailor(ledger_manager=mock_ledger)


def _blank_result(job_id: str) -> TailoredApplication:
    return TailoredApplication(
        job_id=job_id, skills_to_highlight={},
        tailored_projects=[], tailored_experience=[], q_and_a_responses={},
    )


async def _capture_system_prompt(tailor: AITailor, job: Job) -> str:
    """Run tailor_application and return the system_prompt that was built."""
    captured: dict = {}

    async def _spy(system_prompt: str, user_prompt: str) -> TailoredApplication:
        captured["system"] = system_prompt
        return _blank_result(job.id)

    with patch.object(tailor, "_call_llm", side_effect=_spy):
        await tailor.tailor_application(job)
    return captured["system"]


@pytest.mark.asyncio
async def test_system_prompt_contains_skill_taxonomy(tmp_path, sample_job):
    """Skills section must reference a broad taxonomy — not just Frontend vs Backend."""
    tailor = _make_tailor(tmp_path)
    system = await _capture_system_prompt(tailor, sample_job)

    # Taxonomy must cover at minimum these four domains beyond Frontend/Backend
    assert "Mobile" in system,               "Taxonomy must include Mobile Development"
    assert "DevOps" in system or "Infrastructure" in system, \
                                              "Taxonomy must include DevOps/Infrastructure"
    assert "Machine Learning" in system or "AI &" in system, \
                                              "Taxonomy must include AI/ML"
    assert "Data Engineering" in system or "Data Pipeline" in system, \
                                              "Taxonomy must include Data Engineering"

    # Old binary hard-coding must be gone
    assert "Frontend JD → create a 'Frontend' category (not 'Backend & Systems')" not in system
    assert "Backend JD → create 'Backend & Systems'. Full-stack → both." not in system


@pytest.mark.asyncio
async def test_system_prompt_uses_keyword_overlap_for_project_scoring(tmp_path, sample_job):
    """Project selection must use JD keyword-overlap scoring, not binary domain routing."""
    tailor = _make_tailor(tmp_path)
    system = await _capture_system_prompt(tailor, sample_job)

    # Must mention keyword / overlap scoring
    assert "keyword" in system.lower() or "overlap" in system.lower(), \
        "Project scoring must reference keyword-overlap, not binary domain rules"

    # Old binary routing lines must be gone
    assert "Frontend JD (Vue/React/TypeScript) → pick frontend/TypeScript repos" not in system
    assert "Backend JD (Go/distributed) → pick systems repos, exclude pure-frontend repos" not in system


@pytest.mark.asyncio
async def test_user_prompt_uses_keyword_overlap_for_project_scoring(tmp_path, sample_job):
    """User prompt must also use keyword-overlap language for project scoring."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    captured: dict = {}

    async def _spy(system_prompt: str, user_prompt: str) -> TailoredApplication:
        captured["user"] = user_prompt
        return _blank_result(sample_job.id)

    with patch.object(tailor, "_call_llm", side_effect=_spy):
        await tailor.tailor_application(sample_job)

    user = captured["user"]
    assert "keyword" in user.lower() or "overlap" in user.lower(), \
        "User prompt must reference keyword-overlap for project scoring"
    assert "Frontend/TypeScript/Vue JD → exclude Go/distributed/systems repos" not in user
    assert "Backend/Go/systems JD → exclude pure frontend repos" not in user


# ──────────────────────────────────────────────────────────────────────────────
# Gap 2 — _parse_ledger_as_resume must always include GitHub Projects section
# ──────────────────────────────────────────────────────────────────────────────
from src.core.ai import _parse_ledger_as_resume


def test_parse_ledger_returns_github_section_when_before_resume_marker(tmp_path):
    """
    If ## GitHub Projects: appears BEFORE ## Imported Resume:, the GitHub block
    must still be present in the returned context — not silently dropped.

    This is the new-user failure mode: GitHub Refresh runs first, then PDF upload.
    The marker-based split discards everything before '## Imported Resume:',
    including the GitHub section, so the AI gets zero project context.
    """
    ledger = (
        "## Technical Skills\n* Python, Go\n\n"
        "## GitHub Projects:\n### QuantumRepo\nQuantum computing framework.\n\n"
        "## Imported Resume: resume.pdf\n\n"
        "Zen Nguyen\nzen@sfu.ca\n"
    )
    path = tmp_path / "ledger.md"
    path.write_text(ledger)

    result = _parse_ledger_as_resume(str(path))

    assert "QuantumRepo" in result, (
        "_parse_ledger_as_resume must include GitHub Projects even when they appear "
        "before the ## Imported Resume: marker"
    )
    assert "Zen Nguyen" in result, "Imported resume text must still be present"


def test_parse_ledger_returns_github_section_when_after_resume_marker(tmp_path):
    """
    If ## GitHub Projects: appears AFTER ## Imported Resume: (the normal layout
    after a refresh-then-upload sequence), the section must be included.
    This verifies the happy-path still works after the fix.
    """
    ledger = (
        "## Technical Skills\n* Python, Go\n\n"
        "## Imported Resume: resume.pdf\n\n"
        "Zen Nguyen\nzen@sfu.ca\n\n"
        "## GitHub Projects:\n### QuantumRepo\nQuantum computing framework.\n"
    )
    path = tmp_path / "ledger.md"
    path.write_text(ledger)

    result = _parse_ledger_as_resume(str(path))

    assert "QuantumRepo" in result
    assert "Zen Nguyen" in result


# ──────────────────────────────────────────────────────────────────────────────
# Bullet trim: projects with <= 2 keyword matches must be trimmed to 2 bullets
# ──────────────────────────────────────────────────────────────────────────────

def _make_project(title: str, overlap: int, n_bullets: int) -> TailoredProject:
    return TailoredProject(
        title=title,
        tech="Python",
        date="Jan 2026",
        bullets=[f"Bullet {i}" for i in range(n_bullets)],
        keyword_overlap_count=overlap,
    )


def _blank_result_with_projects(job_id: str, projects: list) -> TailoredApplication:
    return TailoredApplication(
        job_id=job_id,
        skills_to_highlight={"Languages": ["Python"]},
        tailored_projects=projects,
        tailored_experience=[],
    )


@pytest.mark.asyncio
async def test_non_top_low_overlap_project_trimmed_to_two_bullets(tmp_path, sample_job):
    """Non-top projects (rank 2nd or 3rd) with keyword_overlap_count <= 2 must be trimmed to 2 bullets."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    high = _make_project("HighMatch", overlap=5, n_bullets=4)
    low  = _make_project("LowMatch",  overlap=1, n_bullets=4)
    mocked_result = _blank_result_with_projects(sample_job.id, [high, low])

    with patch.object(tailor, "_call_llm", return_value=mocked_result):
        result = await tailor.tailor_application(sample_job)

    # high comes first (sorted by overlap desc), low is second → trimmed
    assert result.tailored_projects[0].title == "HighMatch"
    assert result.tailored_projects[1].title == "LowMatch"
    assert len(result.tailored_projects[1].bullets) == 2, (
        "Non-top project with overlap=1 must be trimmed to 2 bullets"
    )


@pytest.mark.asyncio
async def test_top_project_keeps_all_bullets_regardless_of_overlap(tmp_path, sample_job):
    """The top-ranked project must always keep all 4 bullets, even when overlap is low."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    low_a = _make_project("LowA", overlap=2, n_bullets=4)
    low_b = _make_project("LowB", overlap=1, n_bullets=4)
    mocked_result = _blank_result_with_projects(sample_job.id, [low_a, low_b])

    with patch.object(tailor, "_call_llm", return_value=mocked_result):
        result = await tailor.tailor_application(sample_job)

    # LowA has higher overlap → sorted first → keeps all 4 bullets
    assert result.tailored_projects[0].title == "LowA"
    assert len(result.tailored_projects[0].bullets) == 4, (
        "Top project must always keep all 4 bullets regardless of overlap count"
    )


@pytest.mark.asyncio
async def test_high_overlap_projects_keep_four_bullets(tmp_path, sample_job):
    """Projects with keyword_overlap_count >= 3 must keep all 4 bullets."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    high_overlap_project = _make_project("HighMatch", overlap=3, n_bullets=4)
    mocked_result = _blank_result_with_projects(sample_job.id, [high_overlap_project])

    with patch.object(tailor, "_call_llm", return_value=mocked_result):
        result = await tailor.tailor_application(sample_job)

    assert len(result.tailored_projects[0].bullets) == 4, (
        "A project with keyword_overlap_count=3 must keep all 4 bullets"
    )


@pytest.mark.asyncio
async def test_system_prompt_forbids_skills_not_in_context(tmp_path, sample_job):
    """System prompt must explicitly forbid listing skills that are not in the candidate context."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    captured: dict = {}

    async def _spy(system_prompt: str, user_prompt: str) -> TailoredApplication:
        captured["system"] = system_prompt
        return _blank_result(sample_job.id)

    with patch.object(tailor, "_call_llm", side_effect=_spy):
        await tailor.tailor_application(sample_job)

    system = captured["system"].lower()
    assert "skills_to_highlight" in system and (
        "only" in system or "forbidden" in system or "must not" in system or "context" in system
    ), "System prompt must guard skills_to_highlight to context-only skills"
    assert "missing_skills" in captured["system"], (
        "System prompt must instruct LLM to populate missing_skills field"
    )


@pytest.mark.asyncio
async def test_system_prompt_allows_imported_resume_projects_as_fallback(tmp_path, sample_job):
    """System prompt must allow projects from the imported resume section when GitHub has few matches."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    captured: dict = {}

    async def _spy(system_prompt: str, user_prompt: str) -> TailoredApplication:
        captured["system"] = system_prompt
        return _blank_result(sample_job.id)

    with patch.object(tailor, "_call_llm", side_effect=_spy):
        await tailor.tailor_application(sample_job)

    system = captured["system"].lower()
    assert "imported resume" in system or "technical projects" in system, (
        "System prompt must allow projects from the imported resume section as a fallback source"
    )

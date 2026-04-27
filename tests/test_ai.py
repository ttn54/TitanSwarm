import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from src.core.models import Job, JobStatus, TailoredApplication, TailoredProject, TailoredExperience
from src.core.ai import AITailor, _merge_skill_categories, _deduplicate_languages, _filter_missing_skills, _recommended_course_hints
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


def test_recommended_course_hints_for_backend_role():
    job = Job(
        id="b1",
        company="BackendCo",
        role="Backend Software Engineer",
        status=JobStatus.DISCOVERED,
        job_description="Build APIs, distributed systems, and database services.",
        url="https://example.com/backend",
    )
    hints = _recommended_course_hints(job)
    assert any("Computer Systems" in h for h in hints)
    assert any("Data Structures" in h for h in hints)


@pytest.mark.asyncio
async def test_system_prompt_contains_sfu_course_hints_for_backend_job(tmp_path):
    job = Job(
        id="b2",
        company="BackendCo",
        role="Backend Software Engineer",
        status=JobStatus.DISCOVERED,
        job_description="Design APIs and distributed backend services.",
        url="https://example.com/backend2",
    )
    tailor = _make_tailor(tmp_path)
    system = await _capture_system_prompt(tailor, job)
    assert "Approved SFU coursework hints" in system
    assert "Computer Systems" in system


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


@pytest.mark.asyncio
async def test_json_schema_hint_includes_keyword_overlap_count(tmp_path, sample_job):
    """The JSON schema hint sent to Gemini must include the keyword_overlap_count field
    so the LLM knows to populate it (Pydantic defaults to 0 if the field is absent)."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    captured: dict = {}

    async def _spy(system_prompt: str, user_prompt: str) -> TailoredApplication:
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return _blank_result(sample_job.id)

    with patch.object(tailor, "_call_llm", side_effect=_spy):
        await tailor.tailor_application(sample_job)

    # The JSON schema is appended to the user_prompt in _call_gemini, but
    # tailor_application calls _call_llm (the mock), not _call_gemini directly.
    # Verify the field is in the Gemini JSON schema by instantiating tailor
    # and inspecting the _call_gemini source path via the json_schema variable.
    # We test this by calling _call_gemini directly with a mock client.
    import inspect
    source = inspect.getsource(tailor._call_gemini)
    assert "keyword_overlap_count" in source, (
        "The JSON schema hint in _call_gemini must include 'keyword_overlap_count' "
        "so the LLM populates it instead of the Pydantic default of 0."
    )


@pytest.mark.asyncio
async def test_json_schema_hint_includes_missing_skills(tmp_path, sample_job):
    """The JSON schema hint sent to Gemini must include the missing_skills field
    so the LLM knows to list JD-only skills there instead of hallucinating them
    into skills_to_highlight."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    import inspect
    source = inspect.getsource(tailor._call_gemini)
    assert "missing_skills" in source, (
        "The JSON schema hint in _call_gemini must include 'missing_skills' "
        "so the LLM routes JD-only skills there instead of skills_to_highlight."
    )


@pytest.mark.asyncio
async def test_system_prompt_step_b_covers_technical_projects_section(tmp_path, sample_job):
    """STEP B of the project scoring instructions must mention both GitHub Projects
    AND the TECHNICAL PROJECTS section of the imported resume, so that projects like
    Gridlock Casino (Java/JUnit) that live only in the imported resume are scored."""
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
    assert "technical projects" in system and "github projects" in system, (
        "STEP B must score projects from BOTH '## GitHub Projects:' AND the "
        "'TECHNICAL PROJECTS' section of the imported resume."
    )


# ─────────────────────────────────────────────────────────────────────────────
# _merge_skill_categories unit tests
# ─────────────────────────────────────────────────────────────────────────────

def test_merge_skill_categories_within_cap_unchanged():
    """If there are already 4 or fewer categories, nothing is merged."""
    skills = {
        "Languages": ["Python", "Java"],
        "AI & Data": ["LangChain"],
        "Infrastructure & DevOps": ["Docker"],
        "Backend & Systems": ["RESTful APIs"],
    }
    result = _merge_skill_categories(skills, max_categories=4)
    assert len(result) == 4


def test_merge_skill_categories_reduces_to_cap():
    """When LLM returns > 4 categories, _merge_skill_categories reduces them to <= 4."""
    skills = {
        "Languages": ["Python", "Java"],
        "AI & Data": ["LangChain"],
        "Infrastructure & DevOps": ["Docker"],
        "Backend & Systems": ["RESTful APIs"],
        "Cloud & Services": ["AWS"],
        "Databases": ["PostgreSQL"],
        "Testing & Validation": ["Pytest"],
    }
    result = _merge_skill_categories(skills, max_categories=4)
    assert len(result) <= 4


def test_merge_cloud_into_infrastructure():
    """'Cloud & Services' skills must be merged into 'Infrastructure & DevOps'."""
    skills = {
        "Languages": ["Python"],
        "Infrastructure & DevOps": ["Docker"],
        "Cloud & Services": ["AWS"],
        "Backend & Systems": ["RESTful APIs"],
        "AI & Data": ["LangChain"],
    }
    result = _merge_skill_categories(skills, max_categories=4)
    assert "Cloud & Services" not in result
    infra = result.get("Infrastructure & DevOps", [])
    assert "AWS" in infra


def test_merge_databases_into_backend():
    """'Databases' skills must be merged into 'Backend & Systems'."""
    skills = {
        "Languages": ["Python"],
        "Infrastructure & DevOps": ["Docker"],
        "Backend & Systems": ["RESTful APIs"],
        "Databases": ["PostgreSQL", "MongoDB"],
        "AI & Data": ["LangChain"],
    }
    result = _merge_skill_categories(skills, max_categories=4)
    assert "Databases" not in result
    backend = result.get("Backend & Systems", [])
    assert "PostgreSQL" in backend
    assert "MongoDB" in backend


def test_languages_category_preserved():
    """'Languages' category must always survive the merge — never eliminated."""
    skills = {
        "Languages": ["Python", "Java", "C++", "Go"],
        "AI & Data": ["LangChain"],
        "Infrastructure & DevOps": ["Docker"],
        "Backend & Systems": ["RESTful APIs"],
        "Cloud & Services": ["AWS"],
        "Databases": ["PostgreSQL"],
        "Testing & Validation": ["Pytest"],
    }
    result = _merge_skill_categories(skills, max_categories=4)
    assert "Languages" in result


def test_system_prompt_languages_rule(tmp_path, sample_job):
    """System prompt must instruct the LLM to include ALL languages from context,
    not only JD-relevant ones."""
    with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake"}):
        mock_ledger = MagicMock(spec=LedgerManager)
        mock_ledger.ledger_path = str(tmp_path / "ledger.md")
        (tmp_path / "ledger.md").write_text("## Technical Skills\n* Python\n")
        with patch("google.genai.Client"):
            tailor = AITailor(ledger_manager=mock_ledger)

    import inspect
    source = inspect.getsource(tailor._call_gemini)
    source_lower = source.lower()
    assert "all" in source_lower and "language" in source_lower, (
        "System prompt must instruct LLM to list ALL languages from context."
    )


# ─────────────────────────────────────────────────────────────────────────────
# _deduplicate_languages unit tests
# ─────────────────────────────────────────────────────────────────────────────

def test_deduplicate_removes_language_from_other_category():
    """If Python appears in both Languages and Backend & Systems,
    it must be removed from Backend & Systems."""
    skills = {
        "Languages": ["Python", "Java", "Go"],
        "Backend & Systems": ["Python", "FastAPI", "RESTful APIs"],
    }
    result = _deduplicate_languages(skills)
    assert "Python" not in result["Backend & Systems"]
    assert "Python" in result["Languages"]


def test_deduplicate_keeps_non_language_skills_in_their_category():
    """Skills that are NOT in Languages must stay in their category."""
    skills = {
        "Languages": ["Python", "Java"],
        "Backend & Systems": ["FastAPI", "gRPC"],
    }
    result = _deduplicate_languages(skills)
    assert "FastAPI" in result["Backend & Systems"]
    assert "gRPC" in result["Backend & Systems"]


def test_deduplicate_removes_empty_categories_after_dedup():
    """If dedup empties a non-Languages category, it must be dropped."""
    skills = {
        "Languages": ["Python"],
        "Some Other": ["Python"],   # entirely a duplicate
    }
    result = _deduplicate_languages(skills)
    assert "Some Other" not in result


def test_deduplicate_preserves_languages_category_unchanged():
    """Languages category itself must never be modified by dedup."""
    skills = {
        "Languages": ["Python", "Java", "C++", "Go"],
        "Backend & Systems": ["Python", "FastAPI"],
    }
    result = _deduplicate_languages(skills)
    assert result["Languages"] == ["Python", "Java", "C++", "Go"]


# ─────────────────────────────────────────────────────────────────────────────
# _filter_missing_skills unit tests
# ─────────────────────────────────────────────────────────────────────────────

def test_filter_missing_skills_removes_skill_present_in_context():
    """Java is in the resume context → must NOT appear in missing_skills."""
    context = "Languages: Python, Go, Java, C, C++, TypeScript"
    missing = ["Ansible", "Java", "K8S"]
    result = _filter_missing_skills(missing, context)
    assert "Java" not in result


def test_filter_missing_skills_keeps_truly_absent_skills():
    """Ansible is NOT in the context → must stay in missing_skills."""
    context = "Languages: Python, Go, Java, Docker"
    missing = ["Ansible", "K8S", "MySQL"]
    result = _filter_missing_skills(missing, context)
    assert "Ansible" in result
    assert "K8S" in result
    assert "MySQL" in result


def test_filter_missing_skills_case_insensitive():
    """Match must be case-insensitive (e.g. 'docker' vs 'Docker')."""
    context = "Tools: Git, docker, Pytest"
    missing = ["Docker", "Ansible"]
    result = _filter_missing_skills(missing, context)
    assert "Docker" not in result
    assert "Ansible" in result

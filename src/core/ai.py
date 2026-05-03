import os
import re
import asyncio
from src.core.models import Job, TailoredApplication, TailoredProject, TailoredExperience, CoverLetterResult
from src.core.ledger import LedgerManager


# Merge priority: if we have > max_categories, absorb these keys into a target
_MERGE_MAP = [
    ("Cloud & Services",    "Infrastructure & DevOps"),
    ("Databases",           "Backend & Systems"),
    ("Testing & Validation","Backend & Systems"),
    ("Game Development",    "Languages"),
    ("Mobile Development",  "Backend & Systems"),
]

def _merge_skill_categories(    skills: dict[str, list[str]],
    max_categories: int = 4,
) -> dict[str, list[str]]:
    """
    Enforce a hard cap on the number of skill categories.

    Merging rules (applied in order until len <= max_categories):
    1. Absorb small secondary categories into a natural parent using _MERGE_MAP.
    2. If still over cap after all mapped merges, absorb the smallest remaining
       category into its nearest neighbour in the dict.
    Languages is NEVER eliminated — it is always kept.
    """
    result: dict[str, list[str]] = dict(skills)  # preserve original order

    for source_cat, target_cat in _MERGE_MAP:
        if len(result) <= max_categories:
            break
        if source_cat in result:
            if target_cat in result:
                result[target_cat] = result[target_cat] + result.pop(source_cat)
            else:
                # Target doesn't exist — rename source to target
                result[target_cat] = result.pop(source_cat)

    # Safety: if still over cap, absorb smallest non-Languages category iteratively
    while len(result) > max_categories:
        # Sort by skill count ascending, but never touch Languages
        candidates = sorted(
            [(k, v) for k, v in result.items() if k != "Languages"],
            key=lambda kv: len(kv[1]),
        )
        if len(candidates) < 2:
            break
        smallest_key, smallest_skills = candidates[0]
        second_key = candidates[1][0]
        result[second_key] = result[second_key] + result.pop(smallest_key)

    return result


def _deduplicate_languages(skills: dict[str, list[str]]) -> dict[str, list[str]]:
    """
    Remove from every non-Languages category any skill that already appears
    in the Languages category (case-insensitive). Drop categories that become
    empty after dedup.
    """
    lang_set = {s.lower() for s in skills.get("Languages", [])}
    result: dict[str, list[str]] = {}
    for cat, skill_list in skills.items():
        if cat == "Languages":
            result[cat] = skill_list
        else:
            cleaned = [s for s in skill_list if s.lower() not in lang_set]
            if cleaned:
                result[cat] = cleaned
    return result


def _filter_missing_skills(missing: list[str], resume_text: str) -> list[str]:
    """
    Remove from missing_skills any entry that already appears in the candidate's
    resume/ledger context. Uses word-boundary matching for short tokens and
    case-insensitive substring for multi-word phrases.
    """
    text_lower = resume_text.lower()

    def _in_context(skill: str) -> bool:
        sl = skill.lower()
        if " " in sl:
            return sl in text_lower
        return bool(re.search(r"\b" + re.escape(sl) + r"\b", text_lower))

    return [s for s in missing if not _in_context(s)]


def _contains_placeholder_bullet(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    patterns = [
        "[x]",
        "[y]",
        "[z]",
        "accomplished [x] by doing [y], resulting in [z]",
        "accomplished x by doing y, resulting in z",
    ]
    return any(p in t for p in patterns)


def _has_placeholder_bullets(result: TailoredApplication) -> bool:
    for exp in result.tailored_experience:
        for b in exp.bullets:
            if _contains_placeholder_bullet(b):
                return True
    for edu in result.tailored_education:
        for b in edu.bullets:
            if _contains_placeholder_bullet(b):
                return True
    return False


_TECH_TITLE_KEYWORDS = {
    "engineer", "developer", "software", "programmer", "analyst", "architect",
    "designer", "lead", "scientist", "researcher", "intern", "co-op", "coop",
    "data", "cloud", "devops", "sre", "qa", "tester", "technical", "tech",
    "backend", "frontend", "fullstack", "full-stack", "mobile", "web",
    "platform", "infrastructure", "security", "network", "database",
    "machine learning", "deep learning", "ai ", "ml ",
}

def _is_work_relevant(experience: list) -> bool:
    """Return True if any work experience entry has a tech/engineering title."""
    for exp in experience:
        title_lower = (exp.title or "").lower()
        if any(kw in title_lower for kw in _TECH_TITLE_KEYWORDS):
            return True
    return False


def _is_generic_education_bullet(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    generic_phrases = [
        "studied core computer science principles",
        "including data structures, algorithms",
        "coursework relevant to",
        "strong foundation in",
        "developed strong",
    ]
    if any(p in t for p in generic_phrases):
        return True
    # Very short, generic bullets are usually low-signal filler.
    return len(t.split()) < 8


def _hydrate_education_bullets(result: TailoredApplication, course_hints: list[str]) -> None:
    """Ensure education bullets are concrete and template-quality.

    If bullets are empty or all generic, replace with a deterministic
    coursework line based on role-aware approved hints.
    """
    if not result.tailored_education:
        return

    hints = [h.strip() for h in (course_hints or []) if h and h.strip()]
    if not hints:
        return

    for edu in result.tailored_education:
        bullets = [b.strip() for b in (edu.bullets or []) if b and b.strip()]
        if not bullets or all(_is_generic_education_bullet(b) for b in bullets):
            edu.bullets = [f"Relevant Coursework: {', '.join(hints[:4])}."]


def _normalize_education_institutions(result: TailoredApplication) -> None:
    """Expand common institution abbreviations for cleaner resume rendering."""
    if not result.tailored_education:
        return

    normalize_map = {
        "sfu": "Simon Fraser University",
        "ubc": "The University of British Columbia",
        "uvic": "University of Victoria",
        "bcit": "British Columbia Institute of Technology",
        "langara": "Langara College",
        "uoft": "University of Toronto",
        "u of t": "University of Toronto",
        "uottawa": "University of Ottawa",
        "uofc": "University of Calgary",
        "ualberta": "University of Alberta",
        "sait": "Southern Alberta Institute of Technology",
    }

    for edu in result.tailored_education:
        inst = (edu.institution or "").strip()
        if not inst:
            continue
        normalized = normalize_map.get(inst.lower())
        if normalized:
            edu.institution = normalized


def _load_dotenv():
    """Minimal .env loader — no dependency on python-dotenv."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _parse_ledger_as_resume(ledger_path: str) -> str:
    """
    Reads ledger.md and returns the AI context for tailoring.

    Always includes the '## GitHub Projects:' block regardless of its position
    in the file — this section may appear before OR after '## Imported Resume:'
    depending on whether the user ran GitHub Refresh before or after uploading
    their PDF.  Dropping it silently would give the AI zero project context.

    Layout handled:
      Case A (normal): base → ## Imported Resume: → ## GitHub Projects:
      Case B (new user does refresh first): base → ## GitHub Projects: → ## Imported Resume:
    """
    if not os.path.exists(ledger_path):
        return ""
    content = open(ledger_path, encoding="utf-8").read()

    _RESUME_MARKER = "## Imported Resume:"
    _GITHUB_MARKER = "## GitHub Projects:"

    # Extract GitHub Projects block (everything from the marker to the next ## or EOF)
    github_block = ""
    if _GITHUB_MARKER in content:
        after_gh = content.split(_GITHUB_MARKER, 1)[1]
        # Stop at the next top-level section heading (##) if present
        next_section = re.search(r"\n## ", after_gh)
        block_body = after_gh[: next_section.start()] if next_section else after_gh
        github_block = f"{_GITHUB_MARKER}\n{block_body.strip()}"

    if _RESUME_MARKER in content:
        resume_body = content.split(_RESUME_MARKER, 1)[1].strip()
        # If resume already contains the GitHub block (Case A), no need to prepend
        if github_block and _GITHUB_MARKER not in resume_body:
            return f"{github_block}\n\n{resume_body}"
        return resume_body

    # No resume uploaded yet — return the whole ledger as context
    return content.strip()


def _extract_github_tech_map(resume_text: str) -> dict[str, str]:
    """
    Parse the '## GitHub Projects:' section and return a dict mapping
    lowercase repo name → extracted tech stack string from the README.

    Looks for lines like: "### RepoName  ★0  |  TypeScript"
    and then scans the README text for Tech Stack / Built With sections.
    """
    tech_map: dict[str, str] = {}
    _GITHUB_MARKER = "## GitHub Projects:"
    if _GITHUB_MARKER not in resume_text:
        return tech_map

    gh_section = resume_text.split(_GITHUB_MARKER, 1)[1]

    # Split into per-repo blocks by the ### heading
    repo_blocks = re.split(r"(?=^### )", gh_section, flags=re.MULTILINE)
    for block in repo_blocks:
        block = block.strip()
        if not block.startswith("###"):
            continue
        # Repo name from "### RepoName  ★0  |  TypeScript"
        header_m = re.match(r"^### ([\w\-. ]+?)\s+[★|]", block)
        if not header_m:
            continue
        repo_name = header_m.group(1).strip()

        # Collect all tech mentioned in this block
        # Strategy: find lists under "Tech Stack", "Built With", "Frontend", "Backend",
        # "Languages", "Technologies" headings, and also the "|  Language" from the header.
        techs: list[str] = []

        # Language from header line (e.g. "| TypeScript")
        lang_m = re.search(r"\|\s+([A-Za-z+#]+)\s", block.split("\n")[0])
        if lang_m:
            techs.append(lang_m.group(1))

        # Scan README for **Tech** or - **Tech** or "React" "TypeScript" etc.
        # Look for bold items like **React**, **TypeScript**, **Vite**
        bold_techs = re.findall(r"\*\*([A-Za-z][A-Za-z0-9.# +\-]{1,30})\*\*", block)
        techs.extend(bold_techs)

        # Look for "Tech Stack" or "Frontend" section lines  (e.g. "- React with TypeScript")
        tech_lines = re.findall(
            r"(?i)(?:tech stack|frontend|backend|built with|technologies)[^\n]*\n((?:[-*•]\s+[^\n]+\n?)+)",
            block,
        )
        for chunk in tech_lines:
            items = re.findall(r"[-*•]\s+([^\n]+)", chunk)
            techs.extend(items)

        if techs:
            # Deduplicate preserving order
            seen: set[str] = set()
            unique_techs = []
            for t in techs:
                t_clean = t.strip().strip("*").strip()
                if t_clean and t_clean.lower() not in seen and len(t_clean) < 40:
                    seen.add(t_clean.lower())
                    unique_techs.append(t_clean)
            tech_map[repo_name.lower()] = ", ".join(unique_techs[:12])

    return tech_map


def _enrich_resume_with_github_tech(resume_text: str) -> str:
    """
    For each project in the TECHNICAL PROJECTS section of the imported resume,
    look up whether a GitHub repo exists with a matching name. If so, append
    an explicit 'Full tech stack from GitHub: ...' annotation right after the
    project's tech line so the AI cannot miss it.

    This fixes the case where the uploaded PDF says "Python, Docker, AWS"
    for a full-stack project that actually has React/TypeScript in GitHub.
    """
    tech_map = _extract_github_tech_map(resume_text)
    if not tech_map:
        return resume_text

    # Find TECHNICAL PROJECTS section in the resume body
    tech_proj_re = re.compile(
        r"(?i)(technical projects?)\s*\n",
    )
    m = tech_proj_re.search(resume_text)
    if not m:
        return resume_text

    proj_section_start = m.end()
    proj_section_text = resume_text[proj_section_start:]

    def _best_match(title: str) -> str | None:
        """Return the best-matching key in tech_map for this project title."""
        title_lower = title.lower()
        # Exact substring match first
        for key in tech_map:
            if key in title_lower or title_lower in key:
                return key
        # Word overlap: split title into words, check if ≥2 words appear in any key
        title_words = set(re.findall(r"[a-z0-9]+", title_lower))
        best_key, best_score = None, 0
        for key in tech_map:
            key_words = set(re.findall(r"[a-z0-9]+", key))
            score = len(title_words & key_words)
            if score > best_score:
                best_score, best_key = score, key
        return best_key if best_score >= 1 else None

    # Find project title lines: lines followed by a date (e.g. "Jan 2026 – Present")
    proj_title_re = re.compile(
        r"^([A-Z][^\n]+?)\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}",
        re.MULTILINE,
    )

    enriched = proj_section_text
    # Process replacements in reverse order to preserve offsets
    for pm in reversed(list(proj_title_re.finditer(proj_section_text))):
        title = pm.group(1)
        matched_key = _best_match(title)
        if not matched_key:
            continue
        gh_tech = tech_map[matched_key]
        # Find the tech line right after this title (next non-empty line)
        after_title = proj_section_text[pm.end():]
        tech_line_m = re.search(r"\n([^\n•\-*]+)\n", after_title)
        if tech_line_m:
            insert_pos = pm.end() + tech_line_m.end() - 1  # after the tech line's newline
            annotation = f"\n  [GitHub full stack: {gh_tech}]"
            enriched = enriched[:insert_pos] + annotation + enriched[insert_pos:]

    return resume_text[:proj_section_start] + enriched


def _recommended_course_hints(job: Job) -> list[str]:
    """Return role-aware SFU coursework hints to use when education details are sparse."""
    role = (job.role or "").lower()
    desc = (job.job_description or "").lower()
    text = f"{role} {desc}"

    if any(k in text for k in ["backend", "api", "systems", "distributed", "database", "go", "grpc"]):
        return [
            "Computer Systems",
            "Data Structures & Programming",
            "Operating Systems",
            "Database Systems",
            "Discrete Mathematics",
        ]
    if any(k in text for k in ["frontend", "react", "typescript", "ui", "web"]):
        return [
            "Software Engineering",
            "Human-Computer Interaction",
            "Web Development",
            "Data Structures & Programming",
        ]
    if any(k in text for k in ["machine learning", "ml", "ai", "data", "analytics", "nlp"]):
        return [
            "Linear Algebra",
            "Probability and Statistics",
            "Data Structures & Programming",
            "Machine Learning",
        ]
    return [
        "Data Structures & Programming",
        "Computer Systems",
        "Software Engineering",
    ]


async def _gemini_call_with_retry(loop, client, model: str, contents, config):
    """
    Call the Gemini API with model-cascade fallback on 503 (overloaded).

    Cascade: flash-lite-001 → flash-001 → flash → gemma-3-27b-it
    Each model runs on separate Google infrastructure, so if the entire Gemini
    flash pool is down, Gemma (different cluster) will still respond.

    Note: Gemma does not support response_mime_type in config — the caller's
    JSON-fence stripping handles parsing for those responses.
    """
    from google.genai import types as _gtypes
    from google.genai.errors import ServerError

    _model_cascade = [
        model,
        "gemini-3.1-flash-lite-preview",  # 2.5s, 500 RPD
        "gemma-4-31b-it",                 # 16s, 1.5K RPD, unlimited TPM
        "gemma-3-27b-it",                  # 22s, 14.4K RPD — last resort
    ]
    # Deduplicate while preserving order
    seen: set = set()
    cascade = [m for m in _model_cascade if not (m in seen or seen.add(m))]

    last_exc = None
    for candidate in cascade:
        # Gemma models don't support response_mime_type — strip it for those models
        if "gemma" in candidate or "gemini" not in candidate:
            try:
                _cfg = _gtypes.GenerateContentConfig(temperature=config.temperature or 0.2)
            except Exception:
                _cfg = config
        else:
            _cfg = config

        delay = 8
        for attempt in range(2):   # 2 tries per model before escalating
            try:
                _m, _c = candidate, _cfg   # capture for lambda closure
                return await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model=_m, contents=contents, config=_c,
                    ),
                )
            except ServerError as e:
                last_exc = e
                # Google GenAI SDK exposes status differently depending on version
                status = getattr(e, "code", getattr(e, "status_code", None))
                if status is None and e.args:
                    status = e.args[0]
                
                is_503 = (status == 503) or ("503" in str(e))
                if is_503 and attempt == 0:
                    import logging
                    logging.getLogger(__name__).warning("Gemini 503 Overloaded. Retrying...")
                    await asyncio.sleep(delay)
                    continue
                break   # non-503 or second attempt failed → next model
    raise last_exc



class AITailor:
    """
    Provider-agnostic AI tailoring engine.

    Reads AI_PROVIDER env var to select backend:
      - "gemini"  → Google Gemini Flash (free tier, default)
      - "openai"  → OpenAI gpt-4o-mini

    Raises ValueError on startup if the required API key is missing.
    """

    def __init__(self, ledger_manager: LedgerManager):
        self.ledger = ledger_manager
        self.provider = os.getenv("AI_PROVIDER", "gemini").lower()

        if self.provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY is not set. Add it to your .env file. "
                    "Get a free key at https://aistudio.google.com/app/apikey"
                )
            from google import genai
            self._gemini_client = genai.Client(api_key=api_key)

        elif self.provider == "openai":
            if "OPENAI_API_KEY" not in os.environ:
                raise ValueError(
                    "OPENAI_API_KEY is not set. Add it to your .env file."
                )
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI()

        else:
            raise ValueError(f"Unknown AI_PROVIDER '{self.provider}'. Use 'gemini' or 'openai'.")

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> TailoredApplication:
        if self.provider == "gemini":
            return await self._call_gemini(system_prompt, user_prompt)
        return await self._call_openai(system_prompt, user_prompt)

    async def _call_gemini(self, system_prompt: str, user_prompt: str) -> TailoredApplication:
        from google.genai import types

        json_schema = (
            '{\n'
            '  "job_id": "<string>",\n'
            '  "skills_to_highlight": {\n'
            '    // CRITICAL: Category NAMES must reflect THIS JD domain, not be generic.\n'
            '    // Frontend JD → use "Frontend" not "Backend & Systems".\n'
            '    // Backend JD → use "Backend & Systems". Full-stack → both.\n'
            '    // Examples: "Frontend", "Backend & Systems", "Languages", "Infrastructure & DevOps",\n'
            '    //           "AI & Data", "Testing & Validation", "Cloud & Infrastructure"\n'
            '    // Only include categories containing skills the JD actually requires.\n'
            '    "<JD-relevant category>": ["skill1", "skill2"],\n'
            '    "<another JD-relevant category>": ["skill3"]\n'
            '  },\n'
            '  "tailored_projects": [\n'
            '    {\n'
            '      "title": "<project name from resume>",\n'
            '      "tech": "<4-5 techs from THIS project most relevant to THIS JD — not all techs>",\n'
            '      "date": "<date range>",\n'
            '      "project_type": "<Personal Project or Collaborative Project>",\n'
            '      "keyword_overlap_count": <integer — count of JD keywords matched by this project>,\n'
            '      "bullets": ["<XYZ bullet 1>", "<XYZ bullet 2>", "<XYZ bullet 3 — add if relevant>", "<XYZ bullet 4 — add if highly relevant>"]\n'
            '    }\n'
            '  ],\n'
            '  "tailored_experience": [\n'
            '    {\n'
            '      "title": "<exact job title from context>",\n'
            '      "company": "<exact company name>",\n'
            '      "start_date": "<start date as in context>",\n'
            '      "end_date": "<end date or Present>",\n'
            '      "location": "<city or Remote>",\n'
            '      "bullets": ["<XYZ bullet 1 with JD keyword>", "<XYZ bullet 2>"]\n'
            '    }\n'
            '  ],\n'
            '  "tailored_education": [\n'
            '    {\n'
            '      "degree": "<exact degree/program text from context>",\n'
            '      "institution": "<exact school/institution from context>",\n'
            '      "start_date": "<start date as in context>",\n'
            '      "end_date": "<end date or Present>",\n'
            '      "location": "<city or empty>",\n'
            '      "bullets": ["<optional fact-based education bullet>"]\n'
            '    }\n'
            '  ],\n'
            '  "q_and_a_responses": {"<question>": "<answer>"},\n'
            '  "missing_skills": ["<exact tool/language from JD that is NOT in candidate context>"]\n'
            '}'
        )

        full_prompt = (
            f"{system_prompt}\n\n{user_prompt}\n\n"
            f"Respond with ONLY valid JSON matching this exact structure — no markdown fences, no explanation:\n{json_schema}"
        )

        loop = asyncio.get_event_loop()
        response = await _gemini_call_with_retry(
            loop, self._gemini_client,
            model="gemini-2.5-flash-lite",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        # Strip markdown fences in case a Gemma fallback was used
        _raw = re.sub(r"^```(?:json)?\s*", "", response.text.strip(), flags=re.IGNORECASE)
        _raw = re.sub(r"\s*```$", "", _raw.strip())
        return TailoredApplication.model_validate_json(_raw)

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> TailoredApplication:
        completion = await self._openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            response_format=TailoredApplication,
        )
        return completion.choices[0].message.parsed

    async def fetch_missing_description(self, url: str) -> str:
        """Just-in-time scrape for LinkedIn jobs missing descriptions due to lazy loading."""
        import logging
        from src.infrastructure.browser import BrowserManager
        
        logger = logging.getLogger(__name__)
        logger.info(f"Lazy loading missing description for: {url}")
        try:
            manager = BrowserManager.get_instance()
            text = await manager.fetch_text(url)
            return re.sub(r'\s+', ' ', text).strip()[:10000]
        except Exception as e:
            logger.warning(f"JIT fetch failed for {url}: {e}")
            return "Description unavailable."

    async def tailor_application(self, job: Job) -> TailoredApplication:
        if not job.job_description or len(job.job_description) < 150:
            job.job_description = await self.fetch_missing_description(job.url)

        # 1. Read the full resume text from the ledger
        resume_text = _parse_ledger_as_resume(self.ledger.ledger_path)
        if not resume_text:
            # Fallback: use FAISS chunks if no resume imported
            try:
                chunks = self.ledger.search_facts(job.role, top_k=8)
                resume_text = "\n".join(chunks)
            except RuntimeError:
                resume_text = "No resume facts available."

        course_hints = _recommended_course_hints(job)
        course_hints_str = "\n".join(f"- {c}" for c in course_hints)

        # Enrich TECHNICAL PROJECTS in the resume text with full tech stack from GitHub.
        # This annotates each project inline so the AI cannot miss React/TS/etc. that
        # are absent from the uploaded PDF's tech line but present in the GitHub README.
        resume_text = _enrich_resume_with_github_tech(resume_text)

        # 2. System prompt — strict hallucination guard + XYZ format + keyword injection
        system_prompt = (
            "You are an elite Resume Tailor and ATS Optimizer for software engineering roles.\n\n"
            "IRON RULE — NO HALLUCINATIONS: You are ABSOLUTELY FORBIDDEN from inventing any project, "
            "tool, company, date, GPA, metric, or technology that does not appear in the "
            "CANDIDATE'S CONTEXT below. Every claim must be traceable to the context text. "
            "NOTE: Lines starting with '[GitHub full stack: ...]' are verified annotations — "
            "you MAY use those technologies in bullets and the 'tech' field for that project.\n\n"
            "PROJECT SOURCES RULE (relevance-first):\n"
            "Use the following priority order to find the 3 best-matching projects:\n"
            "  PRIORITY 1 — '## GitHub Projects:' section: each '### RepoName' entry is a real project. "
            "Use its README and description as the verified facts for bullet points AND for tech stack scoring.\n"
            "  PRIORITY 2 — 'TECHNICAL PROJECTS' section of the imported resume: if fewer than 3 GitHub "
            "repos have meaningful keyword overlap with the JD, supplement with projects listed in the "
            "TECHNICAL PROJECTS section of the imported resume. Use ONLY facts stated there for bullets.\n"
            "IMPORTANT — TECH STACK COMPLETENESS RULE: The imported resume's tech listing per project "
            "is often INCOMPLETE — it usually only lists the primary backend/deployed stack and frequently "
            "OMITS frontend technologies (React, TypeScript, CSS, etc.) even when the project had a "
            "significant frontend. When a project appears in BOTH '## GitHub Projects:' AND 'TECHNICAL "
            "PROJECTS', the GitHub README/description is AUTHORITATIVE for the full tech stack and must "
            "be used for keyword overlap scoring. Do NOT limit the overlap score to just what the imported "
            "resume lists — look at the full GitHub README for that project.\n"
            "EXAMPLE: If the imported resume lists a project as 'Python, Docker, AWS, FastAPI' but the "
            "GitHub README also shows 'React, TypeScript, REST API', that project scores high overlap "
            "for a Frontend/React/TypeScript JD — its resume listing just wasn't complete.\n"
            "In both cases: select projects by keyword overlap with THIS JD — relevance is the only criterion. "
            "DO NOT include a project just because it sounds impressive. "
            "A Go/distributed-systems project is IRRELEVANT for a Java/Python delivery-engineering JD. "
            "Score each project honestly and pick the 3 with the highest overlap.\n"
            "For title: use the project name exactly as written. "
            "For tech: list only the techs with the highest overlap with THIS JD — pull from GitHub README "
            "if the resume listing is incomplete. "
            "For date: use the date shown in the context, or 'Present' if not specified. "
            "For project_type: use 'Personal Project' or 'Collaborative Project' as shown.\n\n"
            "BULLET FORMAT — XYZ RULE (mandatory for every bullet):\n"
            "Structure every bullet as: 'Accomplished [X] by doing [Y], resulting in [Z].'\n"
            "Front-load the impact. Lead with the outcome or scale, not the action.\n"
            "Example BAD:  'Engineered a WAL with fsync durability.'\n"
            "Example GOOD: 'Eliminated data loss risk by engineering a binary WAL with strict fsync "
            "durability and atomic snapshots, ensuring zero corruption across 17 integration tests.'\n"
            "BULLET DOMAIN ALIGNMENT RULE: Bullets must be written in the language of the JD's domain.\n"
            "  • Frontend/React/TypeScript JD → bullets must emphasise: component architecture, "
            "TypeScript typing, state management, UI performance, accessibility, API integration "
            "from the client side, frontend security (XSS/CSRF prevention), responsive design, "
            "reusable component libraries, React hooks. NEVER lead with deployment, Docker, "
            "server throughput, or backend metrics for a frontend role.\n"
            "  • Backend JD → bullets must emphasise: API design, throughput, latency, "
            "database schema, service reliability, concurrency.\n"
            "  Always align bullet vocabulary and impact statements to what this specific JD cares about.\n\n"
            "ATS KEYWORD INJECTION RULE:\n"
            "First, extract the top 8-10 exact required phrases from the job description "
            "(e.g. 'CI/CD pipelines', 'distributed systems', 'RESTful APIs'). "
            "You MUST embed at least 4 of these exact phrases verbatim somewhere in the bullets. "
            "Wrap each injected JD keyword in **double asterisks** (e.g. **distributed systems**) "
            "so they render as bold in the PDF — this maximises ATS scoring and recruiter eye-tracking.\n\n"
            "YOUR JOB:\n"
            "1. For skills_to_highlight: derive category NAMES from the JD domain using this taxonomy:\n"
            "  • 'Frontend'                -> JD mentions UI, React, Vue, Angular, TypeScript, accessibility, CSS\n"
            "  • 'Backend & Systems'        -> JD mentions APIs, microservices, Node.js, Go, Python server, gRPC, databases\n"
            "  • 'Mobile Development'       -> JD mentions iOS, Android, Swift, Kotlin, React Native, Flutter\n"
            "  • 'Infrastructure & DevOps'  -> JD mentions Docker, Kubernetes, Terraform, CI/CD, cloud infra, pipelines\n"
            "  • 'AI & Machine Learning'    -> JD mentions ML, LLMs, PyTorch, TensorFlow, RAG, NLP, embeddings, AI\n"
            "  • 'Data Engineering'         -> JD mentions SQL, ETL, Airflow, Spark, Pandas, data pipelines, analytics\n"
            "  • 'Distributed Systems'      -> JD mentions Raft, consensus, fault tolerance, distributed DB, replication\n"
            "  • 'Cloud & Services'         -> JD mentions AWS, GCP, Azure, serverless, S3, Lambda, cloud deployment\n"
            "  • 'Security & Networking'    -> JD mentions auth, OAuth, JWT, TLS, OWASP, penetration testing\n"
            "  • 'Testing & Validation'     -> JD mentions test, QA, validation, bug, automation, quality\n"
            "  • 'Databases'               -> JD mentions schema design, indexing, PostgreSQL, MongoDB, Redis\n"
            "  • 'Languages'               -> ALWAYS include this category; list ALL programming languages from the candidate's context, not just JD-relevant ones\n"
            "CATEGORY RULES: Output EXACTLY 3-4 categories — no more, no less. "
            "If a JD only touches 2 distinct areas, merge related categories (e.g. 'Cloud & Services' into 'Infrastructure & DevOps', 'Databases' into 'Backend & Systems'). "
            "ALWAYS include 'Languages' as one of the 3-4 categories. "
            "You may create a new category label (e.g. 'Game Development', 'Embedded Systems') if no taxonomy entry fits.\n"
            "SKILLS GUARDRAIL (CRITICAL): For skills_to_highlight, you are ABSOLUTELY FORBIDDEN from listing "
            "any skill, tool, language, or technology that does not appear explicitly in the CANDIDATE'S CONTEXT. "
            "Do NOT add skills from the JD that the candidate has not demonstrated. "
            "If the JD mentions Kubernetes but the candidate's context does not, Kubernetes must NOT appear in "
            "skills_to_highlight — it must go into missing_skills instead.\n"
            "For missing_skills: list every specific tool/language/technology the JD requires or strongly prefers "
            "that is NOT present anywhere in the candidate's context. Be granular (e.g. 'Kubernetes', 'Ansible', "
            "'Cassandra') not vague (e.g. 'DevOps skills'). An empty list is valid if the candidate matches fully.\n"
            "2. For tailored_projects: use keyword-overlap scoring — works for ANY job type.\n"
            "  STEP A: Extract the top 10 specific tech keywords from the JD (tools, languages, frameworks, patterns).\n"
            "  STEP B: For EACH candidate project — both repos from '## GitHub Projects:' AND projects from "
            "the 'TECHNICAL PROJECTS' section of the imported resume — count how many JD keywords appear "
            "in its description, README, or tech stack. Projects with zero keyword overlap MUST be excluded. "
            "Store this count in the 'keyword_overlap_count' field for that project.\n"
            "  TECH DOMAIN BOUNDARY RULE (critical for frontend/mobile/backend specialised JDs):\n"
            "  When the JD's PRIMARY requirement is a specific frontend framework or language "
            "(React, TypeScript, Vue, Angular, GraphQL, etc.), ONLY the following terms count as overlap "
            "for keyword scoring: React, TypeScript, JavaScript, GraphQL, Redux, Zustand, CSS/SCSS, HTML, "
            "Next.js, Vue, Angular, state management, component, hooks, accessibility, XSS, CSRF, "
            "frontend security, REST API (only if JD explicitly mentions REST alongside the frontend stack), "
            "and any other term the JD explicitly calls out.\n"
            "  The following NEVER count as keyword overlap for a Frontend/React/TypeScript JD: "
            "Python, Go, Java, Streamlit (a Python-only server-rendered UI lib — NOT React/TypeScript), "
            "FastAPI, Django, Flask, Raft, consensus algorithm, distributed database, gRPC, "
            "Asyncio, HTTPX, scraping, AI/LLM-specific terms (unless JD mentions them), "
            "Docker, Kubernetes (unless JD explicitly mentions them).\n"
            "  EXAMPLE: For a React/TypeScript/GraphQL Frontend JD — a Python/Streamlit AI project scores "
            "0-1 overlap (Streamlit ≠ React), a Go distributed-database project scores 0 overlap, "
            "a React/TypeScript SPA scores 4-6 overlap. Rank accordingly.\n"
            "  STEP C: Rank ALL candidate projects by overlap count. Select the top 3 only.\n"
            "  For the 'tech' field per project: list ONLY the 4-5 techs from that project "
            "with the highest overlap with THIS JD's keywords — not the full stack.\n"
            "  BULLET COUNT RULE (after ranking by overlap): project #1 must have 4 bullets, project #2 must have 4 bullets,"
            " and project #3 must have 3 bullets.\n"
            "3. For tailored_experience: if the CANDIDATE'S CONTEXT contains a 'WORK EXPERIENCE' section, "
            "populate this array with each role. For each entry rewrite the bullets in XYZ format "
            "('Accomplished X, as measured by Y, by doing Z') and naturally inject the top 3-5 exact JD keywords "
            "wherever truthful. Preserve title, company, start_date, end_date, and location exactly as written "
            "in the context. Do NOT invent roles, companies, dates, or metrics. "
            "If the context has NO work experience entries, output an empty array for this field.\n"
            "4. For tailored_education: if the CANDIDATE'S CONTEXT contains an 'EDUCATION' section, populate this "
            "array with each education entry using exact source wording for degree and institution. Preserve "
            "start_date/end_date/location exactly as written when present. Do NOT normalize degree wording and do "
            "NOT invent GPA, awards, or certifications. If no education entries exist in context, output an empty "
            "array for this field.\n"
            "When education bullets are missing/sparse, you may choose 1-3 items from the approved hint list below "
            "to produce realistic education bullets aligned to the job.\n"
            f"Approved SFU coursework hints:\n{course_hints_str}\n"
            "5. Never output placeholder bullets like '[X]'/'[Y]'/'[Z]'. Every bullet must be concrete and factual.\n"
            "6. Do NOT invent project names, tech stacks, dates, or metrics not present in the context.\n\n"
            f"CANDIDATE'S CONTEXT:\n{resume_text}"
        )

        # 3. User prompt — full JD, no truncation
        questions_str = (
            "\n".join(f"- {q}" for q in job.custom_questions)
            if job.custom_questions else "None"
        )
        user_prompt = (
            f"TARGET ROLE: {job.role} at {job.company}\n\n"
            f"FULL JOB DESCRIPTION:\n{job.job_description}\n\n"
            f"TASKS:\n"
            f"1. Extract the top 8-10 exact required phrases from the JD above. "
            f"Embed at least 4 verbatim into the bullets below.\n"
            f"2. From the resume skills section, select ONLY categories/skills relevant to this JD. "
            f"Omit irrelevant categories entirely. "
            f"If the JD mentions Agile, SDLC, or project planning — embed those exact terms naturally into at least one bullet.\n"
            f"3. For tailored_projects: use keyword-overlap scoring. "
            f"Extract the top 10 tech keywords from the JD. For EACH candidate project — "
            f"both repos from '## GitHub Projects:' AND projects from the 'TECHNICAL PROJECTS' section — "
            f"score keyword overlap using the FULL tech stack from GitHub README (not just what the "
            f"imported resume lists — the resume tech listing is often incomplete and omits frontend tech). "
            f"TECH DOMAIN BOUNDARY: For a Frontend/React/TypeScript JD, ONLY React, TypeScript, "
            f"JavaScript, GraphQL, Redux/Zustand, CSS, HTML, Next.js, component, hooks, state management, "
            f"accessibility, frontend security terms count as keyword overlap. "
            f"Python, Streamlit, Go, FastAPI, Raft, gRPC, AI/LLM terms score ZERO overlap for this JD. "
            f"A Python/Streamlit project scores 0-1. A Go distributed-DB scores 0. A React/TypeScript SPA scores highest. "
            f"Rank ALL candidate projects by overlap score and pick the top 3. "
            f"Projects with zero keyword overlap must be excluded entirely. "
            f"For the 'tech' field per project: list only the 4-5 techs with the highest overlap with THIS JD's keywords — "
            f"pull from GitHub README if the resume listing is incomplete. "
            f"Set keyword_overlap_count on each selected project to the number of JD keywords matched. "
            f"After ranking projects by overlap score, enforce bullet counts by rank: project #1 = 4 bullets, project #2 = 4 bullets, project #3 = 3 bullets. "
            f"Write bullets in the DOMAIN LANGUAGE of the JD — for a Frontend JD, emphasise components, "
            f"TypeScript, state management, UI performance, client-side API integration, frontend security. "
            f"Preserve project name as title exactly.\n"
            f"4. For tailored_experience: look for a 'WORK EXPERIENCE' section in the candidate's context above. "
            f"If found, include each role with XYZ-format bullets injecting JD keywords truthfully. "
            f"If the context has no WORK EXPERIENCE section, output an empty array [].\n"
            f"5. For tailored_education: look for an 'EDUCATION' section in candidate context. Use exact source "
            f"wording for degree and institution. Preserve dates exactly. No invented GPA/awards/certs. "
            f"Output [] if no education exists.\n"
            f"6. Never output placeholder bullets like '[X]'/'[Y]'/'[Z]'.\n"
            f"7. Answer these application questions (if any):\n{questions_str}\n\n"
            f"job_id to use in output: {job.id}"
        )

        result = await self._call_llm(system_prompt, user_prompt)
        if _has_placeholder_bullets(result):
            retry_prompt = (
                user_prompt +
                "\n\nRETRY INSTRUCTION: Your previous output used placeholder bullet text. "
                "Regenerate with concrete, fact-based bullets only. Do not use [X], [Y], [Z], or template phrases."
            )
            result = await self._call_llm(system_prompt, retry_prompt)
        # Hard cap: never show more than 3 projects regardless of AI output
        result.tailored_projects = result.tailored_projects[:3]
        # Sort by overlap descending so the best-matching project is always first
        result.tailored_projects = sorted(
            result.tailored_projects,
            key=lambda p: p.keyword_overlap_count,
            reverse=True,
        )
        # Code-enforced rank caps keep resume length predictable.
        # When work experience is not tech-relevant, give project #2 more bullets
        # (4/4/3 instead of 4/3/2) to fill the space left by thin work bullets.
        _work_relevant = _is_work_relevant(result.tailored_experience)
        result.work_experience_relevant = _work_relevant
        _caps = (4, 3, 2) if _work_relevant else (4, 4, 3)
        for i, proj in enumerate(result.tailored_projects):
            proj.bullets = proj.bullets[:_caps[i]]
        # Hard cap: never show more than 4 skill categories on the resume
        result.skills_to_highlight = _merge_skill_categories(
            result.skills_to_highlight, max_categories=4
        )
        # Remove Languages skills that leaked into other categories (e.g. Python in Backend)
        result.skills_to_highlight = _deduplicate_languages(result.skills_to_highlight)
        # Remove false positives from missing_skills (skills the candidate already has)
        result.missing_skills = _filter_missing_skills(result.missing_skills, resume_text)
        # Expand institution abbreviations (e.g. SFU) for cleaner Education output.
        _normalize_education_institutions(result)
        # Upgrade weak education bullets to concrete coursework when needed.
        _hydrate_education_bullets(result, course_hints)
        return result

    async def _call_llm_text(self, prompt: str) -> str:
        """Call the LLM and return raw text (not parsed JSON)."""
        if self.provider == "gemini":
            from google.genai import types
            loop = asyncio.get_event_loop()
            response = await _gemini_call_with_retry(
                loop, self._gemini_client,
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
            )
            return response.text.strip()
        else:
            completion = await self._openai_client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return completion.choices[0].message.content.strip()

    async def generate_cover_letter(self, job: Job) -> CoverLetterResult:
        """Generate a formal cover letter, returning body text + optional address extracted from JD."""
        resume_text = _parse_ledger_as_resume(self.ledger.ledger_path)
        if not resume_text:
            try:
                chunks = self.ledger.search_facts(job.role, top_k=8)
                resume_text = "\n".join(chunks)
            except RuntimeError:
                resume_text = "No resume facts available."

        prompt = (
            "You are an expert cover letter writer for software engineering roles.\n\n"
            "IRON RULE — NO HALLUCINATIONS: Every claim must be directly traceable "
            "to the CANDIDATE'S RESUME below. Do NOT invent projects, technologies, "
            "companies, dates, or metrics.\n\n"
            "Write a professional 3-paragraph cover letter body:\n"
            "1. Opening: Why you're excited about THIS specific role and company.\n"
            "2. Body: 2-3 concrete examples from the resume that directly match "
            "the job requirements. Reference specific projects and technologies.\n"
            "3. Closing: Enthusiasm + call to action.\n\n"
            "RULES:\n"
            "- Keep the body under 300 words\n"
            "- Use a confident, professional tone — not robotic\n"
            "- Do NOT start with 'I am writing to apply' — be more engaging\n"
            "- Do NOT include a salutation line (e.g. 'Dear Hiring Manager') — just the paragraphs\n\n"
            "ALSO: Scan the job description for a company street address "
            "(e.g. '1055 Dunsmuir St #1400, Vancouver, BC V7X 1K8'). "
            "If an address is present verbatim in the JD, include it in company_address. "
            "If no address is present, set company_address to null.\n\n"
            "Respond with ONLY valid JSON — no markdown fences:\n"
            '{\n'
            '  "body": "<3 paragraphs of letter body, newline-separated>",\n'
            '  "company_address": "<street address from JD verbatim, or null>"\n'
            '}\n\n'
            f"CANDIDATE'S RESUME:\n{resume_text}\n\n"
            f"TARGET ROLE: {job.role} at {job.company}\n\n"
            f"JOB DESCRIPTION:\n{job.job_description}"
        )

        raw = await self._call_llm_text(prompt)

        # Strip accidental markdown fences before parsing
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw.strip())

        return CoverLetterResult.model_validate_json(raw)

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
        # Stop at the next TOP-LEVEL section marker (e.g. "## Imported Resume:").
        # Top-level markers always end with ":" — README sub-headings like "## Features"
        # do NOT end with ":", so this avoids truncating the block at README content.
        next_section = re.search(r"\n## [A-Za-z][^\n]+:", after_gh)
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


# Canonical tech keyword list used for scanning GitHub README blocks.
# These are the only terms that will appear in [GitHub full stack:] annotations.
_KNOWN_TECH_KEYWORDS: list[tuple[str, str]] = [
    # Frontend frameworks & libraries
    ("react", "React"), ("next.js", "Next.js"), ("nextjs", "Next.js"),
    ("vue", "Vue"), ("angular", "Angular"), ("svelte", "Svelte"),
    ("graphql", "GraphQL"), ("apollo", "Apollo"),
    ("redux", "Redux"), ("zustand", "Zustand"), ("recoil", "Recoil"), ("jotai", "Jotai"),
    ("tailwind", "Tailwind CSS"), ("sass", "Sass"), ("scss", "SCSS"),
    ("vite", "Vite"), ("webpack", "Webpack"),
    ("react native", "React Native"), ("expo", "Expo"), ("flutter", "Flutter"),
    ("jest", "Jest"), ("vitest", "Vitest"), ("cypress", "Cypress"),
    ("storybook", "Storybook"), ("radix", "Radix UI"), ("shadcn", "shadcn/ui"),
    # Backend frameworks
    ("fastapi", "FastAPI"), ("django", "Django"), ("flask", "Flask"),
    ("express", "Express"), ("nestjs", "NestJS"), ("spring", "Spring"),
    ("gin", "Gin"), ("fiber", "Fiber"), ("actix", "Actix"),
    # Languages
    ("typescript", "TypeScript"), ("javascript", "JavaScript"),
    ("python", "Python"), ("golang", "Go"), (" go ", "Go"),
    ("rust", "Rust"), ("java", "Java"), ("kotlin", "Kotlin"),
    ("swift", "Swift"), ("c#", "C#"), (".net", ".NET"),
    ("c++", "C++"), ("ruby", "Ruby"), ("php", "PHP"),
    # Databases & storage
    ("postgresql", "PostgreSQL"), ("postgres", "PostgreSQL"),
    ("mysql", "MySQL"), ("mongodb", "MongoDB"), ("redis", "Redis"),
    ("sqlite", "SQLite"), ("cassandra", "Cassandra"), ("elasticsearch", "Elasticsearch"),
    ("prisma", "Prisma"), ("sqlalchemy", "SQLAlchemy"), ("typeorm", "TypeORM"),
    ("supabase", "Supabase"), ("firebase", "Firebase"),
    # Infra & cloud
    ("docker", "Docker"), ("kubernetes", "Kubernetes"),
    ("aws", "AWS"), ("gcp", "GCP"), ("azure", "Azure"),
    ("vercel", "Vercel"), ("netlify", "Netlify"), ("terraform", "Terraform"),
    ("github actions", "GitHub Actions"), ("ci/cd", "CI/CD"),
    # AI / ML
    ("langchain", "LangChain"), ("pytorch", "PyTorch"), ("tensorflow", "TensorFlow"),
    ("faiss", "FAISS"), ("openai", "OpenAI"), ("gemini", "Gemini"),
    ("pandas", "Pandas"), ("numpy", "NumPy"), ("scikit-learn", "scikit-learn"),
    # Protocols & auth
    ("grpc", "gRPC"), ("websocket", "WebSocket"),
    ("jwt", "JWT"), ("oauth", "OAuth"),
    # Distributed / messaging
    ("raft", "Raft"), ("kafka", "Kafka"), ("rabbitmq", "RabbitMQ"),
    ("asyncio", "Asyncio"), ("httpx", "HTTPX"), ("celery", "Celery"),
    ("node.js", "Node.js"), ("nodejs", "Node.js"),
]


def _extract_github_tech_map(resume_text: str) -> dict[str, str]:
    """
    Parse the '## GitHub Projects:' section and return a dict mapping
    lowercase repo name → tech stack string (only verified tech keywords).

    Strategy:
    1. Extract the primary language from the header line "### Repo  ★0  |  Language".
    2. Scan the entire README block for known tech keywords from _KNOWN_TECH_KEYWORDS.
    This avoids false-positives from README feature descriptions (e.g. "Comprehensive Search").
    """
    tech_map: dict[str, str] = {}
    _GITHUB_MARKER = "## GitHub Projects:"
    if _GITHUB_MARKER not in resume_text:
        return tech_map

    gh_section = resume_text.split(_GITHUB_MARKER, 1)[1]

    # Build lowercase→canonical lookup once
    kw_lookup: list[tuple[str, str]] = _KNOWN_TECH_KEYWORDS

    # Only split on actual repo headers — these always contain ★ (star count)
    # This prevents ### subheadings inside README excerpts from being treated as repo separators
    repo_blocks = re.split(r"(?=^### [\w\-. ]+\s+★)", gh_section, flags=re.MULTILINE)
    for block in repo_blocks:
        block = block.strip()
        if not block.startswith("###"):
            continue

        # Repo name from "### RepoName  ★0  |  Language"
        header_m = re.match(r"^### ([\w\-. ]+?)\s+[★|]", block)
        if not header_m:
            continue
        repo_name = header_m.group(1).strip()

        # Primary language from header: "| TypeScript" — handle end-of-line
        header_line = block.split("\n")[0]
        lang_m = re.search(r"\|\s+([A-Za-z][A-Za-z+#]*)", header_line)

        block_lower = block.lower()
        found: dict[str, str] = {}  # canonical_lower → canonical display name

        # Add header language first (highest confidence)
        if lang_m:
            lang = lang_m.group(1)
            found[lang.lower()] = lang

        # Scan full block text for known tech keywords
        for kw_lower, kw_display in kw_lookup:
            if kw_lower in block_lower and kw_display.lower() not in found:
                found[kw_display.lower()] = kw_display

        if found:
            # Cap at 15 to keep annotations focused; header language is always first
            tech_map[repo_name.lower()] = ", ".join(list(found.values())[:15])

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
        # Find the tech line right after this title (next non-empty line that isn't a bullet)
        after_title = proj_section_text[pm.end():]
        tech_line_m = re.search(r"\n([^\n•\-*]+)\n", after_title)
        if tech_line_m:
            # REPLACE the original tech line with the GitHub-verified tech stack.
            # This prevents the AI from copying the PDF's incomplete tech line and
            # ensures it reads TypeScript/React instead of Python/Docker for frontend projects.
            old_tech_start = pm.end() + tech_line_m.start() + 1  # skip leading \n
            old_tech_end   = pm.end() + tech_line_m.end()   - 1  # keep trailing \n
            enriched = enriched[:old_tech_start] + gh_tech + enriched[old_tech_end:]

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

        # 2. System prompt — authority-first structure, no redundancy with user prompt
        system_prompt = (
            "You are an expert ATS Resume Tailor for software engineering roles. "
            "You receive a candidate context and a job description, and return a TailoredApplication JSON.\n\n"

            "══════════════════════════════════════════════════════\n"
            "RULE 0 — ZERO HALLUCINATIONS (ABSOLUTE, NO EXCEPTIONS)\n"
            "══════════════════════════════════════════════════════\n"
            "Every fact in every bullet must be directly traceable to CANDIDATE'S CONTEXT. "
            "Forbidden: invented tools, companies, metrics, dates, GPA, or technologies. "
            "The tech line shown per project in 'TECHNICAL PROJECTS' has been pre-validated against "
            "the GitHub source code — treat it as ground truth. Technologies in GitHub README excerpts "
            "are also verified and MAY be used in bullets.\n\n"

            "══════════════════════════════════════════════════════\n"
            "RULE 1 — PROJECT SELECTION (DO THIS FIRST, IN ORDER)\n"
            "══════════════════════════════════════════════════════\n"
            "STEP A — Extract 10 specific tech keywords from the JD (tools, languages, frameworks, patterns).\n\n"
            "STEP B — Score EVERY project from BOTH sources:\n"
            "  • '## GitHub Projects:' — each ### heading is a real project; use its README for facts.\n"
            "  • 'TECHNICAL PROJECTS' in the imported resume — supplement if GitHub has fewer than 3.\n"
            "For each project count how many STEP A keywords appear in its tech line/README/description.\n"
            "CRITICAL: The tech line shown in TECHNICAL PROJECTS is AUTHORITATIVE and GitHub-verified —\n"
            "use it directly for scoring, do NOT substitute it with anything else.\n\n"
            "STEP C — Apply domain boundary scoring. Identify the JD's PRIMARY domain, then:\n\n"
            "  JD domain = FRONTEND (React / TypeScript / Vue / Angular / GraphQL is the core ask):\n"
            "    ✅ COUNTS as overlap: React, TypeScript, JavaScript, GraphQL, Redux, Zustand, Recoil,\n"
            "       CSS, SCSS, Tailwind, HTML, Next.js, Vite, Vue, Angular, Svelte, component architecture,\n"
            "       hooks, state management, accessibility, XSS, CSRF, frontend security, JWT (client auth),\n"
            "       REST API (only when JD explicitly pairs it with the frontend stack).\n"
            "    ❌ SCORES ZERO for a Frontend JD (no matter how impressive):\n"
            "       Python, Go, Java, C, C++, Rust, Streamlit, FastAPI, Django, Flask, Express,\n"
            "       Raft, consensus algorithm, distributed database, gRPC, Asyncio, HTTPX, scraping,\n"
            "       LangChain, FAISS, Gemini, OpenAI, Pandas, RAG, vector store, AI/LLM internals,\n"
            "       Docker, Kubernetes, Terraform (unless JD explicitly mentions them).\n"
            "    Concrete example: React/TypeScript SPA = 5-8 overlap. Python/Streamlit AI tool = 0-1.\n"
            "       Go distributed DB = 0. These are not opinions — apply them as hard rules.\n\n"
            "  JD domain = BACKEND / SYSTEMS (APIs, DB, distributed, microservices is the core ask):\n"
            "    ✅ COUNTS: Python, Go, Node.js, Java, SQL, PostgreSQL, REST, gRPC, Kafka, Redis,\n"
            "       Docker, AWS, Kubernetes, concurrency, throughput, fault tolerance, WAL, Raft.\n"
            "    ❌ SCORES ZERO: React, Vue, CSS, HTML (unless JD says fullstack).\n\n"
            "  JD domain = FULLSTACK / GENERAL: count all tech keyword matches normally.\n\n"
            "STEP D — Rank all projects by score. Select top 3. Projects with 0 overlap = excluded.\n"
            "STEP E — Set keyword_overlap_count on each selected project to its actual count.\n\n"

            "══════════════════════════════════════════════════════\n"
            "RULE 2 — TECH FIELD PER PROJECT\n"
            "══════════════════════════════════════════════════════\n"
            "List ONLY the 4-6 technologies from that project with the highest overlap with THIS JD. "
            "Use the tech line shown in TECHNICAL PROJECTS (it is GitHub-verified and authoritative). "
            "Also consult the GitHub README excerpt for additional confirmed technologies.\n\n"

            "══════════════════════════════════════════════════════\n"
            "RULE 3 — BULLET WRITING\n"
            "══════════════════════════════════════════════════════\n"
            "Format every bullet: 'Accomplished [X] by [Y], resulting in [Z].' — lead with outcome/impact.\n\n"
            "BAD:  'Engineered a WAL with fsync durability.'\n"
            "GOOD: 'Eliminated data-loss risk by engineering a crash-safe WAL with atomic fsync snapshots,\n"
            "       guaranteeing zero corruption across all integration test scenarios.'\n\n"
            "Domain alignment — mandatory per JD type:\n"
            "  FRONTEND JD → emphasise: component architecture, TypeScript interfaces/generics, React hooks,\n"
            "    state management (Redux/Zustand/Context), UI performance (lazy loading, memoisation),\n"
            "    client-side API integration, XSS/CSRF prevention, responsive/accessible design.\n"
            "    NEVER lead with Docker, server throughput, database schemas, or deployment pipelines.\n"
            "  BACKEND JD → emphasise: API design, throughput, latency, database schema, concurrency,\n"
            "    service reliability, error handling, observability.\n"
            "  DISTRIBUTED SYSTEMS JD → emphasise: consensus, fault tolerance, replication, CAP theorem,\n"
            "    durability guarantees, leader election, recovery.\n\n"
            "ATS keyword injection: embed ≥4 exact phrases from the JD verbatim. "
            "Wrap each in **double asterisks** so they bold in the PDF.\n\n"
            "Bullet count by rank (enforce exactly): #1 project = 4 bullets, #2 = 4, #3 = 3.\n"
            "No placeholder bullets ([X], [Y], [Z]). Every bullet must be concrete and factual.\n\n"

            "══════════════════════════════════════════════════════\n"
            "RULE 4 — SKILLS\n"
            "══════════════════════════════════════════════════════\n"
            "skills_to_highlight:\n"
            "  • Output EXACTLY 3-4 categories. Always include 'Languages'.\n"
            "  • ONLY skills explicitly in CANDIDATE'S CONTEXT. Never add from the JD.\n"
            "  • JD-only skills go to missing_skills instead.\n"
            "  Category taxonomy (pick closest match, merge if under 4 categories):\n"
            "    Frontend | Backend & Systems | Mobile Development | Infrastructure & DevOps |\n"
            "    AI & Machine Learning | Data Engineering | Distributed Systems | Cloud & Services |\n"
            "    Security & Networking | Testing & Validation | Databases | Languages\n\n"
            "missing_skills: every specific tool/language the JD requires that is NOT in candidate context.\n"
            "  Be granular (e.g. 'Kubernetes', 'Cassandra') — never vague ('DevOps skills').\n\n"

            "══════════════════════════════════════════════════════\n"
            "RULE 5 — EXPERIENCE & EDUCATION\n"
            "══════════════════════════════════════════════════════\n"
            "tailored_experience: rewrite bullets XYZ-style, inject top 3-5 JD keywords truthfully. "
            "Preserve title, company, dates, location exactly. Output [] if no WORK EXPERIENCE in context.\n\n"
            "tailored_education: exact degree/institution wording from context. Preserve all dates. "
            "No invented GPA, awards, or certifications. Output [] if no EDUCATION in context.\n"
            "You may add 1-3 bullets from the approved coursework hints below when education is sparse:\n"
            f"  {course_hints_str}\n\n"

            f"CANDIDATE'S CONTEXT:\n{resume_text}"
        )

        # 3. User prompt — data only, no rule repetition
        questions_str = (
            "\n".join(f"- {q}" for q in job.custom_questions)
            if job.custom_questions else "None"
        )
        user_prompt = (
            f"TARGET ROLE: {job.role} at {job.company}\n\n"
            f"FULL JOB DESCRIPTION:\n{job.job_description}\n\n"
            f"Follow all rules in the system prompt. Produce a TailoredApplication JSON.\n"
            f"job_id: {job.id}\n\n"
            f"PORTAL QUESTIONS (answer in q_and_a_responses, or empty dict if none):\n{questions_str}"
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

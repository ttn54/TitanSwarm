import os
import re
import asyncio
from src.core.models import Job, TailoredApplication, TailoredProject, TailoredExperience, CoverLetterResult
from src.core.ledger import LedgerManager


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
                if e.status_code == 503 and attempt == 0:
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
            '      "bullets": ["<XYZ bullet 1>", "<XYZ bullet 2>", "<XYZ bullet 3 — add if relevant>", "<XYZ bullet 4 — add if highly relevant>"]\n'
            '    }\n'
            '  ],\n'
            '  "tailored_experience": [],\n'
            '  "q_and_a_responses": {"<question>": "<answer>"}\n'
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

    async def tailor_application(self, job: Job) -> TailoredApplication:
        # 1. Read the full resume text from the ledger
        resume_text = _parse_ledger_as_resume(self.ledger.ledger_path)
        if not resume_text:
            # Fallback: use FAISS chunks if no resume imported
            try:
                chunks = self.ledger.search_facts(job.role, top_k=8)
                resume_text = "\n".join(chunks)
            except RuntimeError:
                resume_text = "No resume facts available."

        # 2. System prompt — strict hallucination guard + XYZ format + keyword injection
        system_prompt = (
            "You are an elite Resume Tailor and ATS Optimizer for software engineering roles.\n\n"
            "IRON RULE — NO HALLUCINATIONS: You are ABSOLUTELY FORBIDDEN from inventing any project, "
            "tool, company, date, GPA, metric, or technology that does not appear in the "
            "CANDIDATE'S CONTEXT below. Every claim must be traceable to the context text.\n\n"
            "GITHUB PROJECTS RULE (strict relevance-first selection):\n"
            "The context may contain a '## GitHub Projects:' section. Each entry starting with "
            "'### RepoName' is one of the candidate's REAL projects — these are your only valid project sources. "
            "You MUST select the 3 repos whose tech stack and domain BEST MATCH the JD. "
            "DO NOT include a repo just because it sounds impressive — relevance to THIS specific JD is the only criterion. "
            "A Go/distributed-systems repo is IRRELEVANT for a frontend Vue/TypeScript JD. "
            "A Python/AI repo is IRRELEVANT for a Java/Android JD. Score each repo honestly. "
            "Use the repo's description and README text as the verified facts for bullet points. "
            "For title: use the repo name exactly. For tech: infer from language field and README. "
            "For date: use 'Present' if not specified. For project_type: 'Personal Project'.\n\n"
            "BULLET FORMAT — XYZ RULE (mandatory for every bullet):\n"
            "Structure every bullet as: 'Accomplished [X] by doing [Y], resulting in [Z].'\n"
            "Front-load the impact. Lead with the outcome or scale, not the action.\n"
            "Example BAD:  'Engineered a WAL with fsync durability.'\n"
            "Example GOOD: 'Eliminated data loss risk by engineering a binary WAL with strict fsync "
            "durability and atomic snapshots, ensuring zero corruption across 17 integration tests.'\n\n"
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
            "  • 'Languages'               -> JD lists specific language proficiency requirements\n"
            "CATEGORY RULES: Select only the 2-4 categories the JD actually requires. "
            "You may create a new category label (e.g. 'Game Development', 'Embedded Systems') if no taxonomy entry fits. "
            "Always include 'Testing & Validation' if the JD mentions testing or QA.\n"
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
            "  STEP B: For each GitHub repo in the context, count how many JD keywords appear "
            "in its README, description, or tech stack. Repos with zero keyword overlap MUST be excluded. "
            "Store this count in the 'keyword_overlap_count' field for that project.\n"
            "  STEP C: Rank repos by overlap count. Select the top 3 only.\n"
            "  For the 'tech' field per repo: list ONLY the 4-5 techs from that project "
            "with the highest overlap with THIS JD's keywords — not the full stack.\n"
            "  BULLET COUNT RULE: give 4 bullets to repos with keyword_overlap_count >= 3; give 2 bullets to repos with keyword_overlap_count <= 2.\n"
            "3. For tailored_experience: leave this array empty — work experience is not included on this resume.\n"
            "4. Do NOT invent project names, tech stacks, dates, or metrics not present in the context.\n\n"
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
            f"Extract the top 10 tech keywords from the JD. For each GitHub repo in the context, "
            f"count how many JD keywords appear in its README/stack (this is its overlap score). "
            f"Rank repos by overlap score and pick the top 3 — repos with zero overlap must be excluded entirely. "
            f"For the 'tech' field per repo: list only the 4-5 techs with the highest overlap with THIS JD's keywords. "
            f"Set keyword_overlap_count on each project to the number of JD keywords matched. "
            f"Give 4 bullets to repos with keyword_overlap_count >= 3; give only 2 bullets to repos with keyword_overlap_count <= 2. "
            f"Preserve repo name as title exactly.\n"
            f"4. Leave tailored_experience as an empty array [].\n"
            f"5. Answer these application questions (if any):\n{questions_str}\n\n"
            f"job_id to use in output: {job.id}"
        )

        result = await self._call_llm(system_prompt, user_prompt)
        # Hard cap: never show more than 3 projects regardless of AI output
        result.tailored_projects = result.tailored_projects[:3]
        # Code-enforced bullet trim: LLM may ignore the prompt rule, so enforce it here
        for proj in result.tailored_projects:
            if proj.keyword_overlap_count <= 2:
                proj.bullets = proj.bullets[:2]
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

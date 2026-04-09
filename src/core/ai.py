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
    Reads ledger.md and returns the full text of the imported resume section.
    Falls back to the base ledger facts if no resume has been imported yet.
    """
    if not os.path.exists(ledger_path):
        return ""
    content = open(ledger_path, encoding="utf-8").read()
    marker = "## Imported Resume:"
    if marker in content:
        # Return everything after the marker — this is the pdfplumber-extracted resume text
        return content.split(marker, 1)[1].strip()
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
            '    "Languages": ["skill1", "skill2"],\n'
            '    "Backend & Systems": ["skill3"]\n'
            '    // Only include categories with skills relevant to this JD. Omit irrelevant ones entirely.\n'
            '  },\n'
            '  "tailored_projects": [\n'
            '    {\n'
            '      "title": "<project name from resume>",\n'
            '      "tech": "<tech stack>",\n'
            '      "date": "<date range>",\n'
            '      "project_type": "<Personal Project or Collaborative Project>",\n'
            '      "bullets": ["<XYZ bullet 1>", "<XYZ bullet 2>", "<XYZ bullet 3 — add if relevant>", "<XYZ bullet 4 — add if highly relevant>"]\n'
            '    }\n'
            '  ],\n'
            '  "tailored_experience": [\n'
            '    {\n'
            '      "title": "<job title from resume>",\n'
            '      "company": "<company name from resume>",\n'
            '      "start_date": "<start date>",\n'
            '      "end_date": "<end date>",\n'
            '      "location": "<location>",\n'
            '      "bullets": ["<XYZ bullet 1>", "<XYZ bullet 2>"]\n'
            '    }\n'
            '  ],\n'
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
            "GITHUB PROJECTS RULE (highest priority for tailored_projects):\n"
            "The context may contain a '## GitHub Projects:' section. Each entry starting with "
            "'### RepoName' is one of the candidate's real projects. "
            "EVERY such repo MUST appear as its own separate TailoredProject entry — do NOT merge repos. "
            "Use the repo's description and README text as the verified facts for bullet points. "
            "For title: use the repo name. For tech: infer from language field and README. "
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
            "1. For skills_to_highlight: derive from the GitHub repos' tech stacks and any skills "
            "listed in the context. Omit categories irrelevant to this JD.\n"
            "2. For tailored_projects: produce one TailoredProject per GitHub repo. "
            "BULLET COUNT RULE: 4 bullets if that repo's tech directly matches the JD; 2 if tangential.\n"
            "3. For tailored_experience: include any work experience from the context. "
            "Rewrite bullets in XYZ format using JD language.\n"
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
            f"Omit irrelevant categories entirely.\n"
            f"3. For tailored_projects: create one separate entry per GitHub repo in the context. "
            f"Each '### RepoName' is its own project. Use README text as fact source for bullets. "
            f"Give 4 bullets to repos whose tech matches the JD; 2 to tangential ones. "
            f"Preserve repo name as title exactly.\n"
            f"4. Rewrite every work experience bullet in XYZ format using JD language. "
            f"Preserve title, company, dates, location exactly.\n"
            f"5. Answer these application questions (if any):\n{questions_str}\n\n"
            f"job_id to use in output: {job.id}"
        )

        return await self._call_llm(system_prompt, user_prompt)

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

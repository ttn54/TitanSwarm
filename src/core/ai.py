import os
import re
import asyncio
from src.core.models import Job, TailoredApplication, TailoredProject
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
            '  "summary": "<2-sentence professional summary for this specific role>",\n'
            '  "skills_to_highlight": ["skill1", "skill2", ...],\n'
            '  "tailored_projects": [\n'
            '    {\n'
            '      "title": "<project name from resume>",\n'
            '      "tech": "<tech stack>",\n'
            '      "date": "<date range>",\n'
            '      "bullets": ["<rewritten bullet 1>", "<rewritten bullet 2>"]\n'
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
        response = await loop.run_in_executor(
            None,
            lambda: self._gemini_client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
        )
        return TailoredApplication.model_validate_json(response.text)

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

        # 2. System prompt — strict hallucination guard
        system_prompt = (
            "You are an elite Resume Tailor and ATS Optimizer for software engineering roles.\n\n"
            "IRON RULE — NO HALLUCINATIONS: You are ABSOLUTELY FORBIDDEN from inventing any project, "
            "tool, company, date, GPA, metric, or technology that does not appear verbatim in the "
            "CANDIDATE'S RESUME below. Every claim must be traceable to the resume text.\n\n"
            "YOUR JOB:\n"
            "1. Read the full job description carefully.\n"
            "2. Identify which of the candidate's EXISTING projects and skills best match the JD.\n"
            "3. REWRITE the existing project bullets to mirror the JD's language and keyword priorities "
            "— while keeping all facts 100% accurate.\n"
            "4. Do NOT add projects or bullets that don't exist in the resume.\n"
            "5. Do NOT change dates, company names, or GPAs.\n\n"
            f"CANDIDATE'S RESUME:\n{resume_text}"
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
            f"1. Write a 2-sentence summary tailored to this specific role.\n"
            f"2. List the 8-10 skills from the resume most relevant to this JD.\n"
            f"3. For each project in the resume, rewrite its bullets to emphasize keywords "
            f"from this JD. Keep 2-3 bullets per project. Preserve project titles, tech, dates exactly.\n"
            f"4. Answer these application questions (if any):\n{questions_str}\n\n"
            f"job_id to use in output: {job.id}"
        )

        return await self._call_llm(system_prompt, user_prompt)


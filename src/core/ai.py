import os
import json
import asyncio
from src.core.models import Job, TailoredApplication
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


class AITailor:
    """
    Provider-agnostic AI tailoring engine.

    Reads AI_PROVIDER env var to select backend:
      - "gemini"  → Google Gemini 2.0 Flash (free tier, default)
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
        """Dispatches to the configured provider and returns a TailoredApplication."""
        if self.provider == "gemini":
            return await self._call_gemini(system_prompt, user_prompt)
        return await self._call_openai(system_prompt, user_prompt)

    async def _call_gemini(self, system_prompt: str, user_prompt: str) -> TailoredApplication:
        """Calls Gemini 2.0 Flash with JSON mode, parses response into TailoredApplication."""
        from google.genai import types

        full_prompt = (
            f"{system_prompt}\n\n{user_prompt}\n\n"
            "Respond with ONLY valid JSON matching this exact structure — no markdown, no explanation:\n"
            '{"job_id": "<string>", "tailored_bullets": ["<string>", ...], "q_and_a_responses": {"<question>": "<answer>", ...}}'
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
        )
        return TailoredApplication.model_validate_json(response.text)

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> TailoredApplication:
        """Calls OpenAI gpt-4o-mini with structured Pydantic output."""
        completion = await self._openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            response_format=TailoredApplication,
        )
        return completion.choices[0].message.parsed

    async def tailor_application(self, job: Job) -> TailoredApplication:
        # 1. Ask the Ledger for relevant facts based on the job's required skills
        search_query = f"{job.role} at {job.company}. Skills: {', '.join(job.required_skills)}"
        
        try:
            facts = self.ledger.search_facts(search_query, top_k=4)
        except RuntimeError:
            # Fallback if the index isn't built yet
            facts = []
            
        facts_str = "\n".join([f"- {f}" for f in facts])

        # 2. Build the strict System Prompt enforcing our Hallucination rules
        system_prompt = f"""You are an elite, highly strict Resume Tailor and ATS Optimizer. 
Your ONLY goal is to write resume bullets and answer job questions to help a Co-op software engineer get a job.

CRITICAL RULE: You are FORBIDDEN from inventing or hallucinating ANY experience, tools, or jobs. 
You may ONLY use the verified facts provided below. If the user does not have a skill requested by the job description, do not invent it. Focus on what they DO have.

USER'S VERIFIED FACTS LIBRRAY:
{facts_str}
"""

        # 3. Build the User Prompt telling it what to do for this specific job
        user_prompt = f"""
Please generate a tailored application for the following role:
Company: {job.company}
Role: {job.role}
Job Description: {job.job_description[:1000]}...

Task 1: Write 3-5 ATS-optimized resume bullets emphasizing their background in the context of this job.
Task 2: Answer the following custom application questions:
{', '.join(job.custom_questions) if job.custom_questions else 'None'}
"""
        
        # 4. Call the configured LLM provider
        return await self._call_llm(system_prompt, user_prompt)

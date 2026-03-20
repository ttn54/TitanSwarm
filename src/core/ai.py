import os
import json
from openai import AsyncOpenAI
from src.core.models import Job, TailoredApplication
from src.core.ledger import LedgerManager

class AITailor:
    def __init__(self, ledger_manager: LedgerManager):
        if "OPENAI_API_KEY" not in os.environ:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "The AITailor requires a valid OpenAI API key to run."
            )
        self.client = AsyncOpenAI()
        self.ledger = ledger_manager
        
    async def _call_openai(self, system_prompt: str, user_prompt: str) -> TailoredApplication:
        """Internal wrapped method to call the OpenAI API so it can be mocked in tests"""
        completion = await self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            temperature=0.0, # STRICT constraint against hallucination
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
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
        
        # 4. Call the strict API
        return await self._call_openai(system_prompt, user_prompt)

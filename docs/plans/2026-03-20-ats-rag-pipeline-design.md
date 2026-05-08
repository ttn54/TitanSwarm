# Phase 4: ATS RAG Pipeline (Direct OpenAI Approach)

## 1. Architecture and Data Flow
*   **Approach:** Option A - Direct OpenAI API using Structured Outputs (JSON mode) to guarantee deterministic, un-crashing responses.
*   **Core Component:** `AITailor` class in `src/core/ai.py`.
*   **Data Flow:**
    1.  Receive a scraped `Job` object.
    2.  Query `LedgerManager` for the top 3 verified facts matching the job's `job_description` and `required_skills`.
    3.  Construct a strict system prompt instructing the model to act as an ATS-optimizing resume tailor, with an absolute restriction against hallucinating experience.
    4.  Send the payload to `gpt-4o-mini` with `temperature=0.0`.
    5.  Parse the JSON response directly into a `TailoredApplication` Pydantic model.

## 2. Pydantic Models & Interfaces
*   **New Model (`src/core/models.py`):**
    ```python
    class TailoredApplication(BaseModel):
        job_id: str
        tailored_bullets: List[str]
        q_and_a_responses: dict[str, str]
    ```
*   **AI Interface:**
    *   `__init__(self, ledger_manager: LedgerManager)`
    *   `async def tailor_application(self, job: Job) -> TailoredApplication:`

## 3. Edge Cases & Safety
*   **Missing API Key:** Must loudly raise a `ValueError` with clear instructions if `OPENAI_API_KEY` is not found in the environment.
*   **Hallucinations:** Temperature strictly set to 0.0. "System Prompt" explicitly forbids making up data that is not present in the injected Ledger context.
*   **Malformed JSON:** By using OpenAI's built-in `response_format` with Pydantic, we offload JSON parsing safety to the library itself.
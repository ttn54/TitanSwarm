# AI-Driven Education Rendering Design
**Date:** 2026-04-25
**Status:** Approved

## 1. Goal
Make resume generation AI-first for both work experience bullets and education content, while enforcing source-of-truth constraints (no hallucinations).

## 2. Architecture and Data Flow
1. `AITailor.tailor_application()` will return a new `tailored_education` array in `TailoredApplication`.
2. The AI prompt and response schema will include explicit instructions and JSON shape for education.
3. The resume template will prefer AI output for education (`ai_data.tailored_education`) and only fall back to parsed ledger education when AI output is empty.

## 3. Data Structures
Add a new model in `src/core/models.py`:
- `TailoredEducation`
  - `degree: str`
  - `institution: str`
  - `start_date: str`
  - `end_date: str`
  - `location: str = ""`
  - `bullets: list[str] = []`

Extend `TailoredApplication`:
- `tailored_education: list[TailoredEducation] = []`

## 4. Prompt and Validation Rules
- AI must source education values only from candidate context.
- AI must not invent degree names, schools, GPA, dates, awards, or certifications.
- Degree wording remains exact source wording (no normalization).
- If context has no education section, output an empty list.

## 5. Rendering Rules
In `resume.html`:
- `_edu_to_render = ai_data.tailored_education if ai_data.tailored_education else ledger.education`
- Render `_edu_to_render` in the Education section.

## 6. Safety and Edge Cases
- If AI returns placeholder bullets (e.g. `[X]`, `[Y]`, `[Z]`) in tailored experience/education, trigger one strict retry with explicit anti-placeholder instruction.
- Keep existing behavior as fallback if AI output is missing.

## 7. TDD Plan
1. Add failing model tests for new `tailored_education` field.
2. Add failing template tests for AI-first education rendering and fallback behavior.
3. Implement model + AI schema + template updates.
4. Run targeted tests, then full test suite.

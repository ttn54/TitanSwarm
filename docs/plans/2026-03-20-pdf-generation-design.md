# PDF Generation Design
Date: 2026-03-20

## 1. Architecture and Data Flow
The PDF Generation module uses Python's Jinja2 templating to construct a single-column, strictly structured HTML string that mimics standard, ATS-friendly resume layouts (e.g., "Jake's Resume"). The data is populated using:
- The base `ledger` dictionary representing the verified user history.
- The `ai_data` (A Pydantic `TailoredApplication` object) representing tailored bullet points from the Language Model.

The HTML string is passed directly into a headless `playwright` Chromium browser, which natively prints it out to a `.pdf` file.

## 2. Data Structures and Interfaces
**Inputs:**
- `user_ledger: dict`: A dictionary of personal details and base experience.
- `ai_data: TailoredApplication`: Contains AI-generated `tailored_bullets` and derived information.
- `output_path: str`: Where the PDF should be saved.

**Output:**
Returns the file path of the generated PDF.

## 3. Edge Cases / Failure Modes
- Unicode errors handling special characters from the AI text (Mitigated by HTML+Playwright rendering).
- Layout bleeding onto multiple pages if text is too long.
- Missing fields in `user_ledger` causing Jinja2 to throw undefined attribute errors.

## 4. Integration with Existing Layers
This module acts as the final output bridge of Phase 5, triggered in the Dispatch Terminal after the user approves an application in the stream.

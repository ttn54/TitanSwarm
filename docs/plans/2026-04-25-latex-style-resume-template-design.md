# LaTeX-Style Resume Template Design
Date: 2026-04-25
Status: Approved

## 1. Goal
Adopt a resume layout that closely matches the user-provided LaTeX style while keeping the existing TitanSwarm generation pipeline and preserving this exact section order:
1. TECHNICAL SKILLS
2. WORK EXPERIENCE
3. TECHNICAL PROJECTS
4. EDUCATION

## 2. Architecture and Data Flow
Pipeline remains unchanged:
1. AI tailoring returns structured data.
2. PDF generator renders Jinja template to HTML.
3. Playwright converts HTML into PDF.

Only the resume template is redesigned. No transport, repository, or UI workflow changes are required.

## 3. Rendering Contracts
### 3.1 Header
- Centered name line with strong emphasis.
- Two compact contact rows.
- Dynamic field omission when values are absent.

### 3.2 Section Order (Hard Requirement)
Template will always render sections in this order:
1. Technical Skills
2. Work Experience
3. Technical Projects
4. Education

### 3.3 Data Priority
- Work Experience: use AI-tailored experience first, fallback to ledger experience.
- Education: use AI-tailored education first, fallback to ledger education.

### 3.4 Style Direction
- Compact margins similar to the provided LaTeX output.
- Uppercase section headings with divider lines.
- Dense spacing and concise bullets.
- Strong emphasis on title/date rows with right-aligned dates.

## 4. Safety and Edge Cases
1. Empty section data should cleanly hide that section.
2. Long links must wrap safely.
3. Avoid awkward page breaks splitting entry headers from bullet lists.
4. Preserve source-of-truth constraints (no invented education or experience facts).

## 5. TDD Plan
1. Add failing tests for section order.
2. Add failing tests for header/contact formatting behavior.
3. Add failing tests for AI-first/fallback behavior consistency in reordered sections.
4. Implement template updates.
5. Run targeted tests, then full test suite.

## 6. Integration Notes
- Files impacted:
  - src/core/templates/resume.html
  - tests/test_template_rendering.py
  - tests/test_resume_experience.py (if order assumptions exist)
- No changes needed in repository/network boundaries.

import os
import re
from datetime import date as _date_type
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
from src.core.models import Job, TailoredApplication, CoverLetterResult, UserProfile

def _md_bold(text: str) -> str:
    """Convert **word** markdown bold to HTML <strong> tags for PDF rendering."""
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', str(text))


def compose_cover_letter_html(
    profile: UserProfile,
    company: str,
    role: str,
    cover_letter: CoverLetterResult,
    letter_date: _date_type | None = None,
) -> str:
    """
    Compose the full formal cover letter HTML string from parts.

    The AI supplies only the body paragraphs. This function builds the
    formal shell (candidate header, date, recipient block, Re: line,
    salutation, body, signature) so that formatting is always consistent
    and the AI cannot hallucinate structural elements.
    """
    if letter_date is None:
        letter_date = _date_type.today()

    formatted_date = letter_date.strftime("%B %-d, %Y")

    # Candidate contact line — same pipe-separated style as the resume header
    contact_parts = [p for p in [
        profile.phone, profile.email, profile.linkedin,
        profile.github, profile.website,
    ] if p]
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)

    # Body: convert newlines to <p> tags, preserve bold markdown
    body_paragraphs = [
        f"<p>{_md_bold(para.strip())}</p>"
        for para in cover_letter.body.split("\n\n")
        if para.strip()
    ]
    body_html = "\n".join(body_paragraphs)

    # Recipient address block (only when extracted from JD)
    if cover_letter.company_address:
        addr_lines = "".join(
            f"<div>{line.strip()}</div>"
            for line in cover_letter.company_address.splitlines()
            if line.strip()
        )
        recipient_block = f"""
        <div class="recipient">
            <div>Hiring Manager</div>
            <div>{company}</div>
            {addr_lines}
        </div>"""
    else:
        recipient_block = f"""
        <div class="recipient">
            <div>Hiring Manager</div>
            <div>{company}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Cover Letter — {profile.name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
      font-family: 'Times New Roman', Times, serif;
      font-size: 11pt;
      color: #000;
      line-height: 1.55;
      padding: 52px 64px 52px 64px;
  }}
  .name {{
      text-align: center;
      font-size: 20pt;
      font-weight: bold;
      margin-bottom: 4px;
  }}
  .contact {{
      text-align: center;
      font-size: 9.5pt;
      color: #111;
      margin-bottom: 28px;
  }}
  .date     {{ margin-bottom: 20px; }}
  .recipient {{ margin-bottom: 16px; line-height: 1.45; }}
  .re-line  {{ margin-bottom: 20px; }}
  .body     {{ margin-bottom: 24px; }}
  .body p   {{ margin-bottom: 12px; }}
  .sign     {{ margin-top: 8px; }}
  .page-num {{
      position: fixed; bottom: 24px; right: 56px;
      font-size: 9pt; color: #555;
  }}
</style>
</head>
<body>

<div class="name">{profile.name}</div>
<div class="contact">{contact_line}</div>

<div class="date">{formatted_date}</div>

{recipient_block}

<div class="re-line"><strong>Re: {role}</strong></div>

<div class="body">
{body_html}
</div>

<div class="sign">
    <div>Sincerely,</div>
    <br>
    <div><strong>{profile.name}</strong></div>
</div>

<div class="page-num">1</div>
</body>
</html>"""
    return html

class PDFGenerator:
    def __init__(self, template_dir: str = "templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.env.filters['mdbold'] = _md_bold
    
    async def generate_resume_pdf(self, 
                                  user_ledger: dict, 
                                  ai_data: TailoredApplication, 
                                  output_path: str = "output/resume.pdf") -> str:
        # Load the HTML template
        template = self.env.get_template("resume.html")
        
        # Render the template with injected dictionary data
        rendered_html = template.render(
            personal_info=user_ledger.get("personal_info", {}),
            ledger=user_ledger,
            ai_data=ai_data
        )
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Use Playwright to convert HTML to PDF
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Load the rendered HTML
            await page.set_content(rendered_html)
            
            # Print to standard A4/Letter size without margins 
            await page.pdf(
                path=output_path,
                format="Letter",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
            )
            
            await browser.close()
            
        return output_path

    async def generate_cover_letter_pdf(
        self,
        profile: UserProfile,
        company: str,
        role: str,
        cover_letter: CoverLetterResult,
        output_path: str = "output/cover_letter.pdf",
    ) -> bytes:
        """Render the formal cover letter to PDF and return raw bytes."""
        html = compose_cover_letter_html(profile, company, role, cover_letter)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html)
            pdf_bytes = await page.pdf(
                format="Letter",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            await browser.close()
        # Also write to disk so the download button can serve the file
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        return pdf_bytes

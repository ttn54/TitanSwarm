import os
import re
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
from src.core.models import Job, TailoredApplication

def _md_bold(text: str) -> str:
    """Convert **word** markdown bold to HTML <strong> tags for PDF rendering."""
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', str(text))

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

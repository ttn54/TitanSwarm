import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.models import Job, TailoredApplication, TailoredProject, TailoredExperience
from src.core.pdf_generator import PDFGenerator

@pytest.fixture
def mock_ledger():
    return {
        "personal_info": {
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "phone": "123-456-7890",
            "linkedin": "linkedin.com/in/janedoe",
            "github": "github.com/janedoe",
        },
        "experience": [
            {
                "title": "Software Engineer Intern",
                "company": "Tech Corp",
                "start_date": "May 2024",
                "end_date": "Aug 2024",
                "location": "San Francisco, CA",
                "bullets": ["Optimized backend", "Wrote unit tests"]
            }
        ]
    }

@pytest.fixture
def mock_ai_data():
    return TailoredApplication(
        job_id="test_job_123",
        skills_to_highlight={
            "Languages": ["Python", "Go"],
            "Backend & Systems": ["FastAPI"],
        },
        tailored_projects=[
            TailoredProject(
                title="TitanStore",
                tech="Go, Docker",
                date="Jan 2026 – Present",
                project_type="Personal Project",
                bullets=["Built Raft consensus.", "Used gRPC."],
            )
        ],
        tailored_experience=[
            TailoredExperience(
                title="Server",
                company="Pho Goodness Restaurant",
                start_date="Jan 2024",
                end_date="Present",
                location="Burnaby, BC",
                bullets=["Maintained 3.74 GPA while working 20+ hrs/week."],
            )
        ],
        q_and_a_responses={"Will you require sponsorship?": "No"},
    )

@pytest.mark.asyncio
async def test_pdf_generator_creates_pdf(mock_ledger, mock_ai_data):
    # We will mock the jinja environment rendering so we don't need real templates for the unit test,
    # or we can mock playwright and test the entire thing including jinja rendering if we provide a test template.
    # Let's mock playwright and use a dummy template directory to see it fail.
    
    with patch("src.core.pdf_generator.BrowserManager") as mock_manager_class, \
         patch("src.core.pdf_generator.Environment") as mock_env:
        
        # Setup mock Jinja2 environment
        mock_template = MagicMock()
        mock_template.render.return_value = "<html><body>Mock PDF</body></html>"
        mock_env_instance = mock_env.return_value
        mock_env_instance.get_template.return_value = mock_template
        
        # Setup mock BrowserManager
        mock_manager = AsyncMock()
        mock_manager.render_pdf.return_value = b"MOCK_PDF_BYTES"
        mock_manager_class.get_instance.return_value = mock_manager
        
        generator = PDFGenerator(template_dir="dummy_dir")
        
        output_file = "test_output/resume.pdf"
        result = await generator.generate_resume_pdf(
            user_ledger=mock_ledger,
            ai_data=mock_ai_data,
            output_path=output_file
        )
        
        assert result == output_file
        mock_env_instance.get_template.assert_called_with("resume.html")
        mock_template.render.assert_called_once()
        
        # Check BrowserManager commands
        mock_manager.render_pdf.assert_called_once_with("<html><body>Mock PDF</body></html>")

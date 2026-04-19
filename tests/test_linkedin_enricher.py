import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.core.linkedin_enricher import LinkedInEnricher, LinkedInScrapeError

@pytest.fixture
def enricher():
    import os
    # Temporarily bypass the session file path for the fixture
    e = LinkedInEnricher()
    e.session_file = "/fake/session.json"
    return e

def test_extract_username_various_formats(enricher):
    assert enricher._extract_username("williamhgates") == "williamhgates"
    assert enricher._extract_username("https://www.linkedin.com/in/alex27273/") == "alex27273"
    assert enricher._extract_username("linkedin.com/in/john-doe?foo=bar") == "john-doe"

@pytest.mark.asyncio
async def test_enricher_raises_scraper_error_on_missing_session(enricher):
    with pytest.raises(LinkedInScrapeError, match="Session file not found"):
         await enricher.fetch_profile("williamhgates")

@pytest.mark.asyncio
@patch("os.path.exists", return_value=True)
@patch("src.core.linkedin_enricher.BrowserManager")
@patch("src.core.linkedin_enricher.PersonScraper")
async def test_enricher_fetches_profile_successfully(mock_PersonScraper, mock_BrowserManager, mock_exists, enricher):
    # Mocking the async context manager and its methods
    mock_browser = AsyncMock()
    mock_BrowserManager.return_value.__aenter__.return_value = mock_browser
    
    mock_scraper = AsyncMock()
    mock_PersonScraper.return_value = mock_scraper
    
    # Mock return model of linkedin_scraper.Person
    mock_person = MagicMock()
    
    # Create fake Experience
    exp1 = MagicMock()
    exp1.company = "Tech Corp"
    exp1.title = "SE"
    exp1.start_date = "2020-01"
    exp1.end_date = "2022-01"
    exp1.description = "Some description"
    exp1.location = "Remote"
    mock_person.experiences = [exp1]
    
    # Create fake Education
    edu1 = MagicMock()
    edu1.institution = "State Univ"
    edu1.degree = "BSCS"
    edu1.start_date = "2016"
    edu1.end_date = "2020"
    mock_person.educations = [edu1]
    
    mock_scraper.scrape.return_value = mock_person

    profile_data = await enricher.fetch_profile("alex27273")

    assert profile_data["experience"][0]["company"] == "Tech Corp"
    assert profile_data["education"][0]["institution"] == "State Univ"

    mock_scraper.scrape.assert_called_once_with("https://www.linkedin.com/in/alex27273/")

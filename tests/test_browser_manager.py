import pytest
import asyncio
from src.infrastructure.browser import BrowserManager

@pytest.mark.asyncio
async def test_browser_manager_starts_and_stops():
    """Verify that the BrowserManager singleton can start and stop cleanly."""
    manager = BrowserManager.get_instance()
    
    # Needs to be able to start the background thread and headless browser
    await manager.start()
    assert manager._running == True
    
    # Ensure it's thread-safe and can execute simple commands
    html_content = "<h1>Hello World!</h1>"
    # Should generate a PDF from the background loop and return the bytes
    pdf_bytes = await manager.render_pdf(html_content)
    
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100 # Should be a valid PDF structure
    
    # Needs to shut down cleanly without leaving zombies
    await manager.stop()
    assert manager._running == False

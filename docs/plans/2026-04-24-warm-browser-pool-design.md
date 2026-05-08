# Warm Browser Pool Design
**Date:** 2026-04-24
**Status:** Approved

## 1. Architecture and Data Flow
Currently, `async_playwright()` is instantiated from scratch every time Streamlit needs to render a PDF or scrape a lazy-loaded LinkedIn description. Streamlit's `asyncio.run()` destroys the event loop after every button click, preventing a simple persistent async object.

To solve this, we will build a **BrowserManager Singleton**:
- A dedicated, permanent background Thread runs its own `asyncio` Event Loop.
- This loop launches a single Headless Chromium instance once.
- The UI (Streamlit) sends coroutines to this background thread using `asyncio.run_coroutine_threadsafe()`.
- The background thread executes the Playwright commands (e.g. `page.pdf()`), and returns the result/Future back to the main thread securely.

## 2. Data Structures & Interfaces
We will create `src/infrastructure/browser.py`:
```python
class BrowserManager:
    _instance: "BrowserManager"
    
    def start(self): ...
    def stop(self): ...
    async def render_pdf(self, html: str, output_path: str) -> bytes: ...
    async def fetch_text(self, url: str) -> str: ...
```

## 3. Edge Cases & Resilience
- **Zombie Processes:** We will use the `atexit` standard library to register `BrowserManager.stop()`. If the Streamlit server crashes or is stopped via Ctrl+C, the background thread will be signaled to close the Playwright cleanly, preventing RAM leaks.
- **Thread Safety:** All Playwright objects (browser, page) belong strictly to the background loop. The main thread will *only* pass strings (HTML/URLs) and receive bytes/strings back. No Playwright objects will cross the thread boundary.

## 4. Integration
- Refactor `src/core/pdf_generator.py` to strip out `async_playwright` and call `browser_manager.render_pdf()`.
- Refactor `src/core/ai.py` (`fetch_missing_description`) to call `browser_manager.fetch_text()`.
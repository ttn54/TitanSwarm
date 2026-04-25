import asyncio
import threading
import atexit
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class BrowserManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._start_loop, daemon=True)
        self._playwright = None
        self._browser = None
        self._running = False
        self._initialized = True
        atexit.register(self._sync_stop)

    @classmethod
    def get_instance(cls) -> "BrowserManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def _start_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def start(self):
        if self._running:
            return
        if not self._thread.is_alive():
            self._thread.start()
        
        while not self._loop.is_running():
            await asyncio.sleep(0.01)
        
        future = asyncio.run_coroutine_threadsafe(self._init_browser(), self._loop)
        await asyncio.wrap_future(future)
        self._running = True
        logger.info("BrowserManager: Background chromium browser started.")

    async def _init_browser(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)

    async def stop(self):
        if not self._running:
            return
        future = asyncio.run_coroutine_threadsafe(self._close_browser(), self._loop)
        await asyncio.wrap_future(future)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._running = False
        logger.info("BrowserManager: Background chromium browser stopped.")

    def _sync_stop(self):
        """Called automatically on application exit."""
        if self._running and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._close_browser(), self._loop)
            try:
                future.result(timeout=3.0)
            except Exception:
                pass

    async def _close_browser(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def render_pdf(self, html: str) -> bytes:
        if not self._running:
            await self.start()
        future = asyncio.run_coroutine_threadsafe(self._render_pdf_internal(html), self._loop)
        return await asyncio.wrap_future(future)

    async def _render_pdf_internal(self, html: str) -> bytes:
        page = await self._browser.new_page()
        await page.set_content(html)
        pdf_bytes = await page.pdf(
            format="Letter",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
        )
        await page.close()
        return pdf_bytes

    async def fetch_text(self, url: str) -> str:
        if not self._running:
            await self.start()
        future = asyncio.run_coroutine_threadsafe(self._fetch_text_internal(url), self._loop)
        return await asyncio.wrap_future(future)

    async def _fetch_text_internal(self, url: str) -> str:
        page = await self._browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            text = await page.evaluate("document.body.innerText")
        except Exception as e:
            logger.error(f"Error fetching text from {url}: {e}")
            text = ""
        finally:
            await page.close()
        return text
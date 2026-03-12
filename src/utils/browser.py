"""Playwright browser manager for web scraping."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = structlog.get_logger(__name__)


class BrowserManager:
    """Manages Playwright browser lifecycle for scraping."""

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        timeout: int = 30000,
        user_agent: str | None = None,
    ) -> None:
        """Initialize browser manager.

        Args:
            headless: Run browser in headless mode.
            slow_mo: Slow down operations by this many milliseconds.
            timeout: Default timeout for operations in milliseconds.
            user_agent: Custom user agent string.
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        """Start the browser."""
        if self._browser is not None:
            return

        logger.info("browser.starting", headless=self.headless)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
        )
        logger.info("browser.started")

    async def stop(self) -> None:
        """Stop the browser and cleanup resources."""
        if self._browser is not None:
            logger.info("browser.stopping")
            await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
            logger.info("browser.stopped")

    @property
    def is_running(self) -> bool:
        """Check if browser is running."""
        return self._browser is not None

    async def new_context(self) -> BrowserContext:
        """Create a new browser context with default settings.

        Returns:
            A new browser context.

        Raises:
            RuntimeError: If browser is not started.
        """
        if self._browser is None:
            raise RuntimeError("Browser not started. Call start() first.")

        context = await self._browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        context.set_default_timeout(self.timeout)
        return context

    async def new_page(self) -> Page:
        """Create a new page in a new context.

        Returns:
            A new page.

        Raises:
            RuntimeError: If browser is not started.
        """
        context = await self.new_context()
        return await context.new_page()

    @asynccontextmanager
    async def page_context(self) -> AsyncIterator[Page]:
        """Context manager for creating and cleaning up a page.

        Yields:
            A new page that will be closed on exit.

        Raises:
            RuntimeError: If browser is not started.
        """
        context = await self.new_context()
        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()

    async def __aenter__(self) -> "BrowserManager":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.stop()

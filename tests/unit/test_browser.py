"""Unit tests for browser manager."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.utils.browser import BrowserManager


@pytest.mark.unit
class TestBrowserManagerInit:
    """Tests for BrowserManager initialization."""

    def test_default_settings(self):
        """Default settings are applied."""
        manager = BrowserManager()
        assert manager.headless is True
        assert manager.slow_mo == 0
        assert manager.timeout == 30000
        assert "Mozilla" in manager.user_agent

    def test_custom_settings(self):
        """Custom settings are applied."""
        manager = BrowserManager(
            headless=False,
            slow_mo=100,
            timeout=60000,
            user_agent="Custom Agent",
        )
        assert manager.headless is False
        assert manager.slow_mo == 100
        assert manager.timeout == 60000
        assert manager.user_agent == "Custom Agent"

    def test_not_running_initially(self):
        """Browser is not running after initialization."""
        manager = BrowserManager()
        assert manager.is_running is False


@pytest.mark.unit
class TestBrowserManagerLifecycle:
    """Tests for browser lifecycle with mocks."""

    @pytest.fixture
    def mock_playwright(self):
        """Create mock playwright."""
        with patch("src.utils.browser.async_playwright") as mock:
            mock_pw = AsyncMock()
            mock_browser = AsyncMock()
            mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
            mock.return_value.start = AsyncMock(return_value=mock_pw)
            yield mock, mock_pw, mock_browser

    async def test_start_creates_browser(self, mock_playwright):
        """Starting creates a browser instance."""
        mock_async_pw, mock_pw, mock_browser = mock_playwright

        manager = BrowserManager()
        await manager.start()

        assert manager.is_running is True
        mock_pw.chromium.launch.assert_called_once_with(
            headless=True,
            slow_mo=0,
        )

    async def test_start_idempotent(self, mock_playwright):
        """Calling start multiple times is safe."""
        mock_async_pw, mock_pw, mock_browser = mock_playwright

        manager = BrowserManager()
        await manager.start()
        await manager.start()  # Should not raise

        # Should only launch once
        assert mock_pw.chromium.launch.call_count == 1

    async def test_stop_closes_browser(self, mock_playwright):
        """Stopping closes the browser."""
        mock_async_pw, mock_pw, mock_browser = mock_playwright

        manager = BrowserManager()
        await manager.start()
        await manager.stop()

        assert manager.is_running is False
        mock_browser.close.assert_called_once()

    async def test_stop_without_start_safe(self):
        """Stopping without starting is safe."""
        manager = BrowserManager()
        await manager.stop()  # Should not raise

    async def test_context_manager(self, mock_playwright):
        """Context manager starts and stops browser."""
        mock_async_pw, mock_pw, mock_browser = mock_playwright

        async with BrowserManager() as manager:
            assert manager.is_running is True

        mock_browser.close.assert_called_once()


@pytest.mark.unit
class TestBrowserManagerPages:
    """Tests for page creation with mocks."""

    @pytest.fixture
    def started_manager(self):
        """Create a started browser manager with mocks."""
        manager = BrowserManager()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        # set_default_timeout is a sync method
        mock_context.set_default_timeout = MagicMock()

        manager._browser = mock_browser
        return manager, mock_browser, mock_context, mock_page

    async def test_new_context_creates_context(self, started_manager):
        """new_context creates a browser context."""
        manager, mock_browser, mock_context, _ = started_manager

        context = await manager.new_context()

        assert context == mock_context
        mock_browser.new_context.assert_called_once()

    async def test_new_context_sets_viewport(self, started_manager):
        """new_context sets viewport size."""
        manager, mock_browser, _, _ = started_manager

        await manager.new_context()

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["viewport"] == {"width": 1920, "height": 1080}

    async def test_new_context_requires_running_browser(self):
        """new_context raises if browser not started."""
        manager = BrowserManager()

        with pytest.raises(RuntimeError, match="Browser not started"):
            await manager.new_context()

    async def test_new_page_creates_page(self, started_manager):
        """new_page creates a page in a new context."""
        manager, _, mock_context, mock_page = started_manager

        page = await manager.new_page()

        assert page == mock_page
        mock_context.new_page.assert_called_once()

    async def test_page_context_yields_page(self, started_manager):
        """page_context yields a page."""
        manager, _, mock_context, mock_page = started_manager

        async with manager.page_context() as page:
            assert page == mock_page

    async def test_page_context_closes_context(self, started_manager):
        """page_context closes context on exit."""
        manager, _, mock_context, mock_page = started_manager

        async with manager.page_context():
            pass

        mock_context.close.assert_called_once()

    async def test_page_context_closes_on_exception(self, started_manager):
        """page_context closes context even on exception."""
        manager, _, mock_context, _ = started_manager

        with pytest.raises(ValueError):
            async with manager.page_context():
                raise ValueError("Test error")

        mock_context.close.assert_called_once()


@pytest.mark.unit
class TestBrowserManagerUserAgent:
    """Tests for user agent handling."""

    def test_default_user_agent_looks_like_browser(self):
        """Default user agent resembles a real browser."""
        manager = BrowserManager()
        assert "Mozilla" in manager.user_agent
        assert "Chrome" in manager.user_agent
        assert "Safari" in manager.user_agent

    def test_custom_user_agent_used(self):
        """Custom user agent is used."""
        manager = BrowserManager(user_agent="CustomBot/1.0")
        assert manager.user_agent == "CustomBot/1.0"

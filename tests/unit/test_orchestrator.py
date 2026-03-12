"""Unit tests for orchestrator."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.rate import SavingsRate
from src.models.types import ProductType, Provider, RateType, TemboProduct
from src.orchestrator import Orchestrator, OrchestratorResult, ScrapeResult
from src.storage.base import StorageBackend
from src.utils.browser import BrowserManager
from src.utils.rate_limiter import RateLimiter


@pytest.fixture
def mock_browser():
    """Create mock browser manager."""
    browser = MagicMock(spec=BrowserManager)
    return browser


@pytest.fixture
def mock_storage():
    """Create mock storage backend."""
    storage = MagicMock(spec=StorageBackend)
    storage.append = MagicMock()
    return storage


@pytest.fixture
def sample_rate() -> SavingsRate:
    """Create sample rate."""
    return SavingsRate(
        provider=Provider.TEMBO,
        product_name=TemboProduct.CASH_ISA,
        product_type=ProductType.CASH_ISA,
        rate=Decimal("4.55"),
        rate_type=RateType.VARIABLE,
        scraped_at=datetime.now(timezone.utc),
    )


@pytest.mark.unit
class TestScrapeResult:
    """Tests for ScrapeResult dataclass."""

    def test_default_values(self):
        """ScrapeResult has correct defaults."""
        result = ScrapeResult(provider=Provider.TEMBO)
        assert result.success is True
        assert result.rates == []
        assert result.error is None
        assert result.duration_seconds == 0.0

    def test_with_rates(self, sample_rate):
        """ScrapeResult stores rates."""
        result = ScrapeResult(
            provider=Provider.TEMBO,
            rates=[sample_rate],
            duration_seconds=1.5,
        )
        assert len(result.rates) == 1
        assert result.duration_seconds == 1.5


@pytest.mark.unit
class TestOrchestratorResult:
    """Tests for OrchestratorResult dataclass."""

    def test_default_values(self):
        """OrchestratorResult has correct defaults."""
        result = OrchestratorResult()
        assert result.total_rates == 0
        assert result.successful_providers == 0
        assert result.failed_providers == 0
        assert result.results == []

    def test_all_rates(self, sample_rate):
        """all_rates aggregates rates from all results."""
        result = OrchestratorResult(
            results=[
                ScrapeResult(provider=Provider.TEMBO, rates=[sample_rate]),
                ScrapeResult(provider=Provider.CHIP, rates=[sample_rate]),
            ]
        )
        assert len(result.all_rates) == 2

    def test_duration(self):
        """duration_seconds calculates correctly."""
        start = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 12, 10, 0, 5, tzinfo=timezone.utc)
        result = OrchestratorResult(started_at=start, completed_at=end)
        assert result.duration_seconds == 5.0

    def test_duration_not_completed(self):
        """duration_seconds is 0 if not completed."""
        result = OrchestratorResult()
        assert result.duration_seconds == 0.0


@pytest.mark.unit
class TestOrchestratorInit:
    """Tests for Orchestrator initialization."""

    def test_default_providers(self, mock_browser):
        """Orchestrator defaults to all providers."""
        orch = Orchestrator(browser=mock_browser)
        assert set(orch.providers) == {Provider.TEMBO, Provider.CHIP, Provider.MONEYBOX}

    def test_custom_providers(self, mock_browser):
        """Orchestrator accepts custom provider list."""
        orch = Orchestrator(
            browser=mock_browser,
            providers=[Provider.TEMBO],
        )
        assert orch.providers == [Provider.TEMBO]

    def test_with_storage(self, mock_browser, mock_storage):
        """Orchestrator accepts storage backend."""
        orch = Orchestrator(browser=mock_browser, storage=mock_storage)
        assert orch.storage == mock_storage

    def test_default_rate_limiter(self, mock_browser):
        """Orchestrator creates default rate limiter."""
        orch = Orchestrator(browser=mock_browser)
        assert orch.rate_limiter is not None


@pytest.mark.unit
class TestOrchestratorRun:
    """Tests for Orchestrator.run()."""

    async def test_runs_all_providers(self, mock_browser, sample_rate):
        """Run executes scrapers for all providers."""
        with patch.object(
            Orchestrator, "_scrape_provider", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = ScrapeResult(
                provider=Provider.TEMBO, rates=[sample_rate]
            )

            orch = Orchestrator(browser=mock_browser)
            result = await orch.run()

            assert mock_scrape.call_count == 3  # All providers

    async def test_aggregates_results(self, mock_browser, sample_rate):
        """Run aggregates results from all providers."""
        with patch.object(
            Orchestrator, "_scrape_provider", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = ScrapeResult(
                provider=Provider.TEMBO, rates=[sample_rate]
            )

            orch = Orchestrator(browser=mock_browser)
            result = await orch.run()

            assert result.successful_providers == 3
            assert result.total_rates == 3

    async def test_handles_failures(self, mock_browser):
        """Run continues after provider failure."""
        call_count = 0

        async def mock_scrape(provider):
            nonlocal call_count
            call_count += 1
            if provider == Provider.TEMBO:
                return ScrapeResult(
                    provider=provider,
                    success=False,
                    error="Test error",
                )
            return ScrapeResult(provider=provider, rates=[])

        with patch.object(Orchestrator, "_scrape_provider", side_effect=mock_scrape):
            orch = Orchestrator(browser=mock_browser)
            result = await orch.run()

            assert result.failed_providers == 1
            assert result.successful_providers == 2

    async def test_saves_to_storage(self, mock_browser, mock_storage, sample_rate):
        """Run saves rates to storage."""
        with patch.object(
            Orchestrator, "_scrape_provider", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = ScrapeResult(
                provider=Provider.TEMBO, rates=[sample_rate]
            )

            orch = Orchestrator(browser=mock_browser, storage=mock_storage)
            await orch.run()

            mock_storage.append.assert_called_once()


@pytest.mark.unit
class TestOrchestratorIsolation:
    """Tests for failure isolation."""

    async def test_exception_doesnt_stop_others(self, mock_browser):
        """Exception in one scraper doesn't stop others."""
        call_count = 0

        async def mock_scrape(provider):
            nonlocal call_count
            call_count += 1
            if provider == Provider.TEMBO:
                raise Exception("Test exception")
            return ScrapeResult(provider=provider, rates=[])

        with patch.object(Orchestrator, "_scrape_provider", side_effect=mock_scrape):
            orch = Orchestrator(browser=mock_browser)
            result = await orch.run()

            # All providers attempted
            assert call_count == 3
            # One failed
            assert result.failed_providers == 1
            # Others succeeded
            assert result.successful_providers == 2


@pytest.mark.unit
class TestOrchestratorGetScraper:
    """Tests for get_scraper method."""

    def test_returns_scraper_for_valid_provider(self, mock_browser):
        """Returns scraper instance for valid provider."""
        orch = Orchestrator(browser=mock_browser)
        scraper = orch.get_scraper(Provider.TEMBO)

        assert scraper is not None
        assert scraper.provider == Provider.TEMBO

    def test_returns_none_for_invalid_provider(self, mock_browser):
        """Returns None for unregistered provider."""
        orch = Orchestrator(browser=mock_browser)
        # Clear scrapers to simulate missing registration
        orch.SCRAPER_CLASSES = {}

        scraper = orch.get_scraper(Provider.TEMBO)
        assert scraper is None

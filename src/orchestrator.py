"""Scraping orchestrator for running multiple provider scrapers."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from src.exceptions.scraping import ScrapingError
from src.models.rate import SavingsRate
from src.models.types import Provider
from src.scrapers.base import BaseScraper
from src.scrapers.chip import ChipScraper
from src.scrapers.moneybox import MoneyboxScraper
from src.scrapers.tembo import TemboScraper
from src.storage.base import StorageBackend
from src.utils.browser import BrowserManager
from src.utils.rate_limiter import RateLimiter

logger = structlog.get_logger(__name__)


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""

    provider: Provider
    rates: list[SavingsRate] = field(default_factory=list)
    success: bool = True
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class OrchestratorResult:
    """Combined result of all scraping operations."""

    results: list[ScrapeResult] = field(default_factory=list)
    total_rates: int = 0
    successful_providers: int = 0
    failed_providers: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @property
    def all_rates(self) -> list[SavingsRate]:
        """Get all rates from all providers."""
        rates = []
        for result in self.results:
            rates.extend(result.rates)
        return rates

    @property
    def duration_seconds(self) -> float:
        """Total duration of scraping."""
        if self.completed_at is None:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()


class Orchestrator:
    """Orchestrates scraping across multiple providers."""

    SCRAPER_CLASSES: dict[Provider, type[BaseScraper]] = {
        Provider.TEMBO: TemboScraper,
        Provider.CHIP: ChipScraper,
        Provider.MONEYBOX: MoneyboxScraper,
    }

    def __init__(
        self,
        browser: BrowserManager,
        storage: StorageBackend | None = None,
        rate_limiter: RateLimiter | None = None,
        providers: list[Provider] | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            browser: Browser manager for page access.
            storage: Optional storage backend for saving rates.
            rate_limiter: Optional rate limiter for throttling.
            providers: List of providers to scrape. If None, scrapes all.
        """
        self.browser = browser
        self.storage = storage
        self.rate_limiter = rate_limiter or RateLimiter()
        self.providers = providers or list(Provider)
        self._log = logger.bind(component="orchestrator")

    async def run(self) -> OrchestratorResult:
        """Run scraping for all configured providers.

        Returns:
            OrchestratorResult with all rates and statistics.
        """
        result = OrchestratorResult()
        self._log.info(
            "orchestrator.start",
            providers=[p.value for p in self.providers],
        )

        # Run scrapers for each provider
        tasks = [self._scrape_provider(p) for p in self.providers]
        scrape_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for provider, scrape_result in zip(self.providers, scrape_results, strict=True):
            if isinstance(scrape_result, BaseException):
                result.results.append(
                    ScrapeResult(
                        provider=provider,
                        success=False,
                        error=str(scrape_result),
                    )
                )
                result.failed_providers += 1
            else:
                result.results.append(scrape_result)
                if scrape_result.success:
                    result.successful_providers += 1
                    result.total_rates += len(scrape_result.rates)
                else:
                    result.failed_providers += 1

        result.completed_at = datetime.now(timezone.utc)

        # Save to storage if configured
        if self.storage and result.total_rates > 0:
            self._save_rates(result.all_rates)

        self._log.info(
            "orchestrator.complete",
            total_rates=result.total_rates,
            successful=result.successful_providers,
            failed=result.failed_providers,
            duration_seconds=result.duration_seconds,
        )

        return result

    async def _scrape_provider(self, provider: Provider) -> ScrapeResult:
        """Scrape a single provider.

        Args:
            provider: Provider to scrape.

        Returns:
            ScrapeResult with rates or error.
        """
        start_time = datetime.now(timezone.utc)
        self._log.info("orchestrator.provider.start", provider=provider.value)

        try:
            # Check rate limiter
            if not await self.rate_limiter.acquire(provider.value):
                return ScrapeResult(
                    provider=provider,
                    success=False,
                    error="Rate limited - circuit breaker open",
                )

            # Get scraper class and instantiate
            scraper_class = self.SCRAPER_CLASSES.get(provider)
            if scraper_class is None:
                return ScrapeResult(
                    provider=provider,
                    success=False,
                    error=f"No scraper registered for {provider.value}",
                )

            scraper = scraper_class(browser=self.browser)
            rates = await scraper.scrape()

            # Record success
            self.rate_limiter.record_success(provider.value)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self._log.info(
                "orchestrator.provider.success",
                provider=provider.value,
                rates_found=len(rates),
                duration_seconds=duration,
            )

            return ScrapeResult(
                provider=provider,
                rates=rates,
                success=True,
                duration_seconds=duration,
            )

        except ScrapingError as e:
            self.rate_limiter.record_failure(provider.value)
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            self._log.warning(
                "orchestrator.provider.failed",
                provider=provider.value,
                error=str(e),
                duration_seconds=duration,
            )

            return ScrapeResult(
                provider=provider,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )

    def _save_rates(self, rates: list[SavingsRate]) -> None:
        """Save rates to storage.

        Args:
            rates: Rates to save.
        """
        if self.storage is None:
            return

        try:
            self.storage.append(rates)
            self._log.info("orchestrator.storage.saved", count=len(rates))
        except Exception as e:
            self._log.error("orchestrator.storage.error", error=str(e))

    def get_scraper(self, provider: Provider) -> BaseScraper | None:
        """Get scraper instance for a provider.

        Args:
            provider: Provider to get scraper for.

        Returns:
            Scraper instance or None if not registered.
        """
        scraper_class = self.SCRAPER_CLASSES.get(provider)
        if scraper_class:
            return scraper_class(browser=self.browser)
        return None

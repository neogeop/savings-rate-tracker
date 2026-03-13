"""Abstract base scraper class."""

import re
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from playwright.async_api import Page

from src.exceptions.scraping import RateExtractionError, SelectorNotFoundError
from src.models.rate import SavingsRate
from src.models.types import Provider
from src.utils.browser import BrowserManager

logger = structlog.get_logger(__name__)

# Common patterns for extracting interest rates
RATE_PATTERNS = [
    re.compile(r"(\d+\.?\d*)\s*%"),  # "4.55%" or "4.55 %"
    re.compile(r"(\d+\.?\d*)\s*per\s*cent", re.IGNORECASE),  # "4.55 per cent"
    re.compile(r"(\d+\.?\d*)\s*percent", re.IGNORECASE),  # "4.55 percent"
    re.compile(r"AER\s*:?\s*(\d+\.?\d*)", re.IGNORECASE),  # "AER: 4.55" or "AER 4.55"
    re.compile(r"(\d+\.?\d*)\s*AER", re.IGNORECASE),  # "4.55 AER"
]


class BaseScraper(ABC):
    """Abstract base class for provider scrapers."""

    def __init__(
        self,
        browser: BrowserManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize scraper.

        Args:
            browser: Browser manager for page access.
            config: Provider-specific configuration.
        """
        self.browser = browser
        self.config = config or {}
        self._log = logger.bind(provider=self.provider.value)

    @property
    @abstractmethod
    def provider(self) -> Provider:
        """Return the provider this scraper handles."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base URL for the provider."""

    @abstractmethod
    async def scrape(self) -> list[SavingsRate]:
        """Scrape all savings rates from the provider.

        Returns:
            List of scraped savings rates.

        Raises:
            ScrapingError: If scraping fails.
        """

    async def get_page_content(self, url: str, wait_selector: str | None = None) -> str:
        """Navigate to URL and get page content.

        Args:
            url: URL to navigate to.
            wait_selector: Optional selector to wait for before getting content.

        Returns:
            HTML content of the page.

        Raises:
            SelectorNotFoundError: If wait_selector is not found.
        """
        self._log.info("scrape.page.loading", url=url)

        async with self.browser.page_context() as page:
            await page.goto(url, wait_until="domcontentloaded")

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception as e:
                    raise SelectorNotFoundError(
                        f"Selector '{wait_selector}' not found",
                        url=url,
                        selector=wait_selector,
                    ) from e

            content = await page.content()
            self._log.info("scrape.page.loaded", url=url, content_length=len(content))
            return content

    async def get_element_text(
        self, page: Page, selector: str, url: str | None = None
    ) -> str:
        """Get text content of an element.

        Args:
            page: Playwright page.
            selector: CSS selector for the element.
            url: URL for error context.

        Returns:
            Text content of the element.

        Raises:
            SelectorNotFoundError: If selector matches no elements.
        """
        element = await page.query_selector(selector)
        if element is None:
            raise SelectorNotFoundError(
                f"Element not found: {selector}",
                url=url,
                selector=selector,
            )
        text = await element.text_content()
        return (text or "").strip()

    def extract_rate(self, text: str, url: str | None = None) -> Decimal:
        """Extract interest rate from text.

        Args:
            text: Text containing rate information.
            url: URL for error context.

        Returns:
            Extracted rate as Decimal.

        Raises:
            RateExtractionError: If no rate can be extracted.
        """
        for pattern in RATE_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    rate = Decimal(match.group(1))
                    if self.validate_rate(rate):
                        self._log.debug(
                            "rate.extracted", raw_text=text[:50], rate=str(rate)
                        )
                        return rate
                except InvalidOperation:
                    continue

        raise RateExtractionError(
            f"Could not extract rate from text: {text[:100]}",
            url=url,
            raw_text=text[:200],
        )

    def validate_rate(self, rate: Decimal) -> bool:
        """Validate that a rate is within expected bounds.

        Args:
            rate: Rate to validate.

        Returns:
            True if rate is valid, False otherwise.
        """
        # Rates should be between 0% and 15%
        if rate < Decimal("0") or rate > Decimal("15"):
            self._log.warning("rate.invalid", rate=str(rate))
            return False
        return True

    def extract_all_rates(self, text: str) -> list[Decimal]:
        """Extract all rates from text.

        Args:
            text: Text containing rate information.

        Returns:
            List of extracted rates.
        """
        rates = []
        for pattern in RATE_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    rate = Decimal(match.group(1))
                    if self.validate_rate(rate):
                        rates.append(rate)
                except InvalidOperation:
                    continue
        return list(set(rates))  # Remove duplicates

    def extract_rate_with_pattern(self, text: str, pattern: str) -> Decimal | None:
        """Extract rate using a custom regex pattern.

        Args:
            text: Text to search.
            pattern: Regex pattern with one capture group for the rate.

        Returns:
            Extracted rate or None if not found/invalid.
        """
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                rate = Decimal(match.group(1))
                if self.validate_rate(rate):
                    self._log.debug(
                        "rate.pattern_match", pattern=pattern, rate=str(rate)
                    )
                    return rate
            except (IndexError, ValueError, InvalidOperation):
                pass
        return None

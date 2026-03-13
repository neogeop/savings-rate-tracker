"""Tembo Money scraper implementation."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup

from src.exceptions.scraping import RateExtractionError, SelectorNotFoundError
from src.models.rate import SavingsRate
from src.models.types import ProductType, Provider, RateType, TemboProduct
from src.scrapers.base import BaseScraper
from src.utils.browser import BrowserManager

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "providers" / "tembo.yaml"


class TemboScraper(BaseScraper):
    """Scraper for Tembo Money savings products."""

    def __init__(
        self,
        browser: BrowserManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize Tembo scraper.

        Args:
            browser: Browser manager for page access.
            config: Optional config override. If not provided, loads from YAML.
        """
        if config is None:
            config = self._load_config()
        super().__init__(browser, config)

    @staticmethod
    def _load_config() -> dict[str, Any]:
        """Load configuration from YAML file."""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f)
                return dict(data) if data else {}
        return {}

    @property
    def provider(self) -> Provider:
        """Return Tembo provider."""
        return Provider.TEMBO

    @property
    def base_url(self) -> str:
        """Return Tembo base URL."""
        return str(self.config.get("base_url", "https://www.tembomoney.com"))

    async def scrape(self) -> list[SavingsRate]:
        """Scrape all Tembo savings rates.

        Returns:
            List of scraped savings rates.
        """
        rates: list[SavingsRate] = []
        products = self.config.get("products", [])

        for product_config in products:
            try:
                rate = await self._scrape_product(product_config)
                if rate:
                    rates.append(rate)
            except Exception as e:
                self._log.warning(
                    "scrape.product.failed",
                    product=product_config.get("name"),
                    error=str(e),
                )

        self._log.info("scrape.complete", provider="tembo", rates_found=len(rates))
        return rates

    async def _scrape_product(self, product_config: dict[str, Any]) -> SavingsRate | None:
        """Scrape a single product page.

        Args:
            product_config: Product configuration from YAML.

        Returns:
            SavingsRate if successful, None otherwise.
        """
        product_name = product_config.get("name", "")
        url = f"{self.base_url}{product_config.get('url', '')}"

        self._log.info("scrape.product.start", product=product_name, url=url)

        # Get page content
        wait_selector = self.config.get("wait", {}).get("selector")
        html = await self.get_page_content(url, wait_selector)

        # Extract rate from HTML
        rate = self._extract_rate_from_html(html, product_config)

        # Build SavingsRate object
        return SavingsRate(
            provider=self.provider,
            product_name=TemboProduct(product_name),
            product_type=ProductType(product_config.get("product_type", "cash_isa")),
            rate=rate,
            rate_type=RateType(product_config.get("rate_type", "variable")),
            scraped_at=datetime.now(timezone.utc),
            url=url,
            term_months=product_config.get("term_months"),
        )

    def _extract_rate_from_html(
        self, html: str, product_config: dict[str, Any]
    ) -> Decimal:
        """Extract rate from HTML using configured selectors or patterns.

        Args:
            html: HTML content.
            product_config: Product configuration with selectors.

        Returns:
            Extracted rate as Decimal.

        Raises:
            RateExtractionError: If rate cannot be extracted.
        """
        soup = BeautifulSoup(html, "lxml")
        selectors = product_config.get("selectors", {})
        full_text: str | None = None  # Lazy cache

        # If a custom rate_pattern is specified, use it for extraction
        rate_pattern = product_config.get("rate_pattern")
        if rate_pattern:
            full_text = soup.get_text()
            if rate := self.extract_rate_with_pattern(full_text, rate_pattern):
                return rate

        # Try primary selector(s)
        rate_selector = selectors.get("rate", ".rate-value")
        for selector in rate_selector.split(","):
            selector = selector.strip()
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                try:
                    return self.extract_rate(text)
                except RateExtractionError:
                    continue

        # Try fallback selector if available
        fallback = selectors.get("rate_fallback")
        if fallback:
            element = soup.select_one(fallback)
            if element:
                text = element.get_text(strip=True)
                return self.extract_rate(text)

        raise RateExtractionError(
            f"Could not extract rate for {product_config.get('name')}",
            raw_text=html[:500],
        )

    def extract_rate_from_fixture(self, html: str) -> Decimal:
        """Extract rate from HTML fixture (for testing).

        Args:
            html: HTML content.

        Returns:
            Extracted rate as Decimal.
        """
        soup = BeautifulSoup(html, "lxml")

        # Try common selectors
        for selector in [".rate-value", ".aer-rate", "[data-rate]", ".product-rate"]:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                try:
                    return self.extract_rate(text)
                except RateExtractionError:
                    continue

        raise RateExtractionError("Could not extract rate from fixture")

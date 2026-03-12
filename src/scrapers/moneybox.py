"""Moneybox scraper implementation."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup

from src.exceptions.scraping import RateExtractionError, SelectorNotFoundError
from src.models.rate import SavingsRate
from src.models.types import MoneyboxProduct, ProductType, Provider, RateType
from src.scrapers.base import BaseScraper
from src.utils.browser import BrowserManager

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "providers" / "moneybox.yaml"


class MoneyboxScraper(BaseScraper):
    """Scraper for Moneybox savings products."""

    # Product-specific patterns for Moneybox (searches raw HTML due to JSON metadata)
    _PRODUCT_PATTERNS: dict[str, str] = {
        "moneybox_cash_isa": r"Cash ISA.*?(\d+\.\d+)%\s*AER",
        "moneybox_open_access_isa": r"Open Access.*?(\d+\.\d+)%",
        "moneybox_notice_90": r"90[- ]?Day.*?(\d+\.\d+)%",
        "moneybox_notice_95": r"95[- ]?Day.*?(\d+\.\d+)%",
        "moneybox_business_saver": r"Business.*?(\d+\.\d+)%",
    }

    def __init__(
        self,
        browser: BrowserManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize Moneybox scraper.

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
        """Return Moneybox provider."""
        return Provider.MONEYBOX

    @property
    def base_url(self) -> str:
        """Return Moneybox base URL."""
        return str(self.config.get("base_url", "https://www.moneyboxapp.com"))

    async def scrape(self) -> list[SavingsRate]:
        """Scrape all Moneybox savings rates.

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
            except (RateExtractionError, SelectorNotFoundError) as e:
                self._log.warning(
                    "scrape.product.failed",
                    product=product_config.get("name"),
                    error=str(e),
                )

        self._log.info("scrape.complete", provider="moneybox", rates_found=len(rates))
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
            product_name=MoneyboxProduct(product_name),
            product_type=ProductType(product_config.get("product_type", "easy_access")),
            rate=rate,
            rate_type=RateType(product_config.get("rate_type", "variable")),
            scraped_at=datetime.now(timezone.utc),
            url=url,
        )

    def _extract_rate_from_html(
        self, html: str, product_config: dict[str, Any]
    ) -> Decimal:
        """Extract rate from HTML using configured selectors or patterns.

        Moneybox embeds rates in JSON metadata within the HTML, so we search
        the raw HTML content directly rather than just visible text.

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
        product_name = product_config.get("name", "")

        # If a custom rate_pattern is specified, search raw HTML first
        # (Moneybox embeds rates in JSON metadata, not visible text)
        rate_pattern = product_config.get("rate_pattern")
        if rate_pattern and (rate := self.extract_rate_with_pattern(html, rate_pattern)):
            return rate

        # Try product-specific patterns (searches raw HTML for JSON metadata)
        if product_name in self._PRODUCT_PATTERNS and (
            rate := self.extract_rate_with_pattern(html, self._PRODUCT_PATTERNS[product_name])
        ):
            return rate

        # Try primary selector(s)
        rate_selector = selectors.get("rate", ".rate-display")
        for selector in rate_selector.split(","):
            selector = selector.strip()
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                try:
                    return self.extract_rate(text)
                except RateExtractionError:
                    continue

        # Last resort: extract all rates from raw HTML and return highest
        all_rates = self.extract_all_rates(html)
        if all_rates:
            return max(all_rates)

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
        for selector in [".rate-display", ".aer-value", ".interest-rate"]:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                try:
                    return self.extract_rate(text)
                except RateExtractionError:
                    continue

        raise RateExtractionError("Could not extract rate from fixture")

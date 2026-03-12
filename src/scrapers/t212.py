"""Trading 212 scraper implementation."""

import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup

from src.exceptions.scraping import RateExtractionError, SelectorNotFoundError
from src.models.rate import SavingsRate
from src.models.types import ProductType, Provider, RateType, T212Product
from src.scrapers.base import BaseScraper
from src.utils.browser import BrowserManager

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "providers" / "t212.yaml"


class T212Scraper(BaseScraper):
    """Scraper for Trading 212 savings products."""

    def __init__(
        self,
        browser: BrowserManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize Trading 212 scraper.

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
        try:
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f)
                return dict(data) if data else {}
        except FileNotFoundError:
            return {}

    @property
    def provider(self) -> Provider:
        """Return Trading 212 provider."""
        return Provider.T212

    @property
    def base_url(self) -> str:
        """Return Trading 212 base URL."""
        return str(self.config.get("base_url", "https://www.trading212.com"))

    async def scrape(self) -> list[SavingsRate]:
        """Scrape all Trading 212 savings rates.

        Returns:
            List of scraped savings rates.
        """
        rates: list[SavingsRate] = []
        products = self.config.get("products", [])
        html_cache: dict[str, str] = {}

        for product_config in products:
            try:
                rate = await self._scrape_product(product_config, html_cache)
                if rate:
                    rates.append(rate)
            except (RateExtractionError, SelectorNotFoundError) as e:
                self._log.warning(
                    "scrape.product.failed",
                    product=product_config.get("name"),
                    error=str(e),
                )

        self._log.info("scrape.complete", provider="t212", rates_found=len(rates))
        return rates

    async def _scrape_product(
        self, product_config: dict[str, Any], html_cache: dict[str, str]
    ) -> SavingsRate | None:
        """Scrape a single product page.

        Args:
            product_config: Product configuration from YAML.
            html_cache: Cache of URL -> HTML to avoid duplicate fetches.

        Returns:
            SavingsRate if successful, None otherwise.
        """
        product_name = product_config.get("name", "")
        url = f"{self.base_url}{product_config.get('url', '')}"

        self._log.info("scrape.product.start", product=product_name, url=url)

        # Get page content (use cache to avoid duplicate fetches)
        if url in html_cache:
            html = html_cache[url]
        else:
            wait_selector = self.config.get("wait", {}).get("selector")
            html = await self.get_page_content(url, wait_selector)
            html_cache[url] = html

        # Extract rate from HTML
        rate = self._extract_rate_from_html(html, product_config)

        # Build SavingsRate object
        return SavingsRate(
            provider=self.provider,
            product_name=T212Product(product_name),
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

        Args:
            html: HTML content.
            product_config: Product configuration with selectors.

        Returns:
            Extracted rate as Decimal.

        Raises:
            RateExtractionError: If rate cannot be extracted.
        """
        # T212 embeds rates in JSON data as decimal values (e.g., 0.038 = 3.8%)
        # Try to extract GBP rate from JSON first
        json_rate = self._extract_gbp_rate_from_json(html, product_config)
        if json_rate:
            return json_rate

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
        rate_selector = selectors.get("rate", ".interest-rate")
        for selector in rate_selector.split(","):
            selector = selector.strip()
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                try:
                    return self.extract_rate(text)
                except RateExtractionError:
                    continue

        # Last resort: try to find any rate in the page text
        if full_text is None:
            full_text = soup.get_text()
        all_rates = self.extract_all_rates(full_text)
        if all_rates:
            return max(all_rates)

        raise RateExtractionError(
            f"Could not extract rate for {product_config.get('name')}",
            raw_text=html[:500],
        )

    def _extract_gbp_rate_from_json(
        self, html: str, product_config: dict[str, Any]
    ) -> Decimal | None:
        """Extract GBP rate from embedded JSON data.

        T212 embeds interest rates in JSON format like:
        "invest":{"AVUSUK":{"GBP":0.038,...}}

        Args:
            html: HTML content containing JSON data.
            product_config: Product configuration with json_key.

        Returns:
            Rate as Decimal percentage, or None if not found.
        """
        json_key = product_config.get("json_key")
        if not json_key:
            return None

        # Pattern to find the account type JSON with GBP rate
        # e.g., "invest":{"AVUSUK":{..."GBP":0.038...}}
        pattern = rf'"{json_key}":\{{"AVUSUK":\{{[^}}]*"GBP":([0-9]+\.?[0-9]*)[^}}]*\}}'
        match = re.search(pattern, html)

        if match:
            decimal_rate = Decimal(match.group(1))
            # Convert from decimal (0.038) to percentage (3.8)
            percentage_rate = decimal_rate * 100
            self._log.debug(
                "rate.extracted.json",
                json_key=json_key,
                decimal_rate=str(decimal_rate),
                percentage_rate=str(percentage_rate),
            )
            return percentage_rate.quantize(Decimal("0.01"))

        return None

    def extract_rate_from_fixture(self, html: str) -> Decimal:
        """Extract rate from HTML fixture (for testing).

        Args:
            html: HTML content.

        Returns:
            Extracted rate as Decimal.
        """
        soup = BeautifulSoup(html, "lxml")

        # Try common selectors
        for selector in [".interest-rate", ".rate-percentage", ".savings-rate"]:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                try:
                    return self.extract_rate(text)
                except RateExtractionError:
                    continue

        raise RateExtractionError("Could not extract rate from fixture")

"""Unit tests for base scraper."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exceptions.scraping import (
    ParseError,
    RateExtractionError,
    ScrapingError,
    SelectorNotFoundError,
    TimeoutError,
)
from src.models.rate import SavingsRate
from src.models.types import Provider
from src.scrapers.base import RATE_PATTERNS, BaseScraper
from src.utils.browser import BrowserManager


class ConcreteScraper(BaseScraper):
    """Concrete implementation for testing."""

    @property
    def provider(self) -> Provider:
        return Provider.TEMBO

    @property
    def base_url(self) -> str:
        return "https://example.com"

    async def scrape(self) -> list[SavingsRate]:
        return []


@pytest.fixture
def mock_browser():
    """Create mock browser manager."""
    browser = MagicMock(spec=BrowserManager)
    return browser


@pytest.fixture
def scraper(mock_browser):
    """Create concrete scraper for testing."""
    return ConcreteScraper(browser=mock_browser)


@pytest.mark.unit
class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_scraping_error_is_exception(self):
        """ScrapingError inherits from Exception."""
        error = ScrapingError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_scraping_error_with_url(self):
        """ScrapingError stores URL."""
        error = ScrapingError("test error", url="https://example.com")
        assert error.url == "https://example.com"

    def test_timeout_error_inherits_from_scraping_error(self):
        """TimeoutError inherits from ScrapingError."""
        error = TimeoutError("timeout", timeout_ms=5000)
        assert isinstance(error, ScrapingError)
        assert error.timeout_ms == 5000

    def test_selector_not_found_error(self):
        """SelectorNotFoundError stores selector."""
        error = SelectorNotFoundError(
            "not found", url="https://example.com", selector=".rate"
        )
        assert isinstance(error, ScrapingError)
        assert error.selector == ".rate"
        assert error.url == "https://example.com"

    def test_rate_extraction_error(self):
        """RateExtractionError stores raw text."""
        error = RateExtractionError(
            "extraction failed", url="https://example.com", raw_text="no rate here"
        )
        assert isinstance(error, ScrapingError)
        assert error.raw_text == "no rate here"

    def test_parse_error(self):
        """ParseError stores content type."""
        error = ParseError(
            "parse failed", url="https://example.com", content_type="application/json"
        )
        assert isinstance(error, ScrapingError)
        assert error.content_type == "application/json"


@pytest.mark.unit
class TestRatePatterns:
    """Tests for rate extraction patterns."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("4.55%", "4.55"),
            ("4.55 %", "4.55"),
            ("Interest rate: 4.55%", "4.55"),
            ("Earn 5% on your savings", "5"),
            ("0.5% AER", "0.5"),
            ("12.25%", "12.25"),
        ],
    )
    def test_percent_pattern(self, text, expected):
        """Percent pattern extracts rates."""
        pattern = RATE_PATTERNS[0]  # (\d+\.?\d*)\s*%
        match = pattern.search(text)
        assert match is not None
        assert match.group(1) == expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("4.55 per cent", "4.55"),
            ("4.55 Per Cent", "4.55"),
            ("earn 5 per cent interest", "5"),
        ],
    )
    def test_per_cent_pattern(self, text, expected):
        """Per cent pattern extracts rates."""
        pattern = RATE_PATTERNS[1]
        match = pattern.search(text)
        assert match is not None
        assert match.group(1) == expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("AER: 4.55", "4.55"),
            ("AER 4.55", "4.55"),
            ("aer:3.25", "3.25"),
        ],
    )
    def test_aer_prefix_pattern(self, text, expected):
        """AER prefix pattern extracts rates."""
        pattern = RATE_PATTERNS[3]
        match = pattern.search(text)
        assert match is not None
        assert match.group(1) == expected


@pytest.mark.unit
class TestExtractRate:
    """Tests for rate extraction."""

    def test_extract_simple_percentage(self, scraper):
        """Extract rate from simple percentage."""
        rate = scraper.extract_rate("Interest rate: 4.55%")
        assert rate == Decimal("4.55")

    def test_extract_per_cent(self, scraper):
        """Extract rate from 'per cent' format."""
        rate = scraper.extract_rate("Earn 4.55 per cent on your savings")
        assert rate == Decimal("4.55")

    def test_extract_aer_format(self, scraper):
        """Extract rate from AER format."""
        rate = scraper.extract_rate("Current AER: 4.55")
        assert rate == Decimal("4.55")

    def test_extract_integer_rate(self, scraper):
        """Extract integer rate."""
        rate = scraper.extract_rate("Earn 5% interest")
        assert rate == Decimal("5")

    def test_extract_rate_raises_on_no_match(self, scraper):
        """RateExtractionError raised when no rate found."""
        with pytest.raises(RateExtractionError) as exc_info:
            scraper.extract_rate("No rate mentioned here")
        assert "Could not extract rate" in str(exc_info.value)

    def test_extract_rate_includes_raw_text(self, scraper):
        """RateExtractionError includes raw text."""
        with pytest.raises(RateExtractionError) as exc_info:
            scraper.extract_rate("No rate here", url="https://example.com")
        assert exc_info.value.raw_text is not None
        assert exc_info.value.url == "https://example.com"


@pytest.mark.unit
class TestValidateRate:
    """Tests for rate validation."""

    def test_valid_rate_in_range(self, scraper):
        """Rates in valid range are accepted."""
        assert scraper.validate_rate(Decimal("4.55")) is True
        assert scraper.validate_rate(Decimal("0")) is True
        assert scraper.validate_rate(Decimal("15")) is True
        assert scraper.validate_rate(Decimal("0.01")) is True

    def test_negative_rate_rejected(self, scraper):
        """Negative rates are rejected."""
        assert scraper.validate_rate(Decimal("-0.5")) is False

    def test_rate_over_15_rejected(self, scraper):
        """Rates over 15% are rejected."""
        assert scraper.validate_rate(Decimal("15.01")) is False
        assert scraper.validate_rate(Decimal("20")) is False
        assert scraper.validate_rate(Decimal("100")) is False


@pytest.mark.unit
class TestExtractAllRates:
    """Tests for extracting multiple rates."""

    def test_extract_multiple_rates(self, scraper):
        """Extract multiple rates from text."""
        text = "Easy access: 3.5%, Fixed: 4.75%, Notice: 4.25%"
        rates = scraper.extract_all_rates(text)
        assert len(rates) == 3
        assert Decimal("3.5") in rates
        assert Decimal("4.75") in rates
        assert Decimal("4.25") in rates

    def test_extract_no_duplicates(self, scraper):
        """Duplicate rates are removed."""
        text = "Get 4.5% interest! Yes, 4.5% AER!"
        rates = scraper.extract_all_rates(text)
        assert len(rates) == 1
        assert rates[0] == Decimal("4.5")

    def test_extract_empty_for_no_rates(self, scraper):
        """Empty list returned when no rates found."""
        rates = scraper.extract_all_rates("No rates here")
        assert rates == []

    def test_invalid_rates_filtered(self, scraper):
        """Invalid rates are filtered out."""
        text = "Special rate: 50% (not real), Normal rate: 4.5%"
        rates = scraper.extract_all_rates(text)
        assert len(rates) == 1
        assert Decimal("4.5") in rates


@pytest.mark.unit
class TestScraperInit:
    """Tests for scraper initialization."""

    def test_scraper_has_provider(self, scraper):
        """Scraper has provider property."""
        assert scraper.provider == Provider.TEMBO

    def test_scraper_has_base_url(self, scraper):
        """Scraper has base_url property."""
        assert scraper.base_url == "https://example.com"

    def test_scraper_with_config(self, mock_browser):
        """Scraper accepts configuration."""
        config = {"selector": ".rate", "timeout": 5000}
        scraper = ConcreteScraper(browser=mock_browser, config=config)
        assert scraper.config == config

    def test_scraper_default_config(self, mock_browser):
        """Scraper has empty config by default."""
        scraper = ConcreteScraper(browser=mock_browser)
        assert scraper.config == {}


@pytest.mark.unit
class TestGetElementText:
    """Tests for element text extraction."""

    async def test_get_element_text_success(self, scraper):
        """Successfully get element text."""
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_element.text_content = AsyncMock(return_value="  4.55%  ")
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        text = await scraper.get_element_text(mock_page, ".rate")
        assert text == "4.55%"

    async def test_get_element_text_not_found(self, scraper):
        """Raise error when element not found."""
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        with pytest.raises(SelectorNotFoundError) as exc_info:
            await scraper.get_element_text(
                mock_page, ".missing", url="https://example.com"
            )
        assert exc_info.value.selector == ".missing"
        assert exc_info.value.url == "https://example.com"

    async def test_get_element_text_empty(self, scraper):
        """Handle empty element text."""
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_element.text_content = AsyncMock(return_value=None)
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        text = await scraper.get_element_text(mock_page, ".empty")
        assert text == ""

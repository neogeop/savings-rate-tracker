"""Unit tests for provider scrapers."""

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.models.types import Provider
from src.scrapers.chip import ChipScraper
from src.scrapers.moneybox import MoneyboxScraper
from src.scrapers.t212 import T212Scraper
from src.scrapers.tembo import TemboScraper
from src.utils.browser import BrowserManager

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def mock_browser():
    """Create mock browser manager."""
    return MagicMock(spec=BrowserManager)


@pytest.fixture
def tembo_cash_isa_html():
    """Load Tembo Cash ISA fixture."""
    return (FIXTURES_DIR / "tembo_cash_isa.html").read_text()


@pytest.fixture
def chip_easy_access_html():
    """Load Chip Easy Access fixture."""
    return (FIXTURES_DIR / "chip_easy_access.html").read_text()


@pytest.fixture
def moneybox_notice_90_html():
    """Load Moneybox 90 Day Notice fixture."""
    return (FIXTURES_DIR / "moneybox_notice_90.html").read_text()


@pytest.fixture
def t212_interest_on_cash_html():
    """Load T212 Interest on Cash fixture."""
    return (FIXTURES_DIR / "t212_interest_on_cash.html").read_text()


@pytest.mark.unit
class TestTemboScraper:
    """Tests for Tembo scraper."""

    def test_provider(self, mock_browser):
        """Scraper returns correct provider."""
        scraper = TemboScraper(browser=mock_browser, config={})
        assert scraper.provider == Provider.TEMBO

    def test_base_url_default(self, mock_browser):
        """Scraper uses default base URL."""
        scraper = TemboScraper(browser=mock_browser, config={})
        assert "tembomoney.com" in scraper.base_url

    def test_base_url_from_config(self, mock_browser):
        """Scraper uses base URL from config."""
        config = {"base_url": "https://custom.tembo.com"}
        scraper = TemboScraper(browser=mock_browser, config=config)
        assert scraper.base_url == "https://custom.tembo.com"

    def test_extract_rate_from_fixture(self, mock_browser, tembo_cash_isa_html):
        """Extract rate from HTML fixture."""
        scraper = TemboScraper(browser=mock_browser, config={})
        rate = scraper.extract_rate_from_fixture(tembo_cash_isa_html)
        assert rate == Decimal("4.55")

    def test_extract_rate_with_selectors(self, mock_browser, tembo_cash_isa_html):
        """Extract rate using configured selectors."""
        config = {
            "products": [
                {
                    "name": "tembo_cash_isa",
                    "selectors": {"rate": ".rate-value"},
                }
            ]
        }
        scraper = TemboScraper(browser=mock_browser, config=config)
        rate = scraper._extract_rate_from_html(
            tembo_cash_isa_html, config["products"][0]
        )
        assert rate == Decimal("4.55")


@pytest.mark.unit
class TestChipScraper:
    """Tests for Chip scraper."""

    def test_provider(self, mock_browser):
        """Scraper returns correct provider."""
        scraper = ChipScraper(browser=mock_browser, config={})
        assert scraper.provider == Provider.CHIP

    def test_base_url_default(self, mock_browser):
        """Scraper uses default base URL."""
        scraper = ChipScraper(browser=mock_browser, config={})
        assert "getchip.uk" in scraper.base_url

    def test_extract_rate_from_fixture(self, mock_browser, chip_easy_access_html):
        """Extract rate from HTML fixture."""
        scraper = ChipScraper(browser=mock_browser, config={})
        rate = scraper.extract_rate_from_fixture(chip_easy_access_html)
        assert rate == Decimal("3.75")

    def test_extract_rate_with_selectors(self, mock_browser, chip_easy_access_html):
        """Extract rate using configured selectors."""
        config = {
            "products": [
                {
                    "name": "chip_easy_access",
                    "selectors": {"rate": ".interest-rate"},
                }
            ]
        }
        scraper = ChipScraper(browser=mock_browser, config=config)
        rate = scraper._extract_rate_from_html(
            chip_easy_access_html, config["products"][0]
        )
        assert rate == Decimal("3.75")


@pytest.mark.unit
class TestMoneyboxScraper:
    """Tests for Moneybox scraper."""

    def test_provider(self, mock_browser):
        """Scraper returns correct provider."""
        scraper = MoneyboxScraper(browser=mock_browser, config={})
        assert scraper.provider == Provider.MONEYBOX

    def test_base_url_default(self, mock_browser):
        """Scraper uses default base URL."""
        scraper = MoneyboxScraper(browser=mock_browser, config={})
        assert "moneyboxapp.com" in scraper.base_url

    def test_extract_rate_from_fixture(self, mock_browser, moneybox_notice_90_html):
        """Extract rate from HTML fixture."""
        scraper = MoneyboxScraper(browser=mock_browser, config={})
        rate = scraper.extract_rate_from_fixture(moneybox_notice_90_html)
        assert rate == Decimal("4.25")

    def test_extract_rate_with_selectors(self, mock_browser, moneybox_notice_90_html):
        """Extract rate using configured selectors."""
        config = {
            "products": [
                {
                    "name": "moneybox_notice_90",
                    "selectors": {"rate": ".rate-display"},
                }
            ]
        }
        scraper = MoneyboxScraper(browser=mock_browser, config=config)
        rate = scraper._extract_rate_from_html(
            moneybox_notice_90_html, config["products"][0]
        )
        assert rate == Decimal("4.25")


@pytest.mark.unit
class TestT212Scraper:
    """Tests for Trading 212 scraper."""

    def test_provider(self, mock_browser):
        """Scraper returns correct provider."""
        scraper = T212Scraper(browser=mock_browser, config={})
        assert scraper.provider == Provider.T212

    def test_base_url_default(self, mock_browser):
        """Scraper uses default base URL."""
        scraper = T212Scraper(browser=mock_browser, config={})
        assert "trading212.com" in scraper.base_url

    def test_base_url_from_config(self, mock_browser):
        """Scraper uses base URL from config."""
        config = {"base_url": "https://custom.trading212.com"}
        scraper = T212Scraper(browser=mock_browser, config=config)
        assert scraper.base_url == "https://custom.trading212.com"

    def test_extract_rate_from_fixture(self, mock_browser, t212_interest_on_cash_html):
        """Extract rate from HTML fixture."""
        scraper = T212Scraper(browser=mock_browser, config={})
        rate = scraper.extract_rate_from_fixture(t212_interest_on_cash_html)
        assert rate == Decimal("5.10")

    def test_extract_rate_with_selectors(self, mock_browser, t212_interest_on_cash_html):
        """Extract rate using configured selectors."""
        config = {
            "products": [
                {
                    "name": "t212_interest_on_cash",
                    "selectors": {"rate": ".interest-rate"},
                }
            ]
        }
        scraper = T212Scraper(browser=mock_browser, config=config)
        rate = scraper._extract_rate_from_html(
            t212_interest_on_cash_html, config["products"][0]
        )
        assert rate == Decimal("5.10")


@pytest.mark.unit
class TestScraperConfigLoading:
    """Tests for config file loading."""

    def test_tembo_loads_yaml_config(self, mock_browser):
        """Tembo scraper loads config from YAML."""
        scraper = TemboScraper(browser=mock_browser)
        # Should have loaded products from YAML
        assert "products" in scraper.config
        assert len(scraper.config["products"]) > 0

    def test_chip_loads_yaml_config(self, mock_browser):
        """Chip scraper loads config from YAML."""
        scraper = ChipScraper(browser=mock_browser)
        assert "products" in scraper.config
        assert len(scraper.config["products"]) > 0

    def test_moneybox_loads_yaml_config(self, mock_browser):
        """Moneybox scraper loads config from YAML."""
        scraper = MoneyboxScraper(browser=mock_browser)
        assert "products" in scraper.config
        assert len(scraper.config["products"]) > 0

    def test_t212_loads_yaml_config(self, mock_browser):
        """T212 scraper loads config from YAML."""
        scraper = T212Scraper(browser=mock_browser)
        assert "products" in scraper.config
        assert len(scraper.config["products"]) > 0


@pytest.mark.unit
class TestRateExtractionEdgeCases:
    """Tests for edge cases in rate extraction."""

    def test_extract_rate_with_aer_suffix(self, mock_browser):
        """Extract rate with AER suffix."""
        html = '<div class="interest-rate">3.75% AER</div>'
        scraper = ChipScraper(browser=mock_browser, config={})
        rate = scraper.extract_rate_from_fixture(html)
        assert rate == Decimal("3.75")

    def test_extract_rate_with_whitespace(self, mock_browser):
        """Extract rate with extra whitespace."""
        html = '<div class="rate-value">  4.55 %  </div>'
        scraper = TemboScraper(browser=mock_browser, config={})
        rate = scraper.extract_rate_from_fixture(html)
        assert rate == Decimal("4.55")

    def test_extract_rate_integer(self, mock_browser):
        """Extract integer rate."""
        html = '<div class="rate-display">5%</div>'
        scraper = MoneyboxScraper(browser=mock_browser, config={})
        rate = scraper.extract_rate_from_fixture(html)
        assert rate == Decimal("5")

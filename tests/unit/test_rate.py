"""Unit tests for SavingsRate model."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.rate import SavingsRate
from src.models.types import (
    ChipProduct,
    ProductType,
    Provider,
    RateType,
    TemboProduct,
)


@pytest.fixture
def valid_rate_data() -> dict:
    """Valid rate data for testing."""
    return {
        "provider": Provider.TEMBO,
        "product_name": TemboProduct.CASH_ISA,
        "product_type": ProductType.CASH_ISA,
        "rate": Decimal("4.55"),
        "rate_type": RateType.VARIABLE,
        "scraped_at": datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc),
    }


@pytest.mark.unit
class TestSavingsRateCreation:
    """Tests for SavingsRate creation."""

    def test_create_valid_rate(self, valid_rate_data):
        """Create a valid SavingsRate."""
        rate = SavingsRate(**valid_rate_data)
        assert rate.provider == Provider.TEMBO
        assert rate.product_name == TemboProduct.CASH_ISA
        assert rate.rate == Decimal("4.55")

    def test_create_with_optional_fields(self, valid_rate_data):
        """Create rate with all optional fields."""
        rate = SavingsRate(
            **valid_rate_data,
            url="https://example.com/isa",
            term_months=12,
            min_deposit=Decimal("1"),
            max_deposit=Decimal("20000"),
            notes="Introductory rate",
        )
        assert rate.url == "https://example.com/isa"
        assert rate.term_months == 12
        assert rate.min_deposit == Decimal("1")
        assert rate.max_deposit == Decimal("20000")

    def test_create_from_string_values(self):
        """Create rate from string enum values."""
        rate = SavingsRate(
            provider="tembo",
            product_name="tembo_cash_isa",
            product_type="cash_isa",
            rate="4.55",
            rate_type="variable",
            scraped_at=datetime.now(timezone.utc),
        )
        assert rate.provider == Provider.TEMBO
        assert rate.rate == Decimal("4.55")


@pytest.mark.unit
class TestRateValidation:
    """Tests for rate validation."""

    def test_negative_rate_rejected(self, valid_rate_data):
        """Negative rates should be rejected."""
        valid_rate_data["rate"] = Decimal("-0.5")
        with pytest.raises(ValidationError) as exc_info:
            SavingsRate(**valid_rate_data)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_rate_over_15_rejected(self, valid_rate_data):
        """Rates over 15% should be rejected."""
        valid_rate_data["rate"] = Decimal("15.5")
        with pytest.raises(ValidationError) as exc_info:
            SavingsRate(**valid_rate_data)
        assert "less than or equal to 15" in str(exc_info.value)

    def test_rate_at_boundaries(self, valid_rate_data):
        """Rates at 0% and 15% should be accepted."""
        valid_rate_data["rate"] = Decimal("0")
        rate_zero = SavingsRate(**valid_rate_data)
        assert rate_zero.rate == Decimal("0")

        valid_rate_data["rate"] = Decimal("15")
        rate_max = SavingsRate(**valid_rate_data)
        assert rate_max.rate == Decimal("15")

    def test_rate_with_percent_sign(self, valid_rate_data):
        """Rate string with % sign should be parsed."""
        valid_rate_data["rate"] = "4.55%"
        rate = SavingsRate(**valid_rate_data)
        assert rate.rate == Decimal("4.55")

    def test_rate_precision_rounded(self, valid_rate_data):
        """Rates should be rounded to 2 decimal places."""
        valid_rate_data["rate"] = Decimal("4.555")
        rate = SavingsRate(**valid_rate_data)
        assert rate.rate == Decimal("4.56")  # Rounded up


@pytest.mark.unit
class TestDepositValidation:
    """Tests for deposit range validation."""

    def test_min_greater_than_max_rejected(self, valid_rate_data):
        """min_deposit > max_deposit should be rejected."""
        valid_rate_data["min_deposit"] = Decimal("10000")
        valid_rate_data["max_deposit"] = Decimal("5000")
        with pytest.raises(ValidationError) as exc_info:
            SavingsRate(**valid_rate_data)
        assert "min_deposit cannot be greater than max_deposit" in str(exc_info.value)

    def test_negative_deposit_rejected(self, valid_rate_data):
        """Negative deposits should be rejected."""
        valid_rate_data["min_deposit"] = Decimal("-100")
        with pytest.raises(ValidationError) as exc_info:
            SavingsRate(**valid_rate_data)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_only_min_deposit_allowed(self, valid_rate_data):
        """Only min_deposit without max_deposit is allowed."""
        valid_rate_data["min_deposit"] = Decimal("1")
        rate = SavingsRate(**valid_rate_data)
        assert rate.min_deposit == Decimal("1")
        assert rate.max_deposit is None


@pytest.mark.unit
class TestTermValidation:
    """Tests for term_months validation."""

    def test_term_months_boundaries(self, valid_rate_data):
        """Term months at valid boundaries."""
        valid_rate_data["term_months"] = 1
        rate_min = SavingsRate(**valid_rate_data)
        assert rate_min.term_months == 1

        valid_rate_data["term_months"] = 120
        rate_max = SavingsRate(**valid_rate_data)
        assert rate_max.term_months == 120

    def test_term_months_zero_rejected(self, valid_rate_data):
        """Term months of 0 should be rejected."""
        valid_rate_data["term_months"] = 0
        with pytest.raises(ValidationError) as exc_info:
            SavingsRate(**valid_rate_data)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_term_months_over_max_rejected(self, valid_rate_data):
        """Term months over 120 should be rejected."""
        valid_rate_data["term_months"] = 121
        with pytest.raises(ValidationError) as exc_info:
            SavingsRate(**valid_rate_data)
        assert "less than or equal to 120" in str(exc_info.value)


@pytest.mark.unit
class TestSerialization:
    """Tests for JSON serialization/deserialization."""

    def test_to_dict(self, valid_rate_data):
        """Convert to dictionary."""
        rate = SavingsRate(**valid_rate_data)
        data = rate.to_dict()

        assert data["provider"] == "tembo"
        assert data["product_name"] == "tembo_cash_isa"
        assert data["rate"] == "4.55"
        assert data["rate_type"] == "variable"
        assert "2026-03-12T10:00:00" in data["scraped_at"]

    def test_from_dict(self, valid_rate_data):
        """Create from dictionary."""
        rate = SavingsRate(**valid_rate_data)
        data = rate.to_dict()

        restored = SavingsRate.from_dict(data)
        assert restored.provider == rate.provider
        assert restored.product_name == rate.product_name
        assert restored.rate == rate.rate

    def test_json_roundtrip(self, valid_rate_data):
        """JSON serialization roundtrip."""
        rate = SavingsRate(**valid_rate_data)
        json_str = rate.model_dump_json()

        restored = SavingsRate.model_validate_json(json_str)
        assert restored.rate == rate.rate
        assert restored.provider == rate.provider

    def test_to_dict_with_optional_fields(self, valid_rate_data):
        """to_dict includes optional fields when set."""
        valid_rate_data["min_deposit"] = Decimal("100")
        valid_rate_data["max_deposit"] = Decimal("20000")
        rate = SavingsRate(**valid_rate_data)
        data = rate.to_dict()

        assert data["min_deposit"] == "100"
        assert data["max_deposit"] == "20000"


@pytest.mark.unit
class TestDecimalPrecision:
    """Tests for decimal precision handling."""

    def test_float_to_decimal_conversion(self, valid_rate_data):
        """Float values should convert to Decimal correctly."""
        valid_rate_data["rate"] = 4.55
        rate = SavingsRate(**valid_rate_data)
        assert rate.rate == Decimal("4.55")

    def test_int_to_decimal_conversion(self, valid_rate_data):
        """Integer values should convert to Decimal correctly."""
        valid_rate_data["rate"] = 5
        rate = SavingsRate(**valid_rate_data)
        assert rate.rate == Decimal("5.00")

    def test_string_to_decimal_conversion(self, valid_rate_data):
        """String values should convert to Decimal correctly."""
        valid_rate_data["rate"] = "4.55"
        rate = SavingsRate(**valid_rate_data)
        assert rate.rate == Decimal("4.55")


@pytest.mark.unit
class TestExtraFieldsRejected:
    """Tests for extra fields validation."""

    def test_extra_fields_rejected(self, valid_rate_data):
        """Extra fields should be rejected."""
        valid_rate_data["unknown_field"] = "value"
        with pytest.raises(ValidationError) as exc_info:
            SavingsRate(**valid_rate_data)
        assert "Extra inputs are not permitted" in str(exc_info.value)


@pytest.mark.unit
class TestMultipleProviders:
    """Tests for different providers."""

    def test_chip_product(self):
        """Create rate for Chip product."""
        rate = SavingsRate(
            provider=Provider.CHIP,
            product_name=ChipProduct.EASY_ACCESS,
            product_type=ProductType.EASY_ACCESS,
            rate=Decimal("3.75"),
            rate_type=RateType.VARIABLE,
            scraped_at=datetime.now(timezone.utc),
        )
        assert rate.provider == Provider.CHIP
        assert rate.product_name == ChipProduct.EASY_ACCESS

"""Unit tests for type definitions."""

import pytest

from src.models.types import (
    ChipProduct,
    MoneyboxProduct,
    ProductType,
    Provider,
    RateType,
    TemboProduct,
)


@pytest.mark.unit
class TestProvider:
    """Tests for Provider enum."""

    def test_provider_values(self):
        """Verify provider enum values."""
        assert Provider.TEMBO.value == "tembo"
        assert Provider.CHIP.value == "chip"
        assert Provider.MONEYBOX.value == "moneybox"

    def test_provider_membership(self):
        """Verify all expected providers exist."""
        providers = {p.value for p in Provider}
        assert providers == {"tembo", "chip", "moneybox"}

    def test_provider_string_conversion(self):
        """Provider value should convert to string correctly."""
        assert Provider.TEMBO.value == "tembo"
        assert f"{Provider.CHIP.value}" == "chip"
        # Enums compare equal to their string values
        assert Provider.TEMBO == "tembo"

    def test_provider_from_value(self):
        """Provider can be created from string value."""
        assert Provider("tembo") == Provider.TEMBO
        assert Provider("chip") == Provider.CHIP


@pytest.mark.unit
class TestTemboProduct:
    """Tests for TemboProduct enum."""

    def test_tembo_product_values(self):
        """Verify Tembo product enum values."""
        assert TemboProduct.CASH_ISA.value == "tembo_cash_isa"
        assert TemboProduct.FIXED_RATE_ISA.value == "tembo_fixed_rate_isa"
        assert TemboProduct.CASH_LIFETIME_ISA.value == "tembo_cash_lifetime_isa"
        assert TemboProduct.SS_LIFETIME_ISA.value == "tembo_ss_lifetime_isa"
        assert TemboProduct.EASY_ACCESS_ISA.value == "tembo_easy_access_isa"
        assert TemboProduct.HOMESAVER.value == "tembo_homesaver"

    def test_tembo_product_count(self):
        """Verify expected number of Tembo products."""
        assert len(TemboProduct) == 6

    def test_tembo_product_string_conversion(self):
        """Tembo products should convert to strings correctly."""
        assert TemboProduct.CASH_ISA.value == "tembo_cash_isa"
        # Enums compare equal to their string values
        assert TemboProduct.CASH_ISA == "tembo_cash_isa"


@pytest.mark.unit
class TestChipProduct:
    """Tests for ChipProduct enum."""

    def test_chip_product_values(self):
        """Verify Chip product enum values."""
        assert ChipProduct.CASH_ISA.value == "chip_cash_isa"
        assert ChipProduct.EASY_ACCESS.value == "chip_easy_access"
        assert ChipProduct.INSTANT_ACCESS.value == "chip_instant_access"
        assert ChipProduct.PRIZE_SAVINGS.value == "chip_prize_savings"

    def test_chip_product_count(self):
        """Verify expected number of Chip products."""
        assert len(ChipProduct) == 4


@pytest.mark.unit
class TestMoneyboxProduct:
    """Tests for MoneyboxProduct enum."""

    def test_moneybox_product_values(self):
        """Verify Moneybox product enum values."""
        assert MoneyboxProduct.CASH_ISA.value == "moneybox_cash_isa"
        assert MoneyboxProduct.OPEN_ACCESS_ISA.value == "moneybox_open_access_isa"
        assert MoneyboxProduct.NOTICE_90_DAY.value == "moneybox_notice_90"
        assert MoneyboxProduct.NOTICE_95_DAY.value == "moneybox_notice_95"
        assert MoneyboxProduct.BUSINESS_SAVER.value == "moneybox_business_saver"

    def test_moneybox_product_count(self):
        """Verify expected number of Moneybox products."""
        assert len(MoneyboxProduct) == 5


@pytest.mark.unit
class TestProductType:
    """Tests for ProductType enum."""

    def test_product_type_values(self):
        """Verify product type enum values."""
        assert ProductType.CASH_ISA.value == "cash_isa"
        assert ProductType.LIFETIME_ISA.value == "lifetime_isa"
        assert ProductType.EASY_ACCESS.value == "easy_access"
        assert ProductType.NOTICE_ACCOUNT.value == "notice_account"
        assert ProductType.FIXED_RATE.value == "fixed_rate"
        assert ProductType.PRIZE_SAVINGS.value == "prize_savings"
        assert ProductType.BUSINESS_SAVER.value == "business_saver"

    def test_product_type_count(self):
        """Verify expected number of product types."""
        assert len(ProductType) == 7


@pytest.mark.unit
class TestRateType:
    """Tests for RateType enum."""

    def test_rate_type_values(self):
        """Verify rate type enum values."""
        assert RateType.FIXED.value == "fixed"
        assert RateType.VARIABLE.value == "variable"
        assert RateType.TRACKER.value == "tracker"

    def test_rate_type_count(self):
        """Verify expected number of rate types."""
        assert len(RateType) == 3

    def test_rate_type_from_value(self):
        """RateType can be created from string value."""
        assert RateType("fixed") == RateType.FIXED
        assert RateType("variable") == RateType.VARIABLE


@pytest.mark.unit
class TestProductNameUnion:
    """Tests for ProductName union type."""

    def test_all_products_are_str_enums(self):
        """All product enums should be string enums."""
        for product in TemboProduct:
            assert isinstance(product.value, str)
        for product in ChipProduct:
            assert isinstance(product.value, str)
        for product in MoneyboxProduct:
            assert isinstance(product.value, str)

    def test_product_names_are_unique(self):
        """All product names across providers should be unique."""
        all_names = (
            [p.value for p in TemboProduct]
            + [p.value for p in ChipProduct]
            + [p.value for p in MoneyboxProduct]
        )
        assert len(all_names) == len(set(all_names))

    def test_product_names_have_provider_prefix(self):
        """All product names should be prefixed with provider name."""
        for product in TemboProduct:
            assert product.value.startswith("tembo_")
        for product in ChipProduct:
            assert product.value.startswith("chip_")
        for product in MoneyboxProduct:
            assert product.value.startswith("moneybox_")

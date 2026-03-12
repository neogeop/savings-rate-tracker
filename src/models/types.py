"""Strict type definitions for savings rate scraping."""

from enum import Enum


class Provider(str, Enum):
    """UK fintech savings providers."""

    TEMBO = "tembo"
    CHIP = "chip"
    MONEYBOX = "moneybox"


class TemboProduct(str, Enum):
    """Tembo savings products."""

    CASH_ISA = "tembo_cash_isa"
    FIXED_RATE_ISA = "tembo_fixed_rate_isa"
    CASH_LIFETIME_ISA = "tembo_cash_lifetime_isa"
    SS_LIFETIME_ISA = "tembo_ss_lifetime_isa"
    EASY_ACCESS_ISA = "tembo_easy_access_isa"
    HOMESAVER = "tembo_homesaver"


class ChipProduct(str, Enum):
    """Chip savings products."""

    CASH_ISA = "chip_cash_isa"
    EASY_ACCESS = "chip_easy_access"
    INSTANT_ACCESS = "chip_instant_access"
    PRIZE_SAVINGS = "chip_prize_savings"


class MoneyboxProduct(str, Enum):
    """Moneybox savings products."""

    CASH_ISA = "moneybox_cash_isa"
    OPEN_ACCESS_ISA = "moneybox_open_access_isa"
    NOTICE_90_DAY = "moneybox_notice_90"
    NOTICE_95_DAY = "moneybox_notice_95"
    BUSINESS_SAVER = "moneybox_business_saver"


# Union type for all products
ProductName = TemboProduct | ChipProduct | MoneyboxProduct


class ProductType(str, Enum):
    """Categories of savings products."""

    CASH_ISA = "cash_isa"
    LIFETIME_ISA = "lifetime_isa"
    EASY_ACCESS = "easy_access"
    NOTICE_ACCOUNT = "notice_account"
    FIXED_RATE = "fixed_rate"
    PRIZE_SAVINGS = "prize_savings"
    BUSINESS_SAVER = "business_saver"


class RateType(str, Enum):
    """Interest rate types."""

    FIXED = "fixed"
    VARIABLE = "variable"
    TRACKER = "tracker"

"""Strict type definitions for savings rate scraping."""

from enum import Enum


class Provider(str, Enum):
    """UK fintech savings providers."""

    TEMBO = "tembo"
    CHIP = "chip"
    MONEYBOX = "moneybox"
    T212 = "t212"


class TemboProduct(str, Enum):
    """Tembo savings products."""

    CASH_ISA_EASY_ACCESS = "tembo_cash_isa_easy_access"
    CASH_ISA_FIXED_RATE = "tembo_cash_isa_fixed_rate"
    LIFETIME_ISA_CASH = "tembo_lifetime_isa_cash"
    LIFETIME_ISA_STOCKS = "tembo_lifetime_isa_stocks"
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
    OPEN_ACCESS_CASH_ISA = "moneybox_open_access_cash_isa"


class T212Product(str, Enum):
    """Trading 212 savings products."""

    CASH_ISA = "t212_cash_isa"
    INTEREST_ON_CASH = "t212_interest_on_cash"


# Union type for all products
ProductName = TemboProduct | ChipProduct | MoneyboxProduct | T212Product


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

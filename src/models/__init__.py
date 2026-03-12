"""Data models for savings rates."""

from src.models.rate import SavingsRate
from src.models.types import (
    ChipProduct,
    MoneyboxProduct,
    ProductName,
    ProductType,
    Provider,
    RateType,
    T212Product,
    TemboProduct,
)

__all__ = [
    "Provider",
    "TemboProduct",
    "ChipProduct",
    "MoneyboxProduct",
    "T212Product",
    "ProductName",
    "ProductType",
    "RateType",
    "SavingsRate",
]

"""SavingsRate pydantic model with validation."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.types import ProductName, ProductType, Provider, RateType


class SavingsRate(BaseModel):
    """A savings rate scraped from a provider."""

    provider: Provider
    product_name: ProductName
    product_type: ProductType
    rate: Decimal = Field(ge=Decimal("0"), le=Decimal("15"))
    rate_type: RateType
    scraped_at: datetime
    url: str | None = None
    term_months: int | None = Field(default=None, ge=1, le=120)
    min_deposit: Decimal | None = Field(default=None, ge=Decimal("0"))
    max_deposit: Decimal | None = Field(default=None, ge=Decimal("0"))
    notes: str | None = None

    model_config = {
        "extra": "forbid",
        "ser_json_inf_nan": "constants",
    }

    @field_validator("rate", mode="before")
    @classmethod
    def parse_rate(cls, v: Any) -> Decimal:
        """Parse rate from string or number to Decimal."""
        if isinstance(v, Decimal):
            return v
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            # Remove % sign if present
            cleaned = v.strip().rstrip("%").strip()
            return Decimal(cleaned)
        raise ValueError(f"Cannot parse rate from {type(v)}: {v}")

    @field_validator("rate")
    @classmethod
    def validate_rate_precision(cls, v: Decimal) -> Decimal:
        """Ensure rate has at most 2 decimal places."""
        # Round to 2 decimal places
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_deposit_range(self) -> "SavingsRate":
        """Ensure min_deposit <= max_deposit if both are set."""
        if (
            self.min_deposit is not None
            and self.max_deposit is not None
            and self.min_deposit > self.max_deposit
        ):
            raise ValueError("min_deposit cannot be greater than max_deposit")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with serializable values."""
        data = self.model_dump()
        data["rate"] = str(self.rate)
        data["scraped_at"] = self.scraped_at.isoformat()
        data["provider"] = self.provider.value
        data["product_name"] = self.product_name.value
        data["product_type"] = self.product_type.value
        data["rate_type"] = self.rate_type.value
        if self.min_deposit is not None:
            data["min_deposit"] = str(self.min_deposit)
        if self.max_deposit is not None:
            data["max_deposit"] = str(self.max_deposit)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SavingsRate":
        """Create from dictionary, parsing string values."""
        # Parse datetime if string
        if isinstance(data.get("scraped_at"), str):
            data = data.copy()
            data["scraped_at"] = datetime.fromisoformat(data["scraped_at"])
        return cls.model_validate(data)

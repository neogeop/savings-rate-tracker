"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def sample_rate_data() -> dict:
    """Sample rate data for testing."""
    return {
        "provider": "tembo",
        "product_name": "tembo_cash_isa",
        "product_type": "cash_isa",
        "rate": "4.55",
        "rate_type": "variable",
        "scraped_at": "2026-03-12T10:00:00Z",
    }

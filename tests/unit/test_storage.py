"""Unit tests for storage backends."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.models.rate import SavingsRate
from src.models.types import ProductType, Provider, RateType, TemboProduct
from src.storage.csv_store import CSVStorage
from src.storage.json_store import JSONStorage


@pytest.fixture
def sample_rates() -> list[SavingsRate]:
    """Create sample rates for testing."""
    return [
        SavingsRate(
            provider=Provider.TEMBO,
            product_name=TemboProduct.CASH_ISA_EASY_ACCESS,
            product_type=ProductType.CASH_ISA,
            rate=Decimal("4.55"),
            rate_type=RateType.VARIABLE,
            scraped_at=datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc),
            url="https://tembo.com/isa",
        ),
        SavingsRate(
            provider=Provider.TEMBO,
            product_name=TemboProduct.CASH_ISA_FIXED_RATE,
            product_type=ProductType.FIXED_RATE,
            rate=Decimal("5.25"),
            rate_type=RateType.FIXED,
            scraped_at=datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc),
            term_months=12,
        ),
    ]


@pytest.fixture
def temp_json_path(tmp_path: Path) -> Path:
    """Create temp JSON file path."""
    return tmp_path / "rates.json"


@pytest.fixture
def temp_csv_path(tmp_path: Path) -> Path:
    """Create temp CSV file path."""
    return tmp_path / "rates.csv"


@pytest.mark.unit
class TestJSONStorageSave:
    """Tests for JSON storage save operation."""

    def test_save_creates_file(self, temp_json_path: Path, sample_rates):
        """Save creates JSON file."""
        storage = JSONStorage(temp_json_path)
        storage.save(sample_rates)

        assert temp_json_path.exists()

    def test_save_includes_schema_version(self, temp_json_path: Path, sample_rates):
        """Saved JSON includes schema version."""
        storage = JSONStorage(temp_json_path)
        storage.save(sample_rates)

        data = json.loads(temp_json_path.read_text())
        assert data["schema_version"] == "1.0"

    def test_save_serializes_rates(self, temp_json_path: Path, sample_rates):
        """Saved JSON contains serialized rates."""
        storage = JSONStorage(temp_json_path)
        storage.save(sample_rates)

        data = json.loads(temp_json_path.read_text())
        assert len(data["rates"]) == 2
        assert data["rates"][0]["rate"] == "4.55"
        assert data["rates"][0]["provider"] == "tembo"

    def test_save_creates_parent_dirs(self, tmp_path: Path, sample_rates):
        """Save creates parent directories if needed."""
        nested_path = tmp_path / "subdir" / "nested" / "rates.json"
        storage = JSONStorage(nested_path)
        storage.save(sample_rates)

        assert nested_path.exists()


@pytest.mark.unit
class TestJSONStorageLoad:
    """Tests for JSON storage load operation."""

    def test_load_returns_rates(self, temp_json_path: Path, sample_rates):
        """Load returns saved rates."""
        storage = JSONStorage(temp_json_path)
        storage.save(sample_rates)

        loaded = storage.load()
        assert len(loaded) == 2
        assert loaded[0].rate == Decimal("4.55")
        assert loaded[0].provider == Provider.TEMBO

    def test_load_missing_file_returns_empty(self, temp_json_path: Path):
        """Load returns empty list if file doesn't exist."""
        storage = JSONStorage(temp_json_path)
        loaded = storage.load()

        assert loaded == []

    def test_load_empty_file_returns_empty(self, temp_json_path: Path):
        """Load returns empty list for empty file."""
        temp_json_path.write_text("")
        storage = JSONStorage(temp_json_path)

        loaded = storage.load()
        assert loaded == []

    def test_load_invalid_json_raises(self, temp_json_path: Path):
        """Load raises error for invalid JSON."""
        temp_json_path.write_text("not valid json")
        storage = JSONStorage(temp_json_path)

        with pytest.raises(ValueError, match="Invalid JSON"):
            storage.load()


@pytest.mark.unit
class TestJSONStorageAppend:
    """Tests for JSON storage append operation."""

    def test_append_to_existing(self, temp_json_path: Path, sample_rates):
        """Append adds to existing rates."""
        storage = JSONStorage(temp_json_path)
        storage.save([sample_rates[0]])
        storage.append([sample_rates[1]])

        loaded = storage.load()
        assert len(loaded) == 2

    def test_append_to_empty(self, temp_json_path: Path, sample_rates):
        """Append to non-existent file creates it."""
        storage = JSONStorage(temp_json_path)
        storage.append(sample_rates)

        loaded = storage.load()
        assert len(loaded) == 2


@pytest.mark.unit
class TestCSVStorageSave:
    """Tests for CSV storage save operation."""

    def test_save_creates_file(self, temp_csv_path: Path, sample_rates):
        """Save creates CSV file."""
        storage = CSVStorage(temp_csv_path)
        storage.save(sample_rates)

        assert temp_csv_path.exists()

    def test_save_includes_header(self, temp_csv_path: Path, sample_rates):
        """Saved CSV includes header row."""
        storage = CSVStorage(temp_csv_path)
        storage.save(sample_rates)

        lines = temp_csv_path.read_text().split("\n")
        assert "provider" in lines[0]
        assert "rate" in lines[0]
        assert "product_name" in lines[0]

    def test_save_serializes_rates(self, temp_csv_path: Path, sample_rates):
        """Saved CSV contains rate data."""
        storage = CSVStorage(temp_csv_path)
        storage.save(sample_rates)

        content = temp_csv_path.read_text()
        assert "tembo" in content
        assert "4.55" in content
        assert "tembo_cash_isa_easy_access" in content


@pytest.mark.unit
class TestCSVStorageLoad:
    """Tests for CSV storage load operation."""

    def test_load_returns_rates(self, temp_csv_path: Path, sample_rates):
        """Load returns saved rates."""
        storage = CSVStorage(temp_csv_path)
        storage.save(sample_rates)

        loaded = storage.load()
        assert len(loaded) == 2
        assert loaded[0].rate == Decimal("4.55")
        assert loaded[0].provider == Provider.TEMBO

    def test_load_missing_file_returns_empty(self, temp_csv_path: Path):
        """Load returns empty list if file doesn't exist."""
        storage = CSVStorage(temp_csv_path)
        loaded = storage.load()

        assert loaded == []

    def test_load_handles_optional_fields(self, temp_csv_path: Path, sample_rates):
        """Load handles optional fields correctly."""
        storage = CSVStorage(temp_csv_path)
        storage.save(sample_rates)

        loaded = storage.load()
        assert loaded[0].url == "https://tembo.com/isa"
        assert loaded[0].term_months is None
        assert loaded[1].term_months == 12


@pytest.mark.unit
class TestCSVStorageAppend:
    """Tests for CSV storage append operation."""

    def test_append_to_existing(self, temp_csv_path: Path, sample_rates):
        """Append adds to existing rates."""
        storage = CSVStorage(temp_csv_path)
        storage.save([sample_rates[0]])
        storage.append([sample_rates[1]])

        loaded = storage.load()
        assert len(loaded) == 2

    def test_append_to_empty(self, temp_csv_path: Path, sample_rates):
        """Append to non-existent file creates it."""
        storage = CSVStorage(temp_csv_path)
        storage.append(sample_rates)

        loaded = storage.load()
        assert len(loaded) == 2


@pytest.mark.unit
class TestStorageRoundtrip:
    """Tests for save/load roundtrip."""

    def test_json_roundtrip_preserves_data(self, temp_json_path: Path, sample_rates):
        """JSON roundtrip preserves all data."""
        storage = JSONStorage(temp_json_path)
        storage.save(sample_rates)
        loaded = storage.load()

        assert loaded[0].provider == sample_rates[0].provider
        assert loaded[0].product_name == sample_rates[0].product_name
        assert loaded[0].rate == sample_rates[0].rate
        assert loaded[0].rate_type == sample_rates[0].rate_type
        assert loaded[0].url == sample_rates[0].url

    def test_csv_roundtrip_preserves_data(self, temp_csv_path: Path, sample_rates):
        """CSV roundtrip preserves all data."""
        storage = CSVStorage(temp_csv_path)
        storage.save(sample_rates)
        loaded = storage.load()

        assert loaded[0].provider == sample_rates[0].provider
        assert loaded[0].product_name == sample_rates[0].product_name
        assert loaded[0].rate == sample_rates[0].rate
        assert loaded[0].rate_type == sample_rates[0].rate_type
        assert loaded[0].url == sample_rates[0].url

    def test_roundtrip_with_all_optional_fields(self, temp_json_path: Path):
        """Roundtrip preserves all optional fields."""
        rate = SavingsRate(
            provider=Provider.TEMBO,
            product_name=TemboProduct.CASH_ISA_EASY_ACCESS,
            product_type=ProductType.CASH_ISA,
            rate=Decimal("4.55"),
            rate_type=RateType.VARIABLE,
            scraped_at=datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc),
            url="https://tembo.com/isa",
            term_months=12,
            min_deposit=Decimal("1"),
            max_deposit=Decimal("20000"),
            notes="Introductory rate",
        )

        storage = JSONStorage(temp_json_path)
        storage.save([rate])
        loaded = storage.load()

        assert loaded[0].url == rate.url
        assert loaded[0].term_months == rate.term_months
        assert loaded[0].min_deposit == rate.min_deposit
        assert loaded[0].max_deposit == rate.max_deposit
        assert loaded[0].notes == rate.notes

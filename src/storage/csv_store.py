"""CSV storage backend."""

import csv
import tempfile
from pathlib import Path

import structlog

from src.models.rate import SavingsRate

logger = structlog.get_logger(__name__)

CSV_FIELDS = [
    "provider",
    "product_name",
    "product_type",
    "rate",
    "rate_type",
    "scraped_at",
    "url",
    "term_months",
    "min_deposit",
    "max_deposit",
    "notes",
]


class CSVStorage:
    """CSV file storage backend for savings rates."""

    def __init__(self, path: Path | str) -> None:
        """Initialize CSV storage.

        Args:
            path: Path to CSV file.
        """
        self.path = Path(path)
        self._log = logger.bind(storage="csv", path=str(self.path))

    def save(self, rates: list[SavingsRate]) -> None:
        """Save rates to CSV file.

        Performs atomic write using temp file + rename.

        Args:
            rates: List of rates to save.
        """
        self._atomic_write(rates)
        self._log.info("storage.saved", count=len(rates))

    def load(self) -> list[SavingsRate]:
        """Load all rates from CSV file.

        Returns:
            List of saved rates, empty list if file doesn't exist.
        """
        if not self.path.exists():
            self._log.debug("storage.file_not_found")
            return []

        try:
            rates = []
            with open(self.path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert empty strings to None for optional fields
                    cleaned = self._clean_row(row)
                    rates.append(SavingsRate.from_dict(cleaned))

            self._log.info("storage.loaded", count=len(rates))
            return rates
        except csv.Error as e:
            self._log.error("storage.load_error", error=str(e))
            raise ValueError(f"Invalid CSV in {self.path}: {e}") from e

    def append(self, rates: list[SavingsRate]) -> None:
        """Append rates to existing CSV file.

        Args:
            rates: List of rates to append.
        """
        if not self.path.exists():
            self.save(rates)
            return

        existing = self.load()
        combined = existing + rates
        self.save(combined)
        self._log.info("storage.appended", new=len(rates), total=len(combined))

    def _clean_row(self, row: dict[str, str]) -> dict[str, str | None]:
        """Clean CSV row, converting empty strings to None.

        Args:
            row: Raw CSV row.

        Returns:
            Cleaned row with None for empty values.
        """
        return {k: (v if v else None) for k, v in row.items()}

    def _atomic_write(self, rates: list[SavingsRate]) -> None:
        """Write data atomically using temp file and rename.

        Args:
            rates: Rates to write.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=".tmp_",
            suffix=".csv",
        )
        temp_file = Path(temp_path)

        try:
            with open(fd, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for rate in rates:
                    row = self._rate_to_row(rate)
                    writer.writerow(row)
            temp_file.rename(self.path)
        except Exception:
            temp_file.unlink(missing_ok=True)
            raise

    def _rate_to_row(self, rate: SavingsRate) -> dict[str, str]:
        """Convert rate to CSV row.

        Args:
            rate: Rate to convert.

        Returns:
            Dictionary suitable for CSV writer.
        """
        data = rate.to_dict()
        # Convert None to empty string for CSV
        return {k: (str(v) if v is not None else "") for k, v in data.items()}

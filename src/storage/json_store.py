"""JSON storage backend."""

import json
import tempfile
from pathlib import Path
from typing import Any

import structlog

from src.models.rate import SavingsRate

logger = structlog.get_logger(__name__)

SCHEMA_VERSION = "1.0"


class JSONStorage:
    """JSON file storage backend for savings rates."""

    def __init__(self, path: Path | str) -> None:
        """Initialize JSON storage.

        Args:
            path: Path to JSON file.
        """
        self.path = Path(path)
        self._log = logger.bind(storage="json", path=str(self.path))

    def save(self, rates: list[SavingsRate]) -> None:
        """Save rates to JSON file.

        Performs atomic write using temp file + rename.

        Args:
            rates: List of rates to save.
        """
        data = self._serialize(rates)
        self._atomic_write(data)
        self._log.info("storage.saved", count=len(rates))

    def load(self) -> list[SavingsRate]:
        """Load all rates from JSON file.

        Returns:
            List of saved rates, empty list if file doesn't exist.
        """
        if not self.path.exists():
            self._log.debug("storage.file_not_found")
            return []

        try:
            content = self.path.read_text(encoding="utf-8")
            if not content.strip():
                return []

            data = json.loads(content)
            rates = self._deserialize(data)
            self._log.info("storage.loaded", count=len(rates))
            return rates
        except json.JSONDecodeError as e:
            self._log.error("storage.load_error", error=str(e))
            raise ValueError(f"Invalid JSON in {self.path}: {e}") from e

    def append(self, rates: list[SavingsRate]) -> None:
        """Append rates to existing JSON file.

        Args:
            rates: List of rates to append.
        """
        existing = self.load()
        combined = existing + rates
        self.save(combined)
        self._log.info("storage.appended", new=len(rates), total=len(combined))

    def _serialize(self, rates: list[SavingsRate]) -> dict[str, Any]:
        """Serialize rates to JSON-compatible dict.

        Args:
            rates: List of rates to serialize.

        Returns:
            Dictionary with schema version and rates.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "rates": [rate.to_dict() for rate in rates],
        }

    def _deserialize(self, data: dict[str, Any]) -> list[SavingsRate]:
        """Deserialize rates from JSON dict.

        Args:
            data: Dictionary with schema version and rates.

        Returns:
            List of SavingsRate objects.
        """
        version = data.get("schema_version", "1.0")
        if version != SCHEMA_VERSION:
            self._log.warning(
                "storage.schema_mismatch",
                expected=SCHEMA_VERSION,
                found=version,
            )

        rates_data = data.get("rates", [])
        return [SavingsRate.from_dict(r) for r in rates_data]

    def _atomic_write(self, data: dict[str, Any]) -> None:
        """Write data atomically using temp file and rename.

        Args:
            data: Data to write.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=".tmp_",
            suffix=".json",
        )
        temp_file = Path(temp_path)

        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_file.rename(self.path)
        except Exception:
            temp_file.unlink(missing_ok=True)
            raise

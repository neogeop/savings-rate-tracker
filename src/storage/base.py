"""Storage backend protocol."""

from typing import Protocol

from src.models.rate import SavingsRate


class StorageBackend(Protocol):
    """Protocol for storage backends."""

    def save(self, rates: list[SavingsRate]) -> None:
        """Save rates to storage.

        Args:
            rates: List of rates to save.
        """
        ...

    def load(self) -> list[SavingsRate]:
        """Load all rates from storage.

        Returns:
            List of saved rates.
        """
        ...

    def append(self, rates: list[SavingsRate]) -> None:
        """Append rates to existing storage.

        Args:
            rates: List of rates to append.
        """
        ...

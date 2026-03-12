"""Rate change detection and anomaly flagging."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from statistics import mean, stdev

import structlog

from src.models.rate import SavingsRate
from src.models.types import ProductName

logger = structlog.get_logger(__name__)


class ChangeType(str, Enum):
    """Types of rate changes."""

    INCREASE = "increase"
    DECREASE = "decrease"
    NO_CHANGE = "no_change"
    NEW_PRODUCT = "new_product"
    ANOMALY = "anomaly"


@dataclass
class RateChange:
    """Represents a detected rate change."""

    product_name: ProductName
    change_type: ChangeType
    previous_rate: Decimal | None
    current_rate: Decimal
    change_amount: Decimal
    change_percent: Decimal
    scraped_at: datetime
    is_anomaly: bool = False
    anomaly_reason: str | None = None

    @property
    def is_significant(self) -> bool:
        """Check if change is significant (>0.1%)."""
        return abs(self.change_percent) >= Decimal("0.1")


@dataclass
class ChangeDetectorConfig:
    """Configuration for change detection."""

    # Minimum change to consider significant (percentage points)
    significant_change_threshold: Decimal = Decimal("0.1")

    # Anomaly detection: flag if change exceeds this % of 30-day average
    anomaly_deviation_threshold: Decimal = Decimal("20.0")

    # Days of history to consider for anomaly detection
    history_days: int = 30


class ChangeDetector:
    """Detects rate changes and anomalies.

    Note: This class is NOT thread-safe. It is designed for use in
    single-threaded asyncio contexts only.
    """

    def __init__(
        self,
        config: ChangeDetectorConfig | None = None,
        historical_rates: list[SavingsRate] | None = None,
    ) -> None:
        """Initialize change detector.

        Args:
            config: Detection configuration.
            historical_rates: Previous rates for comparison.
        """
        self.config = config or ChangeDetectorConfig()
        self._history: dict[ProductName, list[SavingsRate]] = {}
        self._log = logger.bind(component="change_detector")

        if historical_rates:
            self._load_history(historical_rates)

    def _load_history(self, rates: list[SavingsRate]) -> None:
        """Load historical rates into memory.

        Args:
            rates: Historical rates to load.
        """
        for rate in rates:
            if rate.product_name not in self._history:
                self._history[rate.product_name] = []
            self._history[rate.product_name].append(rate)

        # Sort by date
        for product in self._history:
            self._history[product].sort(key=lambda r: r.scraped_at)

        self._log.debug("history.loaded", products=len(self._history))

    def detect_changes(self, current_rates: list[SavingsRate]) -> list[RateChange]:
        """Detect changes in current rates vs historical.

        Args:
            current_rates: Newly scraped rates.

        Returns:
            List of detected changes.
        """
        changes: list[RateChange] = []

        for rate in current_rates:
            change = self._analyze_rate(rate)
            if change:
                changes.append(change)
                self._log_change(change)

        # Update history with current rates
        for rate in current_rates:
            self._add_to_history(rate)

        return changes

    def _analyze_rate(self, rate: SavingsRate) -> RateChange | None:
        """Analyze a single rate for changes.

        Args:
            rate: Rate to analyze.

        Returns:
            RateChange if change detected, None otherwise.
        """
        history = self._history.get(rate.product_name, [])

        if not history:
            # New product
            return RateChange(
                product_name=rate.product_name,
                change_type=ChangeType.NEW_PRODUCT,
                previous_rate=None,
                current_rate=rate.rate,
                change_amount=Decimal("0"),
                change_percent=Decimal("0"),
                scraped_at=rate.scraped_at,
            )

        # Get most recent historical rate
        previous = history[-1]
        change_amount = rate.rate - previous.rate

        # Calculate percent change (handle zero previous rate)
        if previous.rate == Decimal("0"):
            change_percent = Decimal("100") if rate.rate > 0 else Decimal("0")
        else:
            change_percent = (change_amount / previous.rate) * Decimal("100")

        # Determine change type
        if change_amount > Decimal("0"):
            change_type = ChangeType.INCREASE
        elif change_amount < Decimal("0"):
            change_type = ChangeType.DECREASE
        else:
            change_type = ChangeType.NO_CHANGE

        # Check for anomaly
        is_anomaly, anomaly_reason = self._check_anomaly(rate, history)

        if is_anomaly:
            change_type = ChangeType.ANOMALY

        return RateChange(
            product_name=rate.product_name,
            change_type=change_type,
            previous_rate=previous.rate,
            current_rate=rate.rate,
            change_amount=change_amount,
            change_percent=change_percent,
            scraped_at=rate.scraped_at,
            is_anomaly=is_anomaly,
            anomaly_reason=anomaly_reason,
        )

    def _check_anomaly(
        self, rate: SavingsRate, history: list[SavingsRate]
    ) -> tuple[bool, str | None]:
        """Check if rate change is anomalous.

        Args:
            rate: Current rate.
            history: Historical rates.

        Returns:
            Tuple of (is_anomaly, reason).
        """
        # Need enough history for meaningful analysis
        if len(history) < 3:
            return False, None

        # Filter to recent history
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.history_days)
        recent = [r for r in history if r.scraped_at >= cutoff]

        if len(recent) < 3:
            return False, None

        # Calculate statistics
        rates = [float(r.rate) for r in recent]
        avg = mean(rates)
        std = stdev(rates) if len(rates) > 1 else 0

        # Check deviation from average
        current = float(rate.rate)
        if avg > 0:
            deviation_percent = abs(current - avg) / avg * 100

            if deviation_percent > float(self.config.anomaly_deviation_threshold):
                days = self.config.history_days
                reason = f"Rate deviates {deviation_percent:.1f}% from {days}-day average"
                return True, reason

        # Check for sudden large change
        if std > 0:
            z_score = abs(current - avg) / std
            if z_score > 3:  # More than 3 standard deviations
                return True, f"Rate is {z_score:.1f} standard deviations from mean"

        return False, None

    def _add_to_history(self, rate: SavingsRate) -> None:
        """Add rate to history.

        Args:
            rate: Rate to add.
        """
        if rate.product_name not in self._history:
            self._history[rate.product_name] = []
        self._history[rate.product_name].append(rate)

    def _log_change(self, change: RateChange) -> None:
        """Log a detected change.

        Args:
            change: Change to log.
        """
        log_method = self._log.warning if change.is_anomaly else self._log.info

        log_method(
            "change.detected",
            product=change.product_name.value,
            change_type=change.change_type.value,
            previous=str(change.previous_rate) if change.previous_rate else None,
            current=str(change.current_rate),
            change_percent=f"{change.change_percent:.2f}%",
            is_anomaly=change.is_anomaly,
            anomaly_reason=change.anomaly_reason,
        )

    def get_significant_changes(
        self, changes: list[RateChange]
    ) -> list[RateChange]:
        """Filter to only significant changes.

        Args:
            changes: All changes.

        Returns:
            Significant changes only.
        """
        return [c for c in changes if c.is_significant or c.is_anomaly]

    def get_anomalies(self, changes: list[RateChange]) -> list[RateChange]:
        """Filter to only anomalies.

        Args:
            changes: All changes.

        Returns:
            Anomalies only.
        """
        return [c for c in changes if c.is_anomaly]

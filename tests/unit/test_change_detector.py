"""Unit tests for change detector."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.analysis.change_detector import (
    ChangeDetector,
    ChangeDetectorConfig,
    ChangeType,
    RateChange,
)
from src.models.rate import SavingsRate
from src.models.types import ProductType, Provider, RateType, TemboProduct


def make_rate(
    rate: Decimal,
    product: TemboProduct = TemboProduct.CASH_ISA_EASY_ACCESS,
    days_ago: int = 0,
) -> SavingsRate:
    """Create a test rate."""
    return SavingsRate(
        provider=Provider.TEMBO,
        product_name=product,
        product_type=ProductType.CASH_ISA,
        rate=rate,
        rate_type=RateType.VARIABLE,
        scraped_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


@pytest.mark.unit
class TestRateChange:
    """Tests for RateChange dataclass."""

    def test_is_significant_above_threshold(self):
        """Change above threshold is significant."""
        change = RateChange(
            product_name=TemboProduct.CASH_ISA_EASY_ACCESS,
            change_type=ChangeType.INCREASE,
            previous_rate=Decimal("4.00"),
            current_rate=Decimal("4.15"),
            change_amount=Decimal("0.15"),
            change_percent=Decimal("3.75"),
            scraped_at=datetime.now(timezone.utc),
        )
        assert change.is_significant is True

    def test_is_significant_below_threshold(self):
        """Change below threshold is not significant."""
        change = RateChange(
            product_name=TemboProduct.CASH_ISA_EASY_ACCESS,
            change_type=ChangeType.INCREASE,
            previous_rate=Decimal("4.00"),
            current_rate=Decimal("4.003"),
            change_amount=Decimal("0.003"),
            change_percent=Decimal("0.075"),
            scraped_at=datetime.now(timezone.utc),
        )
        assert change.is_significant is False


@pytest.mark.unit
class TestChangeDetectorInit:
    """Tests for ChangeDetector initialization."""

    def test_default_config(self):
        """Detector uses default config."""
        detector = ChangeDetector()
        assert detector.config.significant_change_threshold == Decimal("0.1")
        assert detector.config.anomaly_deviation_threshold == Decimal("20.0")

    def test_custom_config(self):
        """Detector accepts custom config."""
        config = ChangeDetectorConfig(
            significant_change_threshold=Decimal("0.5"),
            anomaly_deviation_threshold=Decimal("30.0"),
        )
        detector = ChangeDetector(config=config)
        assert detector.config.significant_change_threshold == Decimal("0.5")

    def test_loads_historical_rates(self):
        """Detector loads historical rates."""
        history = [make_rate(Decimal("4.00"), days_ago=1)]
        detector = ChangeDetector(historical_rates=history)
        assert TemboProduct.CASH_ISA_EASY_ACCESS in detector._history

    def test_load_history_sorted_chronologically(self):
        """_load_history sorts ascending by scraped_at regardless of input order."""
        rates = [
            make_rate(Decimal("4.30"), days_ago=1),
            make_rate(Decimal("4.10"), days_ago=5),
            make_rate(Decimal("4.20"), days_ago=3),
        ]
        detector = ChangeDetector()
        detector._load_history(rates)
        stored = detector._history[TemboProduct.CASH_ISA_EASY_ACCESS]
        timestamps = [r.scraped_at for r in stored]
        assert timestamps == sorted(timestamps)


@pytest.mark.unit
class TestChangeDetection:
    """Tests for change detection."""

    def test_detect_increase(self):
        """Detects rate increase."""
        history = [make_rate(Decimal("4.00"), days_ago=1)]
        detector = ChangeDetector(historical_rates=history)

        current = [make_rate(Decimal("4.50"))]
        changes = detector.detect_changes(current)

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.INCREASE
        assert changes[0].change_amount == Decimal("0.50")

    def test_detect_decrease(self):
        """Detects rate decrease."""
        history = [make_rate(Decimal("4.00"), days_ago=1)]
        detector = ChangeDetector(historical_rates=history)

        current = [make_rate(Decimal("3.50"))]
        changes = detector.detect_changes(current)

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.DECREASE
        assert changes[0].change_amount == Decimal("-0.50")

    def test_detect_no_change(self):
        """Detects no change."""
        history = [make_rate(Decimal("4.00"), days_ago=1)]
        detector = ChangeDetector(historical_rates=history)

        current = [make_rate(Decimal("4.00"))]
        changes = detector.detect_changes(current)

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.NO_CHANGE

    def test_detect_new_product(self):
        """Detects new product."""
        detector = ChangeDetector()

        current = [make_rate(Decimal("4.00"))]
        changes = detector.detect_changes(current)

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.NEW_PRODUCT
        assert changes[0].previous_rate is None

    def test_calculates_percent_change(self):
        """Calculates percent change correctly."""
        history = [make_rate(Decimal("4.00"), days_ago=1)]
        detector = ChangeDetector(historical_rates=history)

        current = [make_rate(Decimal("4.50"))]
        changes = detector.detect_changes(current)

        assert changes[0].change_percent == Decimal("12.5")  # 0.50/4.00 * 100


@pytest.mark.unit
class TestAnomalyDetection:
    """Tests for anomaly detection."""

    def test_detects_anomaly_large_deviation(self):
        """Detects anomaly when rate deviates significantly."""
        # Build history with stable rates around 4.0%
        history = [
            make_rate(Decimal("4.00"), days_ago=10),
            make_rate(Decimal("4.02"), days_ago=7),
            make_rate(Decimal("3.98"), days_ago=5),
            make_rate(Decimal("4.01"), days_ago=3),
            make_rate(Decimal("3.99"), days_ago=1),
        ]
        detector = ChangeDetector(historical_rates=history)

        # Sudden jump to 5.5% (>20% deviation from ~4% average)
        current = [make_rate(Decimal("5.50"))]
        changes = detector.detect_changes(current)

        assert len(changes) == 1
        assert changes[0].is_anomaly is True
        assert changes[0].change_type == ChangeType.ANOMALY

    def test_no_anomaly_for_gradual_change(self):
        """No anomaly for gradual rate changes."""
        history = [
            make_rate(Decimal("4.00"), days_ago=10),
            make_rate(Decimal("4.10"), days_ago=7),
            make_rate(Decimal("4.20"), days_ago=5),
            make_rate(Decimal("4.30"), days_ago=3),
            make_rate(Decimal("4.40"), days_ago=1),
        ]
        detector = ChangeDetector(historical_rates=history)

        # Continued gradual increase
        current = [make_rate(Decimal("4.50"))]
        changes = detector.detect_changes(current)

        assert len(changes) == 1
        assert changes[0].is_anomaly is False

    def test_no_anomaly_with_insufficient_history(self):
        """No anomaly detection with insufficient history."""
        history = [make_rate(Decimal("4.00"), days_ago=1)]
        detector = ChangeDetector(historical_rates=history)

        # Large change but not enough history to call it anomaly
        current = [make_rate(Decimal("6.00"))]
        changes = detector.detect_changes(current)

        assert len(changes) == 1
        assert changes[0].is_anomaly is False


@pytest.mark.unit
class TestHistoryManagement:
    """Tests for history management."""

    def test_updates_history_after_detection(self):
        """History is updated after detection."""
        detector = ChangeDetector()

        current = [make_rate(Decimal("4.00"))]
        detector.detect_changes(current)

        assert len(detector._history[TemboProduct.CASH_ISA_EASY_ACCESS]) == 1

        # Second detection adds to history
        current2 = [make_rate(Decimal("4.10"))]
        detector.detect_changes(current2)

        assert len(detector._history[TemboProduct.CASH_ISA_EASY_ACCESS]) == 2


@pytest.mark.unit
class TestFilterMethods:
    """Tests for filter methods."""

    def test_get_significant_changes(self):
        """Filters to significant changes."""
        detector = ChangeDetector()
        changes = [
            RateChange(
                product_name=TemboProduct.CASH_ISA_EASY_ACCESS,
                change_type=ChangeType.INCREASE,
                previous_rate=Decimal("4.00"),
                current_rate=Decimal("4.50"),
                change_amount=Decimal("0.50"),
                change_percent=Decimal("12.5"),
                scraped_at=datetime.now(timezone.utc),
            ),
            RateChange(
                product_name=TemboProduct.CASH_ISA_FIXED_RATE,
                change_type=ChangeType.NO_CHANGE,
                previous_rate=Decimal("5.00"),
                current_rate=Decimal("5.00"),
                change_amount=Decimal("0"),
                change_percent=Decimal("0"),
                scraped_at=datetime.now(timezone.utc),
            ),
        ]

        significant = detector.get_significant_changes(changes)
        assert len(significant) == 1
        assert significant[0].product_name == TemboProduct.CASH_ISA_EASY_ACCESS

    def test_get_anomalies(self):
        """Filters to anomalies only."""
        detector = ChangeDetector()
        changes = [
            RateChange(
                product_name=TemboProduct.CASH_ISA_EASY_ACCESS,
                change_type=ChangeType.ANOMALY,
                previous_rate=Decimal("4.00"),
                current_rate=Decimal("6.00"),
                change_amount=Decimal("2.00"),
                change_percent=Decimal("50"),
                scraped_at=datetime.now(timezone.utc),
                is_anomaly=True,
                anomaly_reason="Test anomaly",
            ),
            RateChange(
                product_name=TemboProduct.CASH_ISA_FIXED_RATE,
                change_type=ChangeType.INCREASE,
                previous_rate=Decimal("5.00"),
                current_rate=Decimal("5.10"),
                change_amount=Decimal("0.10"),
                change_percent=Decimal("2"),
                scraped_at=datetime.now(timezone.utc),
            ),
        ]

        anomalies = detector.get_anomalies(changes)
        assert len(anomalies) == 1
        assert anomalies[0].is_anomaly is True

"""Unit tests for rate limiter and circuit breaker."""

import asyncio
import time
from unittest.mock import patch

import pytest

from src.utils.rate_limiter import (
    CircuitBreaker,
    CircuitState,
    RateLimiter,
    TokenBucket,
)


@pytest.mark.unit
class TestTokenBucket:
    """Tests for token bucket rate limiter."""

    def test_initial_capacity(self):
        """Bucket starts with full capacity."""
        bucket = TokenBucket(rate=1.0, capacity=10)
        assert bucket.tokens == 10.0

    def test_acquire_immediate(self):
        """Acquire returns 0 when tokens available."""
        bucket = TokenBucket(rate=1.0, capacity=10)
        wait_time = bucket.acquire(1)
        assert wait_time == 0.0
        assert bucket.tokens == 9.0

    def test_acquire_multiple(self):
        """Acquire multiple tokens at once."""
        bucket = TokenBucket(rate=1.0, capacity=10)
        wait_time = bucket.acquire(5)
        assert wait_time == 0.0
        assert bucket.tokens == 5.0

    def test_acquire_returns_wait_time(self):
        """Acquire returns wait time when tokens insufficient."""
        bucket = TokenBucket(rate=1.0, capacity=2)
        bucket.acquire(2)  # Empty bucket
        wait_time = bucket.acquire(1)
        assert wait_time > 0

    def test_refill_over_time(self):
        """Tokens refill over time."""
        bucket = TokenBucket(rate=10.0, capacity=10)
        bucket.acquire(10)  # Empty bucket

        # Simulate time passing
        bucket.last_refill = time.monotonic() - 0.5  # 0.5 seconds ago
        bucket._refill()

        assert bucket.tokens >= 4.0  # ~5 tokens refilled at 10/sec

    def test_capacity_limit(self):
        """Tokens don't exceed capacity."""
        bucket = TokenBucket(rate=100.0, capacity=10)
        bucket.last_refill = time.monotonic() - 10  # 10 seconds ago
        bucket._refill()

        assert bucket.tokens == 10.0

    async def test_acquire_async_waits(self):
        """Async acquire waits when needed."""
        bucket = TokenBucket(rate=100.0, capacity=1)
        bucket.acquire(1)  # Empty bucket

        start = time.monotonic()
        await bucket.acquire_async(1)
        elapsed = time.monotonic() - start

        # Should have waited a small amount
        assert elapsed >= 0.005  # At least 5ms for 1 token at 100/sec


@pytest.mark.unit
class TestCircuitBreaker:
    """Tests for circuit breaker."""

    def test_initial_state_closed(self):
        """Circuit starts in closed state."""
        circuit = CircuitBreaker()
        assert circuit.state == CircuitState.CLOSED
        assert circuit.can_execute() is True

    def test_opens_after_threshold(self):
        """Circuit opens after failure threshold."""
        circuit = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            circuit.record_failure()

        assert circuit.state == CircuitState.OPEN
        assert circuit.can_execute() is False

    def test_stays_closed_below_threshold(self):
        """Circuit stays closed below threshold."""
        circuit = CircuitBreaker(failure_threshold=3)

        circuit.record_failure()
        circuit.record_failure()

        assert circuit.state == CircuitState.CLOSED
        assert circuit.can_execute() is True

    def test_success_resets_failure_count(self):
        """Success resets failure count."""
        circuit = CircuitBreaker(failure_threshold=3)

        circuit.record_failure()
        circuit.record_failure()
        circuit.record_success()

        assert circuit.failure_count == 0

    def test_transitions_to_half_open(self):
        """Circuit transitions to half-open after timeout."""
        circuit = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        circuit.record_failure()
        assert circuit.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)
        assert circuit.can_execute() is True
        assert circuit.state == CircuitState.HALF_OPEN

    def test_half_open_limits_calls(self):
        """Half-open state limits concurrent calls."""
        circuit = CircuitBreaker(
            failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=1
        )

        circuit.record_failure()
        time.sleep(0.15)

        # First call allowed
        assert circuit.can_execute() is True
        # Second call blocked
        assert circuit.can_execute() is False

    def test_half_open_closes_on_success(self):
        """Half-open closes on success."""
        circuit = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        circuit.record_failure()
        time.sleep(0.15)
        circuit.can_execute()  # Transition to half-open
        circuit.record_success()

        assert circuit.state == CircuitState.CLOSED

    def test_half_open_opens_on_failure(self):
        """Half-open opens on failure."""
        circuit = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        circuit.record_failure()
        time.sleep(0.15)
        circuit.can_execute()  # Transition to half-open
        circuit.record_failure()

        assert circuit.state == CircuitState.OPEN


@pytest.mark.unit
class TestRateLimiter:
    """Tests for combined rate limiter."""

    async def test_acquire_succeeds(self):
        """Acquire succeeds when circuit closed."""
        limiter = RateLimiter()
        result = await limiter.acquire("test_provider")
        assert result is True

    async def test_acquire_fails_when_circuit_open(self):
        """Acquire fails when circuit is open."""
        limiter = RateLimiter(failure_threshold=1)
        limiter.record_failure("test_provider")

        result = await limiter.acquire("test_provider")
        assert result is False

    def test_per_provider_isolation(self):
        """Each provider has isolated circuit."""
        limiter = RateLimiter(failure_threshold=1)

        limiter.record_failure("provider_a")

        assert limiter.get_circuit_state("provider_a") == CircuitState.OPEN
        assert limiter.get_circuit_state("provider_b") == CircuitState.CLOSED

    def test_configure_provider(self):
        """Configure custom rate for provider."""
        limiter = RateLimiter(default_rate=1.0)
        limiter.configure_provider("fast_provider", rate=10.0, capacity=20)

        bucket = limiter._buckets["fast_provider"]
        assert bucket.rate == 10.0
        assert bucket.capacity == 20

    def test_get_circuit_state(self):
        """Get circuit state for provider."""
        limiter = RateLimiter()

        assert limiter.get_circuit_state("unknown") == CircuitState.CLOSED

        limiter._circuits["known"].state = CircuitState.OPEN
        assert limiter.get_circuit_state("known") == CircuitState.OPEN

    async def test_rate_limiting_per_provider(self):
        """Rate limiting is per-provider."""
        limiter = RateLimiter(default_rate=100.0, default_capacity=5)

        # Exhaust provider_a bucket
        for _ in range(5):
            await limiter.acquire("provider_a")

        # provider_b should still work immediately
        start = time.monotonic()
        await limiter.acquire("provider_b")
        elapsed = time.monotonic() - start

        assert elapsed < 0.05  # Should be fast


@pytest.mark.unit
class TestRateLimiterRecovery:
    """Tests for circuit breaker recovery."""

    async def test_recovery_after_success(self):
        """Circuit recovers after successful call in half-open."""
        limiter = RateLimiter(failure_threshold=1, recovery_timeout=0.1)

        limiter.record_failure("test")
        assert limiter.get_circuit_state("test") == CircuitState.OPEN

        # Wait for recovery
        await asyncio.sleep(0.15)
        await limiter.acquire("test")
        limiter.record_success("test")

        assert limiter.get_circuit_state("test") == CircuitState.CLOSED

    async def test_repeated_failures_keep_open(self):
        """Repeated failures keep circuit open."""
        limiter = RateLimiter(failure_threshold=1, recovery_timeout=0.1)

        limiter.record_failure("test")

        # Wait and fail again
        await asyncio.sleep(0.15)
        await limiter.acquire("test")
        limiter.record_failure("test")

        assert limiter.get_circuit_state("test") == CircuitState.OPEN

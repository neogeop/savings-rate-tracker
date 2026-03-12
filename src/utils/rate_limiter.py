"""Rate limiting and circuit breaker utilities."""

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.exceptions.scraping import ScrapingError

logger = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class TokenBucket:
    """Token bucket rate limiter.

    Note: This class is NOT thread-safe. It is designed for use in
    single-threaded asyncio contexts only. See ADR-001.
    """

    rate: float  # Tokens per second
    capacity: int  # Maximum tokens
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        """Initialize bucket with full capacity."""
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def acquire(self, tokens: int = 1) -> float:
        """Try to acquire tokens.

        Args:
            tokens: Number of tokens to acquire.

        Returns:
            Wait time in seconds (0 if acquired immediately).
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return 0.0

        # Calculate wait time
        needed = tokens - self.tokens
        wait_time = needed / self.rate
        return wait_time

    async def acquire_async(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire.
        """
        wait_time = self.acquire(tokens)
        if wait_time > 0:
            logger.debug("rate_limiter.waiting", wait_seconds=wait_time)
            await asyncio.sleep(wait_time)
            # Re-acquire after waiting
            self._refill()
            self.tokens -= tokens


@dataclass
class CircuitBreaker:
    """Circuit breaker for handling service failures.

    Note: This class is NOT thread-safe. It is designed for use in
    single-threaded asyncio contexts only. See ADR-001.
    """

    failure_threshold: int = 3  # Failures before opening
    recovery_timeout: float = 300.0  # Seconds before trying half-open
    half_open_max_calls: int = 1  # Calls allowed in half-open

    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    last_failure_time: float = field(default=0.0)
    half_open_calls: int = field(default=0)

    def __post_init__(self) -> None:
        """Initialize logger."""
        self._log = logger.bind(component="circuit_breaker")

    def can_execute(self) -> bool:
        """Check if request can be executed.

        Returns:
            True if request should proceed, False if circuit is open.
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                self.half_open_calls += 1  # Count transition as first call
                return True
            return False

        # HALF_OPEN - allow limited calls
        if self.half_open_calls < self.half_open_max_calls:
            self.half_open_calls += 1
            return True
        return False

    def record_success(self) -> None:
        """Record successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.CLOSED)
            self._log.info("circuit.closed", reason="success_in_half_open")

        self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
            self._log.warning("circuit.opened", reason="failure_in_half_open")
        elif self.failure_count >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)
            self._log.warning(
                "circuit.opened",
                reason="threshold_exceeded",
                failures=self.failure_count,
            )

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state."""
        old_state = self.state
        self.state = new_state

        if new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0

        self._log.debug(
            "circuit.transition",
            from_state=old_state.value,
            to_state=new_state.value,
        )


class RateLimiter:
    """Combined rate limiter with per-provider buckets and circuit breakers.

    Note: This class is NOT thread-safe. It is designed for use in
    single-threaded asyncio contexts only. See ADR-001.
    """

    def __init__(
        self,
        default_rate: float = 0.5,  # requests per second
        default_capacity: int = 10,  # max burst
        failure_threshold: int = 3,
        recovery_timeout: float = 300.0,
    ) -> None:
        """Initialize rate limiter.

        Args:
            default_rate: Default requests per second.
            default_capacity: Default bucket capacity.
            failure_threshold: Failures before circuit opens.
            recovery_timeout: Seconds before circuit recovery attempt.
        """
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(rate=default_rate, capacity=default_capacity)
        )
        self._circuits: dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        )
        self._log = logger.bind(component="rate_limiter")

    async def acquire(self, provider: str) -> bool:
        """Acquire permission to make a request.

        Args:
            provider: Provider identifier.

        Returns:
            True if request can proceed, False if circuit is open.
        """
        circuit = self._circuits[provider]

        if not circuit.can_execute():
            self._log.warning(
                "rate_limiter.blocked",
                provider=provider,
                circuit_state=circuit.state.value,
            )
            return False

        bucket = self._buckets[provider]
        await bucket.acquire_async()
        return True

    def record_success(self, provider: str) -> None:
        """Record successful request.

        Args:
            provider: Provider identifier.
        """
        self._circuits[provider].record_success()

    def record_failure(self, provider: str) -> None:
        """Record failed request.

        Args:
            provider: Provider identifier.
        """
        self._circuits[provider].record_failure()

    def get_circuit_state(self, provider: str) -> CircuitState:
        """Get circuit state for provider.

        Args:
            provider: Provider identifier.

        Returns:
            Current circuit state.
        """
        return self._circuits[provider].state

    def configure_provider(
        self, provider: str, rate: float, capacity: int
    ) -> None:
        """Configure rate limit for specific provider.

        Args:
            provider: Provider identifier.
            rate: Requests per second.
            capacity: Maximum burst capacity.
        """
        self._buckets[provider] = TokenBucket(rate=rate, capacity=capacity)
        self._log.debug(
            "rate_limiter.configured",
            provider=provider,
            rate=rate,
            capacity=capacity,
        )


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
) -> Callable[[F], F]:
    """Decorator for retrying operations with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts.
        min_wait: Minimum wait between retries (seconds).
        max_wait: Maximum wait between retries (seconds).

    Returns:
        Decorator function.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=min_wait, max=max_wait),
        retry=retry_if_exception_type(ScrapingError),
        reraise=True,
    )

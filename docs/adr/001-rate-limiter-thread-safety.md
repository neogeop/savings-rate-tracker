# ADR-001: Rate Limiter and Circuit Breaker Thread Safety

## Status

Accepted

## Context

The scraping agent includes rate limiting (`TokenBucket`), circuit breaker (`CircuitBreaker`), and a combined `RateLimiter` class. These components maintain mutable state:

- `TokenBucket`: `tokens`, `last_refill`
- `CircuitBreaker`: `state`, `failure_count`, `last_failure_time`, `half_open_calls`
- `RateLimiter`: dictionaries of buckets and circuits per provider

We need to decide whether these components should be thread-safe.

## Decision

**We will NOT implement thread safety for these components.**

The components are designed for use in a single-threaded asyncio context and do not use locks or atomic operations.

## Rationale

### 1. Asyncio is Single-Threaded

The scraping agent uses Python's `asyncio` for concurrency. Asyncio runs in a single thread with cooperative multitasking - coroutines only yield control at `await` points.

```python
async def acquire_async(self, tokens: int = 1) -> None:
    wait_time = self.acquire(tokens)  # Sync - runs atomically
    if wait_time > 0:
        await asyncio.sleep(wait_time)  # Only yields AFTER state is modified
```

Between `await` points, code runs without interruption, making race conditions impossible in pure async code.

### 2. No Shared State Across Processes

Each scraper process has its own `RateLimiter` instance. We don't use shared memory or distributed state, so cross-process races don't apply.

### 3. Simplicity Over Defensive Coding

Adding locks would:
- Increase code complexity
- Add potential for deadlocks
- Reduce performance (lock contention)
- Solve a problem we don't have

### 4. Clear Boundaries

The scraping agent is a CLI tool, not a library. We control the execution context and can guarantee single-threaded async usage.

## Consequences

### Positive

- Simpler implementation
- Better performance (no lock overhead)
- Easier to reason about

### Negative

- Cannot safely use with `ThreadPoolExecutor` or `asyncio.to_thread()`
- Cannot share instances across threads
- Must document this limitation

### Mitigations

1. Add docstrings noting async-only safety:
   ```python
   class TokenBucket:
       """Token bucket rate limiter.

       Note: This class is NOT thread-safe. It is designed for use
       in single-threaded asyncio contexts only.
       """
   ```

2. If threading is needed in the future, create a `ThreadSafeRateLimiter` variant

## Alternatives Considered

### 1. Use `asyncio.Lock`

```python
self._lock = asyncio.Lock()

async def acquire_async(self, tokens: int = 1) -> None:
    async with self._lock:
        wait_time = self.acquire(tokens)
    # ...
```

Rejected: Unnecessary for pure async usage, adds complexity.

### 2. Use `threading.Lock`

```python
self._lock = threading.Lock()

def acquire(self, tokens: int = 1) -> float:
    with self._lock:
        self._refill()
        # ...
```

Rejected: We don't use threads, and mixing threading locks with asyncio can cause issues.

### 3. Use Atomic Operations

Use `atomics` library or implement lock-free algorithms.

Rejected: Over-engineered for our use case.

## References

- [Python asyncio documentation](https://docs.python.org/3/library/asyncio.html)
- [Thread Safety in Python](https://docs.python.org/3/glossary.html#term-GIL)
- [Designing for Concurrency](https://martinfowler.com/articles/patterns-of-distributed-systems/)

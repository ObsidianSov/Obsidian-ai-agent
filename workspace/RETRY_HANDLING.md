# Retry Handling Strategy

## Overview

Retries are essential for handling transient failures. We need a systematic approach with:
- Exponential backoff
- Jitter to prevent thundering herd
- Configurable limits
- Proper error classification

---

## Retry Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          RETRY DECISION TREE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Attempt N fails                                                       │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Is error retriable?                                               │   │
│  │                                                                  │   │
│  │  YES ────────────────────────────── NO                          │   │
│  │   │                                        │                      │   │
│  │   │                                        ▼                      │   │
│  │   │                               ┌─────────────────┐           │   │
│  │   │                               │ Fail immediately │           │   │
│  │   │                               │ (bad API key,   │           │   │
│  │   │                               │  parse error)   │           │   │
│  │   │                               └─────────────────┘           │   │
│  │   │                                                                │   │
│  │   ▼                                                                │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ Attempt < max_retries?                                      │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │        │                                                            │   │
│  │        ├── YES ───────────────────────────────────────────────┘   │   │
│  │        │                                                            │   │
│  │        │    ┌──────────────────────────────────────────────────┐   │   │
│  │        │    │ Calculate delay                                   │   │   │
│  │        │    │                                                  │   │   │
│  │        │    │ delay = min(base * (exponential^attempt), max)   │   │   │
│  │        │    │ + random_jitter                                  │   │   │
│  │        │    └──────────────────────────────────────────────────┘   │   │
│  │        │                           │                              │   │
│  │        │                           ▼                              │   │
│  │        │    ┌──────────────────────────────────────────────────┐   │   │
│  │        │    │ Wait, then retry                                  │   │   │
│  │        │    └──────────────────────────────────────────────────┘   │   │
│  │        │                           │                              │   │
│  │        │                           ▼                              │   │
│  │        └─────────────────────────► Retry ◄────────────────────────┘   │   │
│  │                                                                │       │   │
│  │        └── NO (max retries exceeded)                            │       │   │
│  │                │                                               │       │   │
│  │                ▼                                               │       │   │
│  │        ┌─────────────────────────────┐                         │       │   │
│  │        │ Return/fallback             │                         │       │   │
│  │        │ - Return error to user     │                         │       │   │
│  │        │ - Use fallback behavior    │                         │       │   │
│  │        │ - Try alternative path    │                         │       │   │
│  │        └─────────────────────────────┘                         │       │   │
│  │                                                                │       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Retry Parameters

```python
@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    
    # Number of retry attempts
    max_attempts: int = 3
    
    # Base delay in seconds
    base_delay: float = 1.0
    
    # Maximum delay cap in seconds
    max_delay: float = 60.0
    
    # Exponential base (delay = base * exponential^attempt)
    exponential_base: float = 2.0
    
    # Add randomness to prevent thundering herd
    jitter: bool = True
    jitter_range: float = 0.5  # ±50% randomization
    
    # Which exceptions to retry
    retriable_exceptions: tuple = (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.HTTPError,  # For 5xx errors
    )
```

---

## Delay Calculation

### Formula

```
delay = min(base_delay * (exponential_base ^ attempt), max_delay) + random_jitter
```

### Examples

| Attempt | Base Delay | With Jitter (50%) | Cap |
|---------|------------|-------------------|-----|
| 1 | 1.0s | 0.5s - 1.5s | - |
| 2 | 2.0s | 1.0s - 3.0s | - |
| 3 | 4.0s | 2.0s - 6.0s | - |
| 4 | 8.0s | 4.0s - 12.0s | 60s capped |
| 5 | 16.0s | 8.0s - 24.0s | 60s capped |

---

## Implementation

### 1. Retry Decorator

```python
# agent_core/retry.py

import time
import random
import functools
from typing import Type, Tuple, Callable, Any

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    jitter_range: float = 0.5,
    retriable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] = None
):
    """
    Decorator that adds retry logic to a function.
    
    Args:
        max_attempts: Maximum number of attempts (including first)
        base_delay: Initial delay between retries
        max_delay: Maximum delay cap
        exponential_base: Multiplier for delay each attempt
        jitter: Whether to add randomness
        jitter_range: Jitter range as fraction (0.5 = ±50%)
        retriable_exceptions: Tuple of exceptions that trigger retry
        on_retry: Callback function(exception, attempt) for logging
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                    
                except retriable_exceptions as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if attempt < max_attempts - 1:
                        # Calculate delay
                        delay = _calculate_delay(
                            attempt,
                            base_delay,
                            max_delay,
                            exponential_base,
                            jitter,
                            jitter_range
                        )
                        
                        # Log retry
                        if on_retry:
                            on_retry(e, attempt + 1)
                        
                        # Wait before retry
                        time.sleep(delay)
                    else:
                        # Max attempts exceeded
                        break
            
            # All retries failed
            raise last_exception
        
        return wrapper
    return decorator


def _calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
    jitter_range: float
) -> float:
    """Calculate delay with optional jitter"""
    
    # Exponential backoff
    delay = base_delay * (exponential_base ** attempt)
    
    # Cap at max
    delay = min(delay, max_delay)
    
    # Add jitter
    if jitter:
        jitter_amount = delay * jitter_range
        delay = delay + random.uniform(-jitter_amount, jitter_amount)
    
    return max(0, delay)
```

### 2. LLM Provider with Retry

```python
# agent_core/llm.py

import requests
import time

class OpenRouterProvider:
    """OpenRouter API client with retry logic"""
    
    RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    MAX_RETRIES = 3
    BASE_DELAY = 2.0
    MAX_DELAY = 60.0
    
    def __init__(self, api_key: str = None, **config):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.max_retries = config.get("max_retries", self.MAX_RETRIES)
        self.base_delay = config.get("base_delay", self.BASE_DELAY)
        self.max_delay = config.get("max_delay", self.MAX_DELAY)
        # ... rest of init
    
    def complete(self, prompt: str, system_prompt: str = None) -> str:
        """Complete with automatic retry"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self._request_with_retry(messages)
    
    def _request_with_retry(self, messages: list) -> str:
        """Make request with retry logic"""
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return self._make_request(messages)
                
            except RateLimitError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = e.retry_after or self._calculate_delay(attempt)
                    print(f"[Retry] Rate limited. Waiting {wait:.1f}s...")
                    time.sleep(wait)
                    
            except ServerError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self._calculate_delay(attempt)
                    print(f"[Retry] Server error. Waiting {delay:.1f}s...")
                    time.sleep(delay)
                    
            except NetworkError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self._calculate_delay(attempt)
                    print(f"[Retry] Network error. Waiting {delay:.1f}s...")
                    time.sleep(delay)
        
        raise LLMError(f"Failed after {self.max_retries} attempts: {last_error}")
    
    def _make_request(self, messages: list) -> str:
        """Make single API request"""
        
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=self._build_headers(),
                json=self._build_payload(messages),
                timeout=self.timeout
            )
            
            # Handle status codes
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(f"Rate limited", retry_after=retry_after)
            
            if response.status_code >= 500:
                raise ServerError(f"Server error: {response.status_code}")
            
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
            
        except requests.exceptions.Timeout:
            raise NetworkError("Request timed out")
            
        except requests.exceptions.ConnectionError:
            raise NetworkError("Connection failed")
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with jitter"""
        delay = self.base_delay * (2 ** attempt)
        delay = min(delay, self.max_delay)
        # Add jitter: ±25%
        delay = delay * (1 + random.uniform(-0.25, 0.25))
        return delay
```

### 3. ReAct Engine Retry

```python
# agent_core/reasoning.py

class LLMReActEngine:
    """ReAct engine with retry on parse errors"""
    
    MAX_PARSE_RETRIES = 2
    
    def think(self) -> Decision:
        """Think with retry on parse errors"""
        
        for parse_attempt in range(self.MAX_PARSE_RETRIES):
            try:
                # Build prompt
                system_prompt = self._build_system_prompt()
                user_prompt = self._build_step_prompt()
                
                # Call LLM
                raw_response = self.llm.complete(user_prompt, system_prompt)
                
                # Parse response
                decision = self._parse_response(raw_response)
                
                # Validate
                return self._validate_decision(decision)
                
            except ParseError as e:
                if parse_attempt < self.MAX_PARSE_RETRIES - 1:
                    # Add error context to prompt
                    self._add_retry_hint(str(e))
                else:
                    # Max parse retries - continue with error observation
                    return Decision(
                        action=None,
                        content=None,
                        error=f"Failed to parse after {self.MAX_PARSE_RETRIES} attempts: {e}"
                    )
            
            except RateLimitError as e:
                # Wait and retry
                time.sleep(e.retry_after)
                continue
        
        raise LLMError("Max retries exceeded")
    
    def _add_retry_hint(self, error: str):
        """Add hint to help LLM produce valid output"""
        hint = f"""
        
        IMPORTANT: Previous output had an error: {error}
        Please output ONLY valid JSON in this exact format:
        {{"action": "tool_name", "action_input": {{"param": "value"}}}}
        OR:
        {{"action": "final", "content": "Your response here"}}
        """
        # This gets included in next prompt via observations
        self._pending_hint = hint
```

---

## Per-Layer Retry Configuration

### LLM API Calls

```python
# Most critical - API may rate limit
LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,          # Start with 2 seconds
    max_delay=60.0,         # Cap at 1 minute
    exponential_base=2.0,    # 2, 4, 8, 16...
    jitter=True,
    jitter_range=0.5,        # ±50% randomization
    retriable_exceptions=(
        RateLimitError,
        ServerError,
        NetworkError,
    )
)
```

### Tool Execution

```python
# Less critical - tools are fast
TOOL_RETRY_CONFIG = RetryConfig(
    max_attempts=1,          # No retry for tools
    retriable_exceptions=()  # Immediate failure
)
```

### File Operations

```python
# Files can be slow on network drives
FILE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=0.5,
    max_delay=5.0,
    retriable_exceptions=(
        TimeoutError,
        OSError,  # Temporary file locks
    )
)
```

---

## Custom Retry Strategies

### 1. Linear Backoff (Simple)

```python
def linear_backoff(attempt: int, base: float = 1.0) -> float:
    """Linear increase: 1, 2, 3, 4, ..."""
    return base * (attempt + 1)
```

### 2. Exponential Backoff (Standard)

```python
def exponential_backoff(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    """Exponential: 1, 2, 4, 8, 16... capped"""
    return min(base * (2 ** attempt), cap)
```

### 3. Exponential with Full Jitter

```python
def full_jitter(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    """Random between 0 and cap"""
    return random.uniform(0, min(cap, base * (2 ** attempt)))
```

### 4. Exponential with Equal Jitter

```python
def equal_jitter(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    """Delay capped at cap, random half"""
    temp = min(cap, base * (2 ** attempt))
    return temp / 2 + random.uniform(0, temp / 2)
```

### Comparison

| Strategy | Attempt 1 | Attempt 2 | Attempt 3 | Best For |
|----------|-----------|-----------|-----------|----------|
| Linear | 1s | 2s | 3s | Predictable |
| Exponential | 1s | 2s | 4s | General purpose |
| Full Jitter | 0-1s | 0-2s | 0-4s | Thundering herd |
| Equal Jitter | 0.5-1s | 1-2s | 2-4s | Balance |

**Recommendation:** Use **Exponential with Equal Jitter** for OpenRouter.

---

## Circuit Breaker Pattern

```python
# agent_core/circuit_breaker.py

import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """
    Prevent cascading failures by opening circuit after threshold.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute with circuit breaker protection"""
        
        # Check if circuit should transition
        self._check_state()
        
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit is open. Wait {self._time_until_recovery():.0f}s"
            )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _check_state(self):
        """Check if circuit should transition"""
        
        if self.state == CircuitState.OPEN:
            if self._time_since_failure() >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def _time_since_failure(self) -> float:
        if self.last_failure_time is None:
            return float('inf')
        return time.time() - self.last_failure_time
    
    def _time_until_recovery(self) -> float:
        return max(0, self.recovery_timeout - self._time_since_failure())


# Usage with LLM
llm_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=LLMError
)

def call_llm_with_circuit_breaker(prompt: str) -> str:
    return llm_circuit_breaker.call(llm.complete, prompt)
```

---

## Retry Logging

```python
# agent_core/retry.py

import logging

class RetryLogger:
    """Logging for retry operations"""
    
    def __init__(self):
        self.logger = logging.getLogger("retry")
    
    def log_retry(
        self,
        func_name: str,
        attempt: int,
        max_attempts: int,
        error: Exception,
        delay: float
    ):
        self.logger.warning(
            f"[{func_name}] Retry {attempt}/{max_attempts} "
            f"after {delay:.1f}s - {type(error).__name__}: {error}"
        )
    
    def log_exhausted(
        self,
        func_name: str,
        max_attempts: int,
        last_error: Exception
    ):
        self.logger.error(
            f"[{func_name}] All {max_attempts} attempts failed - "
            f"{type(last_error).__name__}: {last_error}"
        )
    
    def log_success(
        self,
        func_name: str,
        attempt: int,
        duration: float
    ):
        self.logger.debug(
            f"[{func_name}] Succeeded on attempt {attempt} "
            f"after {duration:.1f}s"
        )


# Usage with decorator
def on_retry_callback(error, attempt):
    logger.log_retry("llm.complete", attempt, 3, error, delay)

@with_retry(
    max_attempts=3,
    on_retry=on_retry_callback
)
def call_llm(prompt):
    return llm.complete(prompt)
```

---

## Retry Summary

| Component | Strategy | Max Retries | Base Delay |
|-----------|----------|-------------|------------|
| **LLM API** | Exponential + Jitter | 3 | 2s |
| **Rate Limit** | Respect Retry-After | - | From header |
| **Parse Error** | LLM retry | 2 | 0s (immediate) |
| **Tool Exec** | None | 0-1 | - |
| **Network** | Exponential | 3 | 1s |

### Best Practices

1. **Always cap maximum delay** — Prevents runaway waits
2. **Add jitter** — Prevents thundering herd
3. **Classify errors** — Retry only transient failures
4. **Log retries** — For debugging and monitoring
5. **Consider circuit breaker** — For sustained failures
6. **Respect Retry-After header** — For rate limits

---

## Configuration

```python
# Default retry settings
RETRY_CONFIG = {
    "llm": {
        "max_attempts": 3,
        "base_delay": 2.0,
        "max_delay": 60.0,
        "exponential_base": 2.0,
        "jitter": True,
        "jitter_range": 0.5
    },
    "parse": {
        "max_attempts": 2,
        "immediate": True
    },
    "tool": {
        "max_attempts": 1,
        "no_retry": True
    }
}
```

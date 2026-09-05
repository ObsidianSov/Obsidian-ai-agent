# Error Handling Strategy

## Overview

Errors in an LLM-driven agent can occur at multiple layers. We need a systematic approach to handle them gracefully.

---

## Error Taxonomy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ERROR TYPES                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  LAYER 1: LLM Layer                                                    │
│  ├── API connection failure                                            │
│  ├── Rate limiting (429)                                                │
│  ├── Invalid API key (401)                                              │
│  ├── Malformed response                                                 │
│  └── Content filtering                                                 │
│                                                                          │
│  LAYER 2: Parsing Layer                                                │
│  ├── Invalid JSON                                                       │
│  ├── Missing required fields                                            │
│  ├── Invalid action type                                                │
│  └── Malformed action_input                                            │
│                                                                          │
│  LAYER 3: Validation Layer                                             │
│  ├── Unknown tool requested                                            │
│  ├── Missing required arguments                                         │
│  └── Invalid argument types                                             │
│                                                                          │
│  LAYER 4: Execution Layer                                              │
│  ├── Tool not found                                                     │
│  ├── Tool execution failure                                             │
│  └── Tool timeout                                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       ERROR HANDLING FLOW                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Error Occurs                                                           │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ CLASSIFY ERROR                                                   │   │
│  │                                                                  │   │
│  │  Is it recoverable?                                             │   │
│  │       │                                                          │   │
│  │       ├── YES ──► Retry with backoff ──► Success? ──► Continue  │   │
│  │       │              │                      │                     │   │
│  │       │              └──► Fail? ──► Try alternative approach     │   │
│  │       │                                   │                       │   │
│  │       │                                   ▼                       │   │
│  │       │                            ┌─────────────┐               │   │
│  │       │                            │   Return   │               │   │
│  │       │                            │  error obs │               │   │
│  │       │                            └─────────────┘               │   │
│  │       │                                   │                       │   │
│  │       └── NO ────────────────────────────►│                       │   │
│  │                                                  │                   │
│  │                                                  ▼                   │
│  │                                           ┌─────────────┐           │
│  │                                           │  Return to │           │
│  │                                           │   user     │           │
│  │                                           └─────────────┘           │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Layer-by-Layer Handling

### Layer 1: LLM API Errors

```python
# agent_core/llm.py

class OpenRouterProvider:
    
    def complete(self, prompt: str, system_prompt: str = None) -> str:
        """Complete with comprehensive error handling"""
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.API_BASE}/chat/completions",
                    headers=self._build_headers(),
                    json=self._build_payload(prompt, system_prompt),
                    timeout=self.timeout
                )
                
                # Handle specific HTTP errors
                if response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid API key. Check OPENROUTER_API_KEY."
                    )
                
                if response.status_code == 403:
                    raise ForbiddenError(
                        "Access forbidden. Check API permissions."
                    )
                
                if response.status_code == 429:
                    # Rate limited - extract retry time
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise RateLimitError(
                        f"Rate limited. Retry after {retry_after}s.",
                        retry_after=retry_after
                    )
                
                if response.status_code >= 500:
                    raise ServerError(
                        f"OpenRouter server error: {response.status_code}"
                    )
                
                # Success
                response.raise_for_status()
                return self._parse_response(response)
                
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError) as e:
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue
                raise ConnectionError(f"Failed to connect: {e}")
        
        raise LLMError("Max retries exceeded")
```

### Layer 2: Parsing Errors

```python
# agent_core/reasoning.py

class LLMReActEngine:
    
    def _parse_response(self, raw: str) -> Decision:
        """Parse LLM response with error handling"""
        
        # Step 1: Extract JSON
        json_str = self._extract_json(raw)
        
        # Step 2: Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to fix common issues
            fixed = self._attempt_json_fix(raw)
            if fixed:
                data = fixed
            else:
                raise ParseError(f"Invalid JSON: {e}")
        
        # Step 3: Validate required fields
        if "action" not in data:
            raise ParseError("Missing 'action' field in response")
        
        # Step 4: Validate action type
        action = data["action"]
        valid_actions = {"final", "clarify", "tool", None}
        
        # Allow tool names as action
        if action not in valid_actions and not self._is_valid_tool(action):
            # Could be a tool name - that's OK
            pass
        
        # Step 5: Build decision based on action type
        return self._build_decision(data)
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown"""
        
        # Handle code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.rfind("```")
            return text[start:end].strip()
        
        if "```" in text:
            start = text.find("```") + 3
            end = text.rfind("```")
            return text[start:end].strip()
        
        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start != -1 and end > start:
            return text[start:end]
        
        return text  # Let json.loads handle it
    
    def _attempt_json_fix(self, text: str) -> Optional[dict]:
        """Attempt to fix malformed JSON"""
        
        # Fix single quotes
        try:
            # Replace single quotes with escaped double quotes in values
            import re
            fixed = re.sub(r"'([^']*)'", r'"\1"', text)
            return json.loads(fixed)
        except:
            pass
        
        # Fix trailing commas
        try:
            fixed = re.sub(r',\s*([}\]])', r'\1', text)
            return json.loads(fixed)
        except:
            pass
        
        return None
```

### Layer 3: Validation Errors

```python
# agent_core/reasoning.py

class ValidationError(Exception):
    """Invalid action or arguments"""
    def __init__(self, message: str, field: str = None):
        super().__init__(message)
        self.field = field

class LLMReActEngine:
    
    def _validate_decision(self, decision: Decision) -> Decision:
        """Validate decision before execution"""
        
        # Check if tool exists (if not final/clarify)
        if decision.action not in {"final", "clarify", None}:
            if not self._tool_exists(decision.action):
                raise ValidationError(
                    f"Unknown tool: '{decision.action}'",
                    field="action"
                )
        
        # Check required arguments for tool actions
        if decision.action not in {"final", "clarify"}:
            required = self._get_required_params(decision.action)
            provided = decision.action_input or {}
            
            missing = required - set(provided.keys())
            if missing:
                raise ValidationError(
                    f"Missing required arguments: {missing}",
                    field="action_input"
                )
        
        return decision
    
    def _tool_exists(self, tool_name: str) -> bool:
        """Check if tool exists in registry"""
        return tool_name in [t["name"] for t in self.available_tools]
```

### Layer 4: Execution Errors

```python
# agent_core/executor.py

class ToolExecutor:
    
    def execute(self, action: str, action_input: dict) -> str:
        """Execute tool with error handling"""
        
        # Step 1: Tool exists?
        if not self.can_execute(action):
            return json.dumps({
                "success": False,
                "error": f"Unknown tool: '{action}'",
                "available": self.get_available_tools()
            })
        
        # Step 2: Execute with timeout
        try:
            start_time = time.time()
            
            result = self.registry.execute(action, **action_input)
            
            elapsed = time.time() - start_time
            
            # Check for slow execution
            if elapsed > self.timeout:
                return json.dumps({
                    "success": True,
                    "warning": f"Slow execution: {elapsed:.1f}s",
                    "result": str(result)
                })
            
            return str(result)
            
        except TypeError as e:
            # Wrong arguments
            return json.dumps({
                "success": False,
                "error": f"Invalid arguments: {str(e)}",
                "hint": f"Check required parameters for '{action}'"
            })
            
        except FileNotFoundError as e:
            return json.dumps({
                "success": False,
                "error": f"File not found: {e.filename}"
            })
            
        except PermissionError as e:
            return json.dumps({
                "success": False,
                "error": f"Permission denied: {str(e)}"
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Execution error: {str(e)}",
                "type": type(e).__name__
            })
```

---

## Agent-Level Error Handling

```python
# agent_core/agent.py

class Agent:
    
    def run(self, task: str, context: dict = None) -> str:
        """Main entry point with comprehensive error handling"""
        
        try:
            # Initialize loop
            self.react.reset(task, self.tools.list_tools(), context or {})
            
            # Main loop
            while not self.react.is_complete() and self.react.step < self.config.max_steps:
                try:
                    # THINK
                    decision = self.react.think()
                    
                    # DECIDE
                    if decision.action == "final":
                        return decision.content
                    
                    if decision.action == "clarify":
                        return f"I need clarification: {decision.question}"
                    
                    # ACT
                    result = self.executor.execute(
                        decision.action,
                        decision.action_input
                    )
                    
                    # Check if execution failed
                    if self._is_error_result(result):
                        # Log error, continue loop
                        self._log_error(decision.action, result)
                    
                    # OBSERVE
                    self.react.add_observation(result)
                    
                except RateLimitError as e:
                    # Wait and retry
                    time.sleep(e.retry_after)
                    continue
                    
                except (ParseError, ValidationError) as e:
                    # Ask LLM to fix its output
                    error_observation = f"Parse error: {str(e)}. Please output valid JSON."
                    self.react.add_observation(error_observation)
                    continue
                    
                except AuthenticationError as e:
                    # Can't recover
                    return f"Configuration error: {str(e)}"
                    
                except LLMError as e:
                    # Try to recover or return error
                    if self._retry_llm():
                        continue
                    return f"LLM error: {str(e)}"
            
            # Max steps reached
            return self.react.get_summary()
            
        except KeyboardInterrupt:
            return "Interrupted by user."
            
        except Exception as e:
            # Unexpected error - log and return safe message
            return f"An unexpected error occurred: {str(e)}"
    
    def _is_error_result(self, result: str) -> bool:
        """Check if result is an error"""
        try:
            data = json.loads(result)
            return not data.get("success", True)
        except:
            return False
    
    def _log_error(self, action: str, result: str):
        """Log error for debugging"""
        print(f"[ERROR] Tool '{action}' failed: {result}")
```

---

## Retry Strategy

```python
# agent_core/retry.py

from functools import wraps
import time

class RetryStrategy:
    """Configurable retry logic"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retriable_exceptions: tuple = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retriable = retriable_exceptions
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_attempts):
                try:
                    return func(*args, **kwargs)
                except self.retriable as e:
                    last_exception = e
                    
                    if attempt < self.max_attempts - 1:
                        delay = min(
                            self.base_delay * (self.exponential_base ** attempt),
                            self.max_delay
                        )
                        time.sleep(delay)
                    else:
                        break
            
            raise last_exception
        
        return wrapper

# Usage
retry = RetryStrategy(max_attempts=3, base_delay=2.0)

class OpenRouterProvider:
    @retry
    def complete(self, prompt: str) -> str:
        # API call
        ...
```

---

## Error Messages to LLM

### Format for Error Observations

```python
# When tool fails, return structured error
observation = {
    "success": False,
    "error": "File not found",
    "details": "config.json does not exist in workspace",
    "recoverable": True,  # LLM can try different approach
    "hint": "Use list_files to see available files"
}

# When parsing fails
observation = {
    "success": False,
    "error": "Invalid JSON",
    "recoverable": True,
    "hint": "Output: {\"action\": \"tool_name\", \"action_input\": {...}}"
}

# When validation fails
observation = {
    "success": False,
    "error": "Missing required argument: 'path'",
    "recoverable": True,
    "hint": "Provide path and content for file_write"
}
```

### LLM Error Recovery Examples

| Error | Observation | LLM Recovery |
|-------|------------|--------------|
| File not found | `"Error: config.json not found"` | Use `list_files` first |
| Permission denied | `"Error: Permission denied"` | Try `command` tool |
| Invalid JSON | `"Parse error: missing 'action'"` | Output valid JSON |
| Rate limited | `"Rate limited, retry after 30s"` | Wait and retry |
| Unknown tool | `"Error: Unknown tool 'delete'"` | Use different tool |

---

## Timeout Handling

```python
# agent_core/executor.py

import signal
from functools import wraps

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Tool execution timed out")

class ToolExecutor:
    
    def __init__(self, tool_registry, timeout: int = 30):
        self.registry = tool_registry
        self.timeout = timeout
    
    def execute(self, action: str, action_input: dict) -> str:
        # Set timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout)
        
        try:
            result = self.registry.execute(action, **action_input)
            signal.alarm(0)  # Cancel alarm
            return str(result)
            
        except TimeoutError:
            return json.dumps({
                "success": False,
                "error": f"Tool execution timed out after {self.timeout}s",
                "recoverable": True
            })
            
        except Exception as e:
            signal.alarm(0)
            return json.dumps({
                "success": False,
                "error": str(e)
            })
```

---

## User-Facing Error Messages

```python
class ErrorFormatter:
    """Format errors for user display"""
    
    @staticmethod
    def format(error: Exception, include_details: bool = False) -> str:
        if isinstance(error, AuthenticationError):
            return (
                "🔑 API key issue. Please set your OPENROUTER_API_KEY:\n"
                "   export OPENROUTER_API_KEY=sk-or-..."
            )
        
        if isinstance(error, RateLimitError):
            return (
                "⏳ Rate limited. Please wait a moment and try again."
            )
        
        if isinstance(error, LLMError):
            return (
                "🤖 LLM service error. Please try again."
            )
        
        if isinstance(error, TimeoutError):
            return (
                "⏰ The request took too long. Try a simpler task."
            )
        
        if isinstance(error, NetworkError):
            return (
                "🌐 Network error. Check your connection."
            )
        
        # Generic fallback
        if include_details:
            return f"❌ Error: {str(error)}"
        else:
            return "❌ An error occurred. Please try again."
```

---

## Error Recovery Matrix

| Error Type | Recoverable | Strategy | Max Retries |
|------------|-------------|----------|-------------|
| Network timeout | ✅ | Exponential backoff | 3 |
| Rate limit (429) | ✅ | Wait + retry | 3 |
| Server error (5xx) | ✅ | Retry | 3 |
| Invalid API key | ❌ | Fail fast | 0 |
| Parse error | ✅ | Ask LLM to fix | 2 |
| Unknown tool | ✅ | Continue loop | - |
| Tool error | ✅ | Continue loop | - |
| Tool timeout | ✅ | Continue loop | - |

---

## Logging

```python
# agent_core/logging.py

import logging

class AgentLogger:
    def __init__(self, name: str = "agent"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "[%(levelname)s] %(message)s"
        ))
        self.logger.addHandler(ch)
    
    def log_think(self, step: int, prompt: str):
        self.logger.debug(f"Step {step} - Think:\n{prompt[:200]}...")
    
    def log_decide(self, step: int, decision: dict):
        self.logger.info(f"Step {step} - Decision: {decision.get('action')}")
    
    def log_execute(self, tool: str, args: dict):
        self.logger.debug(f"Execute: {tool}({args})")
    
    def log_observe(self, step: int, result: str):
        self.logger.debug(f"Step {step} - Observe: {result[:100]}...")
    
    def log_error(self, step: int, error: Exception):
        self.logger.error(f"Step {step} - Error: {error}")
```

---

## Summary

| Layer | Error | Handling |
|-------|-------|----------|
| **LLM** | Rate limit | Retry with backoff |
| **LLM** | Auth failure | Fail fast, user message |
| **LLM** | Network error | Retry 3x |
| **Parse** | Invalid JSON | Ask LLM to fix |
| **Validate** | Unknown tool | Return error obs, LLM adapts |
| **Execute** | Tool fails | Return error obs, LLM adapts |
| **Execute** | Timeout | Return error obs |

### Key Principles

1. **Don't expose raw errors to user** — Format them
2. **Make errors recoverable when possible** — LLM can adapt
3. **Fail fast on config issues** — No point retrying bad API key
4. **Log everything** — For debugging
5. **Timeout all operations** — Prevent hanging

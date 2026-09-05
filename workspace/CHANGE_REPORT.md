# Component Change Analysis

## Summary

| File | Status | Changes |
|------|--------|---------|
| `agent_core/agent.py` | **MODIFY** | Replace run() loop logic |
| `agent_core/reasoning.py` | **REPLACE** | Entire file |
| `agent_core/tools.py` | **CLEAN** | Remove 1 duplicate tool |
| `agent_core/memory.py` | **NO CHANGE** | — |
| `agent_core/cli.py` | **NO CHANGE** | — |
| `agent_core/llm.py` | **NEW** | OpenRouter provider |
| `agent_core/executor.py` | **NEW** | Tool execution wrapper |

---

## Detailed Change Specification

### 1. `agent_core/agent.py` — MODIFY

**Current:**
```python
def run(self, task: str, context: Dict = None) -> str:
    # ... gather context ...
    
    # Run ReAct reasoning loop
    result = self.react.think(
        task=task,
        available_tools=available_tools,
        context=merged_context
    )
    
    # Execute tools from trace (POST-hoc, not in loop)
    trace = self.react.get_trace()
    for step in trace:
        if step["action"] and step["state"] == "acting":
            tool_result = self.tools.execute(...)
            step["observation"] = tool_result
    
    # Get final result
    final_step = [s for s in trace if s.get("is_final")]
    response = final_step[0].get("thought", result)
```

**Problems:**
- `react.think()` returns once, tools execute AFTER
- Tool results never feed back into reasoning
- No true iteration loop

**New:**
```python
def run(self, task: str, context: Dict = None) -> str:
    # ... gather context ...
    
    # Initialize reasoning engine
    self.react.reset(task, available_tools, merged_context)
    
    # TRUE ReAct loop
    while not self.react.is_complete() and self.react.step < self.config.max_steps:
        # THINK: Get next action from LLM
        decision = self.react.think()
        
        if decision.action == "final":
            return decision.content
        
        if decision.action == "clarify":
            return f"I need clarification: {decision.question}"
        
        # ACT: Execute tool
        observation = self.executor.execute(
            decision.action,
            decision.action_input
        )
        
        # OBSERVE: Feed back to reasoning
        self.react.add_observation(observation)
    
    # Max steps reached
    return self.react.get_summary()
```

**Changes Summary:**
| Component | Change |
|-----------|--------|
| `__init__` | Add `executor` instance, pass `llm_provider` to engine |
| `run()` | Replace one-shot think + post-execute with true loop |
| Imports | Add `from agent_core.executor import ToolExecutor`, `from agent_core.llm import OpenRouterProvider` |

---

### 2. `agent_core/reasoning.py` — REPLACE

**Current (rule-based):**
```python
def _decide_action(self, task: str, context: Dict, step: int) -> Dict:
    task_lower = task.lower()
    if "write" in task_lower and "file" in task_lower:
        return {"type": "tool", "tool": "file_write", ...}
    # ... 50+ lines of if/elif pattern matching
```

**Problems:**
- Hardcoded rules, no intelligence
- Can't handle complex tasks
- No LLM integration

**New Structure:**
```python
"""
LLM-ReAct Engine - Reasoning + Acting with OpenRouter
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import os

# Keep existing imports for compatibility
from agent_core.memory import MemorySystem
from agent_core.tools import ToolRegistry

@dataclass
class Decision:
    """Represents LLM's decision after thinking"""
    action: str                           # "tool_name" | "final" | "clarify"
    action_input: Optional[Dict] = None  # Tool arguments
    content: Optional[str] = None         # For "final"
    question: Optional[str] = None        # For "clarify"
    raw_thought: Optional[str] = None     # LLM's reasoning text

class LLMReActEngine:
    """
    LLM-driven ReAct implementation.
    Replaces rule-based _decide_action().
    """
    
    def __init__(
        self,
        llm_provider,           # Injected, not created here
        max_steps: int = 10,
        max_retries: int = 3
    ):
        self.llm = llm_provider
        self.max_steps = max_steps
        self.max_retries = max_retries
        
        # State
        self.task: str = ""
        self.available_tools: List[Dict] = []
        self.context: Dict = {}
        self.step: int = 0
        self.observations: List[Dict] = []
        self.thought_history: List[Dict] = []
        self._is_complete: bool = False
    
    def reset(self, task: str, tools: List[Dict], context: Dict):
        """Initialize or reset for new task"""
        self.task = task
        self.available_tools = tools
        self.context = context
        self.step = 0
        self.observations = []
        self.thought_history = []
        self._is_complete = False
    
    def think(self) -> Decision:
        """
        Think about next action.
        Called each iteration of the ReAct loop.
        """
        self.step += 1
        
        # Build prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_step_prompt()
        
        # Call LLM with retry
        raw_response = self._call_llm(system_prompt, user_prompt)
        
        # Parse response
        decision = self._parse_response(raw_response)
        
        # Record thought
        self.thought_history.append({
            "step": self.step,
            "action": decision.action,
            "thought": decision.raw_thought
        })
        
        # Check if done
        if decision.action == "final":
            self._is_complete = True
        
        return decision
    
    def add_observation(self, observation: str):
        """Add tool result to context for next iteration"""
        last_action = self.thought_history[-1] if self.thought_history else {}
        
        self.observations.append({
            "step": self.step,
            "action": last_action.get("action"),
            "result": observation
        })
    
    def is_complete(self) -> bool:
        """Check if reasoning is done"""
        return self._is_complete
    
    def get_summary(self) -> str:
        """Get summary when max steps reached"""
        summary = f"Completed {len(self.observations)} steps. Summary:\n"
        for obs in self.observations:
            summary += f"- Step {obs['step']}: {obs['action']} → {obs['result'][:100]}\n"
        summary += "\nNote: Reached maximum steps limit."
        return summary
    
    # ─────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with tools and instructions"""
        tools_desc = self._format_tools_description()
        
        return f"""You are Obsidian, an AI agent that reasons step-by-step.

You have access to these tools:
{tools_desc}

MEMORY CONTEXT:
{self._format_context()}

INSTRUCTIONS:
1. Think about what the user wants
2. If a tool is needed, select ONE and provide arguments
3. If task is complete, respond with final answer
4. Output ONLY valid JSON

Output format for tool action:
{{"action": "tool_name", "action_input": {{"param": "value"}}}}

Output format when done:
{{"action": "final", "content": "Your response to the user"}}

Output format to ask clarification:
{{"action": "clarify", "question": "What do you mean?"}}
"""
    
    def _build_step_prompt(self) -> str:
        """Build prompt for current step"""
        prompt = f"""Task: {self.task}

Step {self.step} of {self.max_steps}."""
        
        if self.observations:
            prompt += "\n\nPrevious observations:"
            for obs in self.observations:
                prompt += f"\n- Step {obs['step']}: {obs['action']} → {obs['result'][:200]}"
        
        prompt += "\n\nWhat should I do next? Output JSON only."
        return prompt
    
    def _format_tools_description(self) -> str:
        """Format tools for prompt"""
        lines = []
        for tool in self.available_tools:
            name = tool["name"]
            desc = tool.get("description", "")
            params = tool.get("params", {})
            
            param_str = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in params.items())
            lines.append(f"- {name}({param_str}): {desc}")
        
        return "\n".join(lines)
    
    def _format_context(self) -> str:
        """Format memory context"""
        parts = []
        
        if self.context.get("recent_conversation"):
            parts.append(f"Recent: {self.context['recent_conversation'][-2:]}")
        
        if self.context.get("user_preferences"):
            parts.append(f"Preferences: {self.context['user_preferences']}")
        
        return "\n".join(parts) or "No context available"
    
    def _call_llm(self, system: str, user: str) -> str:
        """Call LLM with retry logic"""
        for attempt in range(self.max_retries):
            try:
                return self.llm.complete(user, system_prompt=system)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise LLMError(f"Failed after {self.max_retries} attempts: {e}")
    
    def _parse_response(self, raw: str) -> Decision:
        """Parse LLM JSON response"""
        # Try to extract JSON
        json_str = self._extract_json(raw)
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to fix single quotes
            try:
                data = json.loads(json_str.replace("'", '"'))
            except:
                raise ParseError(f"Invalid JSON: {raw[:200]}")
        
        # Validate and extract
        action = data.get("action", "")
        
        if action == "final":
            return Decision(
                action="final",
                content=data.get("content", ""),
                raw_thought=raw
            )
        
        if action == "clarify":
            return Decision(
                action="clarify",
                question=data.get("question", ""),
                raw_thought=raw
            )
        
        return Decision(
            action=action,
            action_input=data.get("action_input", {}),
            raw_thought=raw
        )
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response"""
        text = text.strip()
        
        # Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        
        # Try to find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start != -1 and end > start:
            return text[start:end]
        
        return text


class LLMError(Exception):
    """LLM-related errors"""
    pass

class ParseError(Exception):
    """Response parsing errors"""
    pass
```

**Changes Summary:**
| Component | Change |
|-----------|--------|
| Entire file | **REPLACE** - Remove `_decide_action()`, `_reflect()`, pattern matching |
| `Decision` class | **NEW** - Structured action output |
| `LLMReActEngine` class | **NEW** - LLM-driven loop |
| `think()` | **NEW** - Build prompt, call LLM, parse |
| `add_observation()` | **NEW** - Feed results back |
| `_build_system_prompt()` | **NEW** - Tool descriptions + instructions |
| `_build_step_prompt()` | **NEW** - Task + observations |
| `_call_llm()` | **NEW** - Retry logic |
| `_parse_response()` | **NEW** - JSON extraction + validation |

---

### 3. `agent_core/tools.py` — CLEAN

**Current (has duplicate):**
```python
class FileReadTool(Tool):
    def __init__(self):
        super().__init__(
            name="file_read",
            ...
        )

class ReadFileTool(Tool):
    """Workspace-relative file read"""
    def __init__(self):
        super().__init__(
            name="read_workspace_file",
            ...
        )
```

**Problem:** Both read files. Keep one.

**New:**
```python
# REMOVE FileReadTool entirely

class ReadFileTool(Tool):
    """Read a file from workspace"""
    def __init__(self):
        super().__init__(
            name="read_workspace_file",  # Keep this one, more descriptive
            description="Read content from a workspace file",
            func=self._read,
            input_schema={"path": {"type": "string", "description": "Workspace-relative file path"}}
        )
    
    def _read(self, path: str) -> str:
        workspace = os.environ.get('OBSIDIAN_WORKSPACE', os.getcwd())
        full_path = os.path.join(workspace, path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"
```

**Changes Summary:**
| Component | Change |
|-----------|--------|
| `FileReadTool` class | **REMOVE** - Duplicate of `ReadFileTool` |
| `_register_default_tools()` | **MODIFY** - Don't register `FileReadTool` |
| `ReadFileTool` | **KEEP** - Primary file reader |

---

### 4. `agent_core/memory.py` — NO CHANGE

**Status:** ✅ No modifications needed.

Existing interfaces are sufficient:
- `get_system_context()` → Returns dict for prompts
- `remember()` / `recall()` → Existing API

---

### 5. `agent_core/cli.py` — NO CHANGE

**Status:** ✅ No modifications needed.

The CLI calls `agent.run()` which has the same signature. The loop change is internal.

---

### 6. `agent_core/llm.py` — NEW

```python
"""
OpenRouter LLM Provider
"""

import os
import time
import requests
from typing import Optional, List, Dict

class OpenRouterProvider:
    """
    LLM provider using OpenRouter API.
    """
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "anthropic/claude-3-haiku",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 60,
        max_retries: int = 3
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. "
                "Set OPENROUTER_API_KEY environment variable."
            )
        
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.api_base = "https://openrouter.ai/api/v1"
    
    def complete(
        self,
        prompt: str,
        system_prompt: str = None
    ) -> str:
        """
        Send prompt to OpenRouter and get completion.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            
        Returns:
            LLM response text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return self.complete_messages(messages)
    
    def complete_messages(
        self,
        messages: List[Dict]
    ) -> str:
        """
        Send message history to OpenRouter.
        
        Args:
            messages: List of {"role": "...", "content": "..."}
            
        Returns:
            LLM response text
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://obsidian-ai.local",
            "X-Title": "Obsidian AI Agent"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                # Handle rate limits
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.max_retries - 1:
                        time.sleep(retry_after)
                        continue
                
                response.raise_for_status()
                data = response.json()
                
                return data["choices"][0]["message"]["content"]
                
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    raise LLMError(f"API request failed: {e}")
        
        raise LLMError(f"Failed after {self.max_retries} attempts: {last_error}")


class LLMError(Exception):
    """LLM API errors"""
    pass
```

---

### 7. `agent_core/executor.py` — NEW

```python
"""
Tool Executor - Safe tool execution wrapper
"""

from typing import Dict, Any, List
import time

class ToolExecutor:
    """
    Executes tools chosen by LLM with error handling.
    """
    
    def __init__(
        self,
        tool_registry,
        timeout: int = 30
    ):
        self.registry = tool_registry
        self.timeout = timeout
    
    def execute(
        self,
        action: str,
        action_input: Dict[str, Any]
    ) -> str:
        """
        Execute a tool and return observation string.
        
        Args:
            action: Tool name
            action_input: Tool arguments
            
        Returns:
            Observation string (success or error)
        """
        # Validate tool exists
        available = [t["name"] for t in self.registry.list_tools()]
        if action not in available:
            return f"Error: Unknown tool '{action}'. Available: {available}"
        
        # Execute with timeout (basic implementation)
        try:
            start_time = time.time()
            
            result = self.registry.execute(action, **action_input)
            
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                return f"Warning: Tool took {elapsed:.1f}s (exceeds {self.timeout}s limit)"
            
            return str(result)
            
        except TypeError as e:
            # Wrong arguments
            return f"Error: Invalid arguments for '{action}': {str(e)}"
            
        except Exception as e:
            # Any other error
            return f"Error executing {action}: {str(e)}"
    
    def can_execute(self, action: str) -> bool:
        """Check if tool exists"""
        return action in [t["name"] for t in self.registry.list_tools()]
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return [t["name"] for t in self.registry.list_tools()]
```

---

## Change Summary Table

| File | Lines Changed | Type | Impact |
|------|--------------|------|--------|
| `agent_core/agent.py` | ~40 lines | MODIFY | Core loop logic |
| `agent_core/reasoning.py` | ~280 lines | REPLACE | All reasoning logic |
| `agent_core/tools.py` | ~10 lines | CLEAN | Remove 1 class |
| `agent_core/memory.py` | 0 lines | NONE | — |
| `agent_core/cli.py` | 0 lines | NONE | — |
| `agent_core/llm.py` | ~120 lines | NEW | API integration |
| `agent_core/executor.py` | ~60 lines | NEW | Tool wrapper |

**Total:** ~510 lines changed, ~0 lines unchanged that shouldn't be.

---

## Compatibility Matrix

| Existing Code | Impact | Action |
|---------------|--------|--------|
| `from agent_core.reasoning import ReActEngine` | BREAKING | Update to `LLMReActEngine` |
| `agent.think()` signature | BREAKING | Now `think()` + `add_observation()` |
| `agent.react.get_trace()` | BREAKING | Remove or adapt |
| `agent.run()` signature | COMPAT | Same signature |
| `create_agent()` | COMPAT | Factory function updates internally |
| `test_agent.py` | NEEDS UPDATE | Test new loop behavior |

---

## Migration Steps

1. **Create `llm.py`** — OpenRouter provider (standalone, test first)
2. **Create `executor.py`** — Tool wrapper (standalone, test with existing tools)
3. **Replace `reasoning.py`** — New LLMReActEngine (import from llm)
4. **Update `agent.py`** — Wire new components
5. **Clean `tools.py`** — Remove duplicate
6. **Update tests** — `test_agent.py` needs rework

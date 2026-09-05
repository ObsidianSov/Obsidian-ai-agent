# Architecture Design: LLM-Driven ReAct Agent

## Overview

Replace the current rule-based ReAct reasoning engine with a real LLM-driven agent loop using OpenRouter, integrated directly into the existing `agent_core` structure.

---

## Current State

```
agent_core/
├── agent.py        # Orchestrator (keep, update to use new engine)
├── reasoning.py    # ⚠️ RULE-BASED - REPLACE
├── tools.py        # Unchanged
├── memory.py       # Unchanged
└── cli.py          # Unchanged
```

---

## Target Structure

```
agent_core/
├── agent.py        # UPDATED - uses new engine
├── reasoning.py    # REPLACED - LLM-driven ReAct
├── executor.py     # NEW - tool execution with error handling
├── llm.py          # NEW - OpenRouter provider
├── tools.py        # Unchanged
├── memory.py       # Unchanged
└── cli.py          # Unchanged
```

---

## Component Specifications

### 1. `llm.py` — OpenRouter Provider

**Responsibilities:**
- Make API calls to OpenRouter
- Handle retries with exponential backoff
- Manage token limits and timeouts

**Key Class:**
```python
class OpenRouterProvider:
    def __init__(
        self,
        api_key: str = None,
        model: str = "anthropic/claude-3-haiku",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 60
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def complete(self, prompt: str, system_prompt: str = None) -> str:
        """Send prompt to OpenRouter, return response text."""

    def complete_messages(self, messages: List[Dict]) -> str:
        """Send message history to OpenRouter."""

    def _retry_with_backoff(self, func) -> Any:
        """Internal retry logic for rate limits."""
```

**Configuration (environment variables):**
```bash
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-3-haiku  # optional override
```

---

### 2. `reasoning.py` — LLM-Driven ReAct Engine

**Responsibilities:**
- Build prompts with tools, memory context, and task
- Call LLM each iteration
- Parse LLM response to extract actions
- Manage the reasoning loop

**Key Class:**
```python
class LLMReActEngine:
    """
    LLM-driven ReAct implementation.
    Replaces the old _decide_action() pattern matching.
    """

    # State tracking (reuse existing Thought dataclass)
    # state: ThoughtState enum
    # thought_history: List[Thought]

    def think(self, task: str, available_tools: List[Dict], context: Dict) -> str:
        """
        Main reasoning loop:
        1. Build system prompt (tools + memory)
        2. Loop up to max_steps:
           a. Build task prompt with previous observations
           b. Call LLM
           c. Parse response
           d. If action=tool → return for execution
           e. If action=final → return response
        3. Return summary if max_steps reached
        """

    def _build_system_prompt(self, tools: List[Dict], context: Dict) -> str:
        """Construct the system prompt with tools and context."""

    def _build_step_prompt(self, task: str, observations: List[Dict], step: int) -> str:
        """Construct prompt for each ReAct iteration."""

    def _parse_response(self, raw: str) -> Dict:
        """
        Parse LLM response to extract action.
        Expects JSON: {"action": "tool_name", "action_input": {...}}
                  or: {"action": "final", "content": "..."}
        """
```

**Prompt Structure:**
```
=== SYSTEM PROMPT ===
You are Obsidian, an AI agent that reasons step-by-step.

AVAILABLE TOOLS:
- file_write: Write content to a file. Params: path (string), content (string)
- read_workspace_file: Read a file from workspace. Params: path (string)
- command: Execute terminal command. Params: command (string)
- list_files: List directory contents. Params: path (string)
- ...

MEMORY CONTEXT:
Recent facts: [from memory system]
User preferences: [from memory system]

INSTRUCTIONS:
1. Think about what the user wants
2. Select ONE tool to use, or respond with final answer
3. Output ONLY valid JSON: {"action": "...", "action_input": {...}}
4. When task is complete, output: {"action": "final", "content": "..."}

=== TASK PROMPT ===
Task: {user_task}

Previous observations:
- Step 1: tool_name returned: {result}
- Step 2: tool_name returned: {result}

Step {n} of {max_steps}. What do you do next?
Output JSON only.
```

**Response Parsing:**
```python
def _parse_response(self, raw: str) -> Dict:
    # Try to extract JSON from response
    # Handle markdown code blocks
    # Validate action type and required fields
    # Return structured dict or raise on invalid
```

---

### 3. `executor.py` — Tool Executor

**Responsibilities:**
- Execute tools chosen by LLM
- Handle errors gracefully
- Return observation strings for LLM context

**Key Class:**
```python
class ToolExecutor:
    """Executes LLM-decided tools safely."""

    def __init__(self, tool_registry: ToolRegistry, timeout: int = 30):
        self.registry = tool_registry
        self.timeout = timeout

    def execute(self, action: str, action_input: Dict) -> str:
        """
        Execute a tool and return observation string.
        Handles errors, timeouts, and invalid tools.
        """
        try:
            result = self.registry.execute(action, **action_input)
            return str(result)
        except ValueError as e:
            return f"Error: Unknown tool '{action}'"
        except Exception as e:
            return f"Error executing {action}: {str(e)}"

    def can_execute(self, action: str) -> bool:
        """Check if tool exists."""
        return action in [t["name"] for t in self.registry.list_tools()]
```

---

### 4. `agent.py` — Updated Orchestrator

**Changes:**
- Replace `from reasoning import ReActEngine` with `from reasoning import LLMReActEngine`
- Add `ToolExecutor` integration
- Add `OpenRouterProvider` initialization
- Handle the observe-think-act loop

**Key Changes:**
```python
from agent_core.reasoning import LLMReActEngine
from agent_core.executor import ToolExecutor
from agent_core.llm import OpenRouterProvider

class Agent:
    def __init__(self, config: AgentConfig = None, workspace: str = "."):
        # ... existing init ...
        
        # NEW: LLM components
        self.llm = OpenRouterProvider()
        self.react = LLMReActEngine(
            llm_provider=self.llm,
            max_steps=self.config.max_steps
        )
        self.executor = ToolExecutor(self.tools)

    def run(self, task: str, context: Dict = None) -> str:
        """Main entry point - process task through LLM ReAct loop."""
        
        # ... existing context gathering ...
        
        # Run LLM reasoning loop
        while self.react.current_step < self.react.max_steps:
            # Get next action from LLM
            decision = self.react.decide_next(
                task=task,
                available_tools=available_tools,
                context=merged_context
            )
            
            if decision["action"] == "final":
                return decision["content"]
            
            if decision["action"] == "clarify":
                return f"I need clarification: {decision['question']}"
            
            # Execute tool
            observation = self.executor.execute(
                decision["action"],
                decision["action_input"]
            )
            
            # Feed result back to reasoning
            self.react.add_observation(decision["step"], observation)
            
            # Update context for next iteration
            merged_context[f"obs_{decision['step']}"] = observation
        
        # Max steps reached
        return self.react.get_summary()
```

---

## Data Flow

```
User Task
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Agent.run()                                                 │
├─────────────────────────────────────────────────────────────┤
│  1. Get memory context                                      │
│  2. Get available tools                                     │
│  3. Call LLMReActEngine.think()                           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ LLMReActEngine.think()                                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ STEP 1: Build Prompt                                   │  │
│  │   - System: tools, memory, instructions               │  │
│  │   - Task: current task + previous observations         │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ STEP 2: Call LLM (OpenRouter)                         │  │
│  │   - POST /chat/completions                           │  │
│  │   - Retry with backoff if rate limited               │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ STEP 3: Parse Response                                │  │
│  │   - Extract JSON from response                        │  │
│  │   - Validate action and parameters                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ STEP 4: Decision                                      │  │
│  │                                                        │  │
│  │   action = "tool" ──────────► return (action, input) │  │
│  │   action = "final" ─────────► return final response   │  │
│  │   action = "clarify" ───────► return clarification   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Agent.run() continues...                                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  For tool actions:                                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ ToolExecutor.execute(action, action_input)            │  │
│  │   → Returns observation string                        │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ LLMReActEngine.add_observation(step, observation)    │  │
│  │   → Loop continues to next iteration                  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: LLM Provider
- Create `llm.py` with `OpenRouterProvider` class
- Add API key validation
- Implement `complete()` method with requests
- Add retry logic for rate limits

### Phase 2: ReAct Engine
- Create `reasoning.py` (replace existing)
- Implement `LLMReActEngine` class
- Build prompt templates in `_build_system_prompt()` and `_build_step_prompt()`
- Implement `_parse_response()` for JSON extraction

### Phase 3: Executor
- Create `executor.py` with `ToolExecutor` class
- Wrap `ToolRegistry.execute()` with error handling
- Add timeout support

### Phase 4: Integration
- Update `agent.py` to wire everything together
- Test full loop with real API calls
- Verify backward compatibility

---

## Configuration

### Environment Variables
```bash
# Required
OPENROUTER_API_KEY=sk-or-...

# Optional
OPENROUTER_MODEL=anthropic/claude-3-haiku
OPENROUTER_TIMEOUT=60
```

### AgentConfig Extension
```python
@dataclass
class AgentConfig:
    # ... existing fields ...
    
    # NEW: LLM settings
    llm_model: str = "anthropic/claude-3-haiku"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024
```

---

## Backward Compatibility

- **Same public API**: `create_agent()` and `agent.run()` unchanged
- **Existing tests**: `test_agent.py` should pass with minimal changes
- **Legacy engine**: Can keep old `reasoning.py` as `reasoning_legacy.py` for fallback

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No API key | Raise `ConfigurationError` with helpful message |
| API rate limit | Retry 3x with exponential backoff |
| Invalid JSON from LLM | Ask LLM to retry with format hint |
| Unknown tool | Return error observation, continue loop |
| Tool execution fails | Return error observation, LLM decides next step |
| Max steps reached | Return summary of what was done |

---

## Security

1. API key via environment variable only
2. Tool execution timeout (30s default)
3. No shell command injection (tools are explicit)
4. Token limits prevent runaway responses

---

## Ready to Implement

The architecture is designed to:
- ✅ Use existing `agent_core` structure
- ✅ Keep `tools.py` and `memory.py` unchanged
- ✅ Replace only `reasoning.py`
- ✅ Add new `llm.py` and `executor.py`
- ✅ Maintain backward-compatible API

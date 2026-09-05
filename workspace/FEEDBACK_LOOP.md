# How Tool Results Feed Back to the LLM

## The Core Concept

The ReAct loop requires **context continuity** — each iteration must know what happened in previous iterations. This is achieved by feeding observations back into the LLM's context.

---

## Two Approaches

### Approach 1: Single-Prompt (Used in Basic Implementation)

Each LLM call is independent. Observations are embedded in the prompt.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  PROMPT (Step 1)                                               │
│  ──────────────────                                             │
│  Task: Write hello to test.txt                                 │
│  Step 1 of 10.                                                 │
│  Previous observations: None                                    │
│                                                                 │
│  RESPONSE                                                       │
│  {"action": "file_write", "action_input": {...}}              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  PROMPT (Step 2)                                               │
│  ──────────────────                                             │
│  Task: Write hello to test.txt                                 │
│  Step 2 of 10.                                                 │
│  Previous observations:                                        │
│  - Step 1: file_write → "Successfully wrote to test.txt"      │
│                                                                 │
│  RESPONSE                                                       │
│  {"action": "final", "content": "Done!"}                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Approach 2: Message History (More Powerful)

Maintains full conversation history. Observations become user messages.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  MESSAGES (Step 1)                                             │
│  ───────────────                                                │
│  [System] You are Obsidian...                                   │
│  [User] Task: Write hello to test.txt                          │
│  [User] Step 1. What should I do?                              │
│                                                                 │
│  [Assistant] {"action": "file_write", ...}                     │
│                                                                 │
│  [User] Observation: Successfully wrote to test.txt           │
│  [User] Step 2. What should I do next?                        │
│                                                                 │
│  [Assistant] {"action": "final", "content": "Done!"}          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

We'll use **Approach 1** (single-prompt) for simplicity and cost efficiency.

---

## Data Flow for Feedback

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           STEP N COMPLETE                               │
│                                                                          │
│  Tool executed → Observation captured                                   │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Observation Record                                               │   │
│  │                                                                 │   │
│  │ {                                                               │   │
│  │   "step": 1,                                                   │   │
│  │   "action": "file_write",                                       │   │
│  │   "input": {"path": "test.txt", "content": "hello"},          │   │
│  │   "result": "Successfully wrote to test.txt"                  │   │
│  │ }                                                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Store in observations list                                       │   │
│  │                                                                 │   │
│  │ self.observations = [                                           │   │
│  │   {step: 1, action: "file_write", result: "Success..."},        │   │
│  │ ]  # Grows each iteration                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                    │                                                    │
└────────────────────┼────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           STEP N + 1                                   │
│                                                                          │
│  Build prompt with observations:                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                                                                 │   │
│  │ Task: {task}                                                   │   │
│  │                                                                 │   │
│  │ Step {n + 1} of {max_steps}.                                   │   │
│  │                                                                 │   │
│  │ Previous observations:                                          │   │
│  │ - Step 1: file_write → Successfully wrote to test.txt          │   │
│  │ - Step 2: command → Listed 5 files                            │   │
│  │ - ...                                                          │   │
│  │                                                                 │   │
│  │ What should I do next?                                         │   │
│  │                                                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Call LLM → Get next decision                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### 1. Storing Observations

```python
class LLMReActEngine:
    def __init__(self, ...):
        self.observations: List[Dict] = []
    
    def add_observation(self, observation: str):
        """Called after tool execution"""
        last_thought = self.thought_history[-1] if self.thought_history else {}
        
        self.observations.append({
            "step": self.step,
            "action": last_thought.get("action"),
            "input": last_thought.get("input"),
            "result": observation
        })
```

### 2. Formatting in Prompt

```python
def _build_step_prompt(self) -> str:
    prompt = f"""Task: {self.task}

Step {self.step} of {self.max_steps}."""
    
    if self.observations:
        prompt += "\n\nPrevious observations:"
        for obs in self.observations:
            # Truncate long results
            result = obs["result"]
            if len(result) > 200:
                result = result[:200] + "..."
            
            prompt += f"\n- Step {obs['step']}: {obs['action']} → {result}"
    
    prompt += "\n\nWhat should I do next? Output JSON only."
    return prompt
```

### 3. Example Prompt with Observations

```
Task: Analyze the files in this directory and count Python files

Step 2 of 10.

Previous observations:
- Step 1: list_files → agent_core, hello.py, index.html, script.js, 
  styles.css, test.txt, test_agent.py, requirements.txt

What should I do next? Output JSON only.
```

---

## Observation Content Guidelines

### What to Include

```python
# ✅ Good - informative, actionable
observation = "Successfully wrote to test.txt (12 bytes)"

# ✅ Good - error with context
observation = "Error: File 'missing.txt' not found in workspace"

# ✅ Good - listing results
observation = "Found 3 Python files: test_agent.py, hello.py, agent_core/agent.py"
```

### What to Exclude

```python
# ❌ Bad - too verbose (floods context)
observation = "Opening file at path /full/path/to/workspace/test.txt using open()..." \
             "Reading 1024 bytes... closing file... done"

# ❌ Bad - missing context
observation = "Error"

# ❌ Bad - internal details
observation = "ToolExecuteError in line 42 of executor.py"
```

---

## Context Window Management

As iterations grow, observations accumulate. Manage this:

### Strategy 1: Truncate

```python
def _format_observations(self) -> str:
    lines = []
    for obs in self.observations:
        result = obs["result"]
        # Truncate each observation to 200 chars
        if len(result) > 200:
            result = result[:200] + "..."
        lines.append(f"Step {obs['step']}: {obs['action']} → {result}")
    
    # If too many, keep only recent
    if len(lines) > 10:
        lines = ["... (earlier steps omitted) ..."] + lines[-10:]
    
    return "\n".join(lines)
```

### Strategy 2: Summarize

```python
def _format_observations(self) -> str:
    if len(self.observations) > 5:
        # Summarize old observations
        summary = f"Summarized {len(self.observations) - 3} completed steps. "
        summary += f"Last result: {self.observations[-1]['result'][:100]}"
        return summary
    
    # Full list for recent
    ...
```

---

## Complete Example: Multi-Step Task

### Task: "Create a Python file that prints hello, run it, show me the output"

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Prompt:                                                             │
│   Task: Create a Python file that prints hello, run it...            │
│   Step 1 of 10.                                                    │
│   Previous observations: None                                        │
│                                                                      │
│ LLM Decision:                                                       │
│   {"action": "file_write", "action_input": {                        │
│     "path": "hello.py",                                            │
│     "content": "print('hello')"                                    │
│   }}                                                                │
│                                                                      │
│ Tool Result:                                                        │
│   "Successfully wrote to hello.py"                                  │
│                                                                      │
│ Observation stored:                                                 │
│   {step: 1, action: "file_write", result: "Successfully wrote..."}  │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Prompt:                                                             │
│   Task: Create a Python file that prints hello, run it...            │
│   Step 2 of 10.                                                     │
│   Previous observations:                                            │
│   - Step 1: file_write → Successfully wrote to hello.py             │
│                                                                      │
│ LLM Decision:                                                       │
│   {"action": "command", "action_input": {                           │
│     "command": "python hello.py"                                    │
│   }}                                                                │
│                                                                      │
│ Tool Result:                                                        │
│   "Exit: 0\nSTDOUT:\nhello\nSTDERR:\n"                            │
│                                                                      │
│ Observation stored:                                                 │
│   {step: 2, action: "command", result: "Exit: 0\nSTDOUT:\nhello"}  │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Prompt:                                                             │
│   Task: Create a Python file that prints hello, run it...            │
│   Step 3 of 10.                                                     │
│   Previous observations:                                            │
│   - Step 1: file_write → Successfully wrote to hello.py             │
│   - Step 2: command → Exit: 0\nSTDOUT:\nhello                      │
│                                                                      │
│ LLM Decision:                                                       │
│   {"action": "final", "content": "Done! Created hello.py which      │
│     prints 'hello'. The output was confirmed when running the file."}│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Error Feedback Example

### Task: "Read a file that doesn't exist"

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Prompt:                                                             │
│   Task: Read a file that doesn't exist                              │
│   Step 1 of 10.                                                    │
│   Previous observations: None                                        │
│                                                                      │
│ LLM Decision:                                                       │
│   {"action": "read_workspace_file", "action_input": {               │
│     "path": "nonexistent.txt"                                       │
│   }}                                                                │
│                                                                      │
│ Tool Result:                                                        │
│   "Error reading file: [Errno 2] No such file: 'nonexistent.txt'"   │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Prompt:                                                             │
│   Task: Read a file that doesn't exist                              │
│   Step 2 of 10.                                                    │
│   Previous observations:                                            │
│   - Step 1: read_workspace_file → Error reading file: No such file   │
│                                                                      │
│ LLM Decision (recovery):                                            │
│   {"action": "final", "content": "I couldn't find 'nonexistent.txt'. │
│     Would you like me to create it or check a different filename?"} │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

| Aspect | Implementation |
|--------|----------------|
| **Storage** | `self.observations` list grows each iteration |
| **Format** | `{step, action, result}` dictionary |
| **Embedding** | Included in next prompt's "Previous observations" section |
| **Truncation** | Results >200 chars truncated with `...` |
| **Limit** | Keep last 10 observations to manage context |

The loop continues until the LLM returns `action: "final"` or `max_steps` is reached.

# Multi-Step Task Handling

## Overview

Multi-step tasks require the agent to:
1. Break down a complex task into steps
2. Execute each step sequentially
3. Use results from previous steps
4. Track progress toward the goal
5. Know when to stop

---

## Task Complexity Spectrum

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TASK COMPLEXITY                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SINGLE-STEP                              MULTI-STEP                    │
│  ───────────                              ───────────                   │
│                                                                          │
│  "Write hello to a.txt"                  "Create a Python file that      │
│                                            prints hello, run it,        │
│                                            and show the output"         │
│       │                                              │                   │
│       ▼                                              ▼                   │
│  ┌─────────┐                                  ┌─────────────┐            │
│  │  Write  │                                  │   Step 1   │            │
│  │  file   │                                  │ Write file │            │
│  └─────────┘                                  └──────┬──────┘            │
│       │                                             │                   │
│       ▼                                             ▼                   │
│  ┌─────────┐                                  ┌─────────────┐            │
│  │  Done   │                                  │   Step 2   │            │
│  └─────────┘                                  │ Run file   │            │
│                                             └──────┬──────┘            │
│                                                   │                    │
│                                                   ▼                    │
│                                             ┌─────────────┐            │
│                                             │   Step 3   │            │
│                                             │ Show output│            │
│                                             └──────┬──────┘            │
│                                                   │                    │
│                                                   ▼                    │
│                                              ┌─────────┐              │
│                                              │  Done   │              │
│                                              └─────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Step Loop Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT.run()                                     │
│                                                                          │
│  while not done and step < max_steps:                                    │
│      │                                                                   │
│      ├──► Think (call LLM) ──► Decision                                 │
│      │                           │                                       │
│      │                           ▼                                       │
│      │                     ┌─────────────┐                              │
│      │                     │  DECISION   │                              │
│      │                     └──────┬──────┘                              │
│      │                            │                                     │
│      │         ┌──────────────────┼──────────────────┐                 │
│      │         │                  │                  │                  │
│      │         ▼                  ▼                  ▼                  │
│      │   ┌──────────┐      ┌──────────┐       ┌──────────┐            │
│      │   │ "tool"  │      │ "final" │       │"clarify" │            │
│      │   └────┬─────┘      └────┬─────┘       └────┬─────┘            │
│      │        │                 │                   │                   │
│      │        ▼                 │                   │                   │
│      │   ┌─────────┐            │                   │                   │
│      │   │ Execute │            │                   │                   │
│      │   │  tool   │            │                   │                   │
│      │   └────┬────┘            │                   │                   │
│      │        │                 │                   │                   │
│      │        ▼                 │                   │                   │
│      │   ┌─────────┐            │                   │                   │
│      │   │Observe  │            │                   │                   │
│      │   └────┬────┘            │                   │                   │
│      │        │                 │                   │                   │
│      │        └─────────────────┴───────────────────┘                   │
│      │                          │                                        │
│      │                          ▼                                        │
│      │                    Next iteration ◄───────────────────────────┘  │
│      │                                                                   │
│      ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         EXIT LOOP                                 │   │
│  │                                                                  │   │
│  │   - Final response returned to user                             │   │
│  │   - Or: Max steps reached → summary returned                   │   │
│  │   - Or: Clarification needed → question returned               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Execution Flow

### Example Task

```
"Create a Python script that calculates the factorial of 5, run it, 
 and show me the result"
```

### Step 1: Write the Script

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1                                                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  THINK:                                                            │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Task: Create a Python script that calculates factorial of 5... │ │
│  │ Step 1 of 10                                                 │ │
│  │ Previous observations: None                                   │ │
│  │                                                               │ │
│  │ I need to first create the Python file. The file_write tool   │ │
│  │ can do this. I'll create a factorial function.               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  DECISION:                                                         │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ {"action": "file_write", "action_input": {                    │ │
│  │   "path": "factorial.py",                                    │ │
│  │   "content": "def factorial(n):\n    if n <= 1: return 1\n  │ │
│  │       return n * factorial(n-1)\n\nprint(factorial(5))"       │ │
│  │ }}                                                            │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ACT:                                                              │
│  ToolExecutor.execute("file_write", {...})                          │
│                                                                     │
│  OBSERVE:                                                          │
│  "Successfully wrote to factorial.py"                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 2: Run the Script

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2                                                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  THINK:                                                            │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Task: Create a Python script that calculates factorial of 5... │ │
│  │ Step 2 of 10                                                 │ │
│  │ Previous observations:                                       │ │
│  │ - Step 1: file_write → Successfully wrote to factorial.py   │ │
│  │                                                               │ │
│  │ The file is created. Now I need to run it using the command  │ │
│  │ tool.                                                       │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  DECISION:                                                         │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ {"action": "command", "action_input": {                       │ │
│  │   "command": "python factorial.py"                            │ │
│  │ }}                                                            │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ACT:                                                              │
│  ToolExecutor.execute("command", {"command": "python factorial.py"}) │
│                                                                     │
│  OBSERVE:                                                          │
│  "Exit: 0\nSTDOUT:\n120\nSTDERR:\n"                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 3: Finalize

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3                                                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  THINK:                                                            │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Task: Create a Python script that calculates factorial of 5... │ │
│  │ Step 3 of 10                                                 │ │
│  │ Previous observations:                                       │ │
│  │ - Step 1: file_write → Successfully wrote to factorial.py   │ │
│  │ - Step 2: command → Exit: 0\nSTDOUT:\n120                  │ │
│  │                                                               │ │
│  │ The script ran successfully and returned 120 (which is        │ │
│  │ 5! = 5 × 4 × 3 × 2 × 1 = 120). The task is complete.       │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  DECISION:                                                         │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ {"action": "final", "content": "Done! Created factorial.py     │ │
│  │   which calculates the factorial. Running it with input 5     │ │
│  │   gives 120 (5! = 5 × 4 × 3 × 2 × 1)."                      │ │
│  │ }}                                                            │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  RESULT: "Done! Created factorial.py..."                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Complex Multi-Step Example

### Task

```
"Find all Python files in the project, count the lines in each, 
 and create a summary report"
```

### Execution Trace

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: List files to find Python files                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  LLM Decision: {"action": "command", "action_input": {              │
│    "command": "Get-ChildItem -Recurse -Filter *.py | Select-Object│
│                 FullName | ConvertTo-Json"                           │
│  }}                                                                 │
│                                                                     │
│  Observation: "{\"FullName\":\"test_agent.py\"},                    │
│                {\"FullName\":\"hello.py\"},                         │
│                {\"FullName\":\"agent_core\\agent.py\"},..."           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Count lines in each file                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  LLM Decision: {"action": "command", "action_input": {              │
│    "command": "(Get-Content test_agent.py | Measure-Object -Line). │
│                 Lines; (Get-Content hello.py | Measure-Object -Line│
│                 ).Lines..."                                         │
│  }}                                                                 │
│                                                                     │
│  Observation: "test_agent.py: 25 lines\nhello.py: 12 lines\n        │
│                agent.py: 150 lines..."                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Create summary report                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  LLM Decision: {"action": "file_write", "action_input": {           │
│    "path": "line_counts.txt",                                       │
│    "content": "Python Files Line Count Summary\n"                   │
│    "======================\n\ntest_agent.py: 25 lines\n..."           │
│  }}                                                                 │
│                                                                     │
│  Observation: "Successfully wrote to line_counts.txt"               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: Return final response                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  LLM Decision: {"action": "final", "content": "Found 8 Python files │
│    totaling 420 lines. Summary saved to line_counts.txt."}           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Planning vs. Reactive Approaches

### Approach 1: Reactive (LLM decides each step)

```
LLM receives task → LLM picks tool → Executes → LLM sees result → LLM picks next tool → ...
```

**Pros:**
- Simple implementation
- LLM adapts to actual results
- Handles unexpected outcomes

**Cons:**
- May make suboptimal choices
- No long-term planning

### Approach 2: Planning (LLM creates a plan first)

```
LLM receives task → LLM creates plan: ["step1", "step2", "step3"] → Execute plan → Adjust as needed
```

**Pros:**
- Clear intent
- Can optimize order
- Can validate completion

**Cons:**
- More complex
- Plans may need adjustment

**Recommendation:** Use **Approach 1** (reactive) for simplicity. The LLM can still implicit planning by considering the task holistically in each decision.

---

## Task Decomposition Strategies

### Strategy 1: Sequential Dependencies

```
Task: A → B → C
      └──► B must happen after A
                └──► C must happen after B
```

**Example:**
```
1. Read config file
2. Process data using config
3. Write output based on processed data
```

### Strategy 2: Parallel Opportunities

```
Task: [A, B] → C
      └─────► Both can run independently
                   └─► C depends on both
```

**Example:**
```
1. List files + Check disk space (parallel)
2. Process files (depends on both)
```

**Note:** Current implementation is sequential. Parallel execution is a future enhancement.

### Strategy 3: Conditional Branching

```
Task: Check condition → If true: A, else: B
      └─► LLM decides based on observation
```

**Example:**
```
1. List files
2. If Python files exist: analyze them
   Else: Report no files found
```

---

## Progress Tracking

### What the LLM Knows

```python
# In each prompt
"""
Task: {task}

Step {n} of {max_steps}.

Previous observations:
- Step 1: action → result
- Step 2: action → result

Remaining steps: {max_steps - n}
"""
```

### How LLM Tracks Progress

```
Step 1: Create file → "File created"
Step 2: Run file   → "Output: 120"
Step 3: ???         → "Task complete, returning final answer"
```

The LLM implicitly tracks progress by:
1. Remembering what it's already done
2. Comparing observations to the goal
3. Deciding when the task is "done enough"

---

## Knowing When to Stop

### LLM Should Return `final` When:

1. **Goal achieved**
   ```
   Task: "Calculate 2+2"
   Observation: "2+2=4"
   → Final: "The answer is 4"
   ```

2. **Goal impossible**
   ```
   Task: "Read nonexistent file"
   Observation: "File not found"
   → Final: "I couldn't find the file. Would you like me to create it?"
   ```

3. **User needs to decide**
   ```
   Task: "Create project"
   Observation: "Should I use React or Vue?"
   → Final: "Which framework would you prefer?"
   ```

4. **Max steps reached** (automatic)
   ```
   10 steps completed without final
   → Return summary of what was accomplished
   ```

### LLM Should NOT Return `final` When:

1. **Tool just executed**
   ```
   Observation: "File written"
   → Needs another step to verify or complete
   ```

2. **Partial progress**
   ```
   Task: "Process 10 files"
   Observation: "Processed 3 files"
   → Needs to process remaining 7
   ```

---

## Error Recovery in Multi-Step

```
┌─────────────────────────────────────────────────────────────────────┐
│ ERROR RECOVERY SCENARIO                                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Task: "Write to config.txt"                                       │
│                                                                     │
│  Step 1:                                                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ LLM: {"action": "file_write", "action_input": {               │  │
│  │   "path": "config.txt",                                       │  │
│  │   "content": "setting=true"                                   │  │
│  │ }}                                                            │  │
│  │                                                               │  │
│  │ Tool: "Error: Permission denied"                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  Step 2:                                                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Prompt: "Step 2. Previous: file_write → Permission denied"   │  │
│  │                                                               │  │
│  │ LLM thinks: "The write failed. Let me try using command      │  │
│  │              with elevated privileges, or ask user."          │  │
│  │                                                               │  │
│  │ LLM Decision: {"action": "command", "action_input": {         │  │
│  │   "command": "echo setting=true > config.txt"}                 │  │
│  │ }}                                                            │  │
│  │                                                               │  │
│  │ Tool: "Successfully wrote to config.txt"                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  Step 3: Final response                                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ {"action": "final", "content": "Done! Wrote to config.txt    │  │
│  │   using command since direct write was denied."}              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Summary

| Aspect | Implementation |
|--------|----------------|
| **Loop** | `while not done and step < max_steps` |
| **Decision** | LLM chooses tool + args |
| **Execution** | `ToolExecutor.execute()` |
| **Observation** | Stored, fed back to next prompt |
| **Completion** | LLM returns `action: "final"` |
| **Max steps** | Automatic fallback (return summary) |
| **Error recovery** | LLM sees error, adapts in next step |

The multi-step loop is the core of the agent's capability — enabling it to handle complex tasks by breaking them into manageable pieces.

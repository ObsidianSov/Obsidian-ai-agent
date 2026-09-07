# Obsidian AI - LLM-Driven Coding Agent

## Target Lifecycle Implementation

| Step | Component | Description | Status |
|------|-----------|-------------|--------|
| 1 | System Prompt | Agent identity and capabilities | ✅ |
| 2 | User Task | The user's request | ✅ |
| 3 | LLM Inference | Calling the LLM | ✅ |
| 4 | Tool Calling | LLM requests tool execution | ✅ |
| 5 | Tool Execution | Actually running the tool | ✅ |
| 6 | Observation | Tool result fed back to LLM | ✅ |
| 7 | Loop | Continue until task complete | ✅ |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           AGENT LIFECYCLE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────┐                                                    │
│   │   SYSTEM    │  "You are Obsidian, an AI coding assistant..."     │
│   │   PROMPT    │                                                    │
│   └─────────────┘                                                    │
│          │                                                           │
│          ▼                                                           │
│   ┌─────────────┐                                                    │
│   │   USER      │  "List files in the current directory"             │
│   │   TASK      │                                                    │
│   └─────────────┘                                                    │
│          │                                                           │
│          ▼                                                           │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │                    LLM INFERENCE                             │    │
│   │         ┌─────────────────────────────────┐                  │    │
│   │         │  OpenRouter API                │                  │    │
│   │         │  - Model: claude-3-haiku      │                  │    │
│   │         │  - Tools: [list_directory]    │                  │    │
│   │         └─────────────────────────────────┘                  │    │
│   └─────────────────────────────────────────────────────────────┘    │
│          │                                                           │
│          ▼                                                           │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐          │
│   │   TOOL      │ ──▶ │   TOOL      │ ──▶ │ OBSERVATION │          │
│   │   CALLING   │     │  EXECUTION  │     │             │          │
│   │ list_directory │   │             │     │ "agent_core │          │
│   │   {path: .} │     │  os.listdir │     │  ARCH.md..." │          │
│   └─────────────┘     └─────────────┘     └─────────────┘          │
│          │                                          │                │
│          └──────────────────────────────────────────┘                │
│                          LOOP                                        │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │                   FINAL RESPONSE                            │    │
│   │  "The current directory contains: agent_core, ARCH.md..."   │    │
│   └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Files

| File | Description |
|------|-------------|
| `agent_core/lifecycle.py` | Complete lifecycle implementation |

---

## Usage

```bash
# CLI
py -m agent_core.lifecycle "List files in the current directory"
py -m agent_core.lifecycle "What is 2 + 2?"

# Python API
from agent_core.lifecycle import create_agent

agent = create_agent()
result = agent.run("Read the contents of test.txt")
print(result)
```

---

## Test Results

```
LLM-DRIVEN CODING AGENT - Lifecycle Test Suite
==============================================

Testing tool definitions...          [PASS]
Testing built-in tool functions...   [PASS]
Testing tool executor...             [PASS]
Testing LLM provider...              [PASS]
Testing agent lifecycle...           [PASS]
Testing multi-step task...           [PASS]

RESULTS: 6/6 tests passed
[SUCCESS] All lifecycle tests passed!
```

---

## Example Output

```
[*] Obsidian processing: List files in the current directory...
    [Step 1] Calling LLM...
    [Tool] list_directory({'path': '.'})
    [Result] agent_core
ARCHITECTURE.md
CHANGE_REPORT.md
...
    [Step 2] Calling LLM...
    [Done] Final response: The current directory contains: agent_core, ARCHITECTURE.md...

[Result]
The current directory contains: agent_core, ARCHITECTURE.md...
```

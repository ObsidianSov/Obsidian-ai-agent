# Data Flow: LLM-Driven ReAct Agent

## Overview

The data flow follows the **ReAct pattern** (Reasoning + Acting): the LLM thinks, decides on an action, receives results, and repeats until the task is complete.

---

## High-Level Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              USER TASK                                   │
│                       "Write a hello world to test.txt"                  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                               Agent.run()                                │
│                                                                          │
│  Input:  task = "Write a hello world to test.txt"                       │
│                                                                          │
│  Steps:                                                                  │
│    1. Add task to working memory                                        │
│    2. Get memory context                                                │
│    3. Get available tools                                               │
│    4. Initialize LLMReActEngine                                         │
│    5. Enter reasoning loop                                              │
│                                                                          │
│  Output: Final response string                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     REASONING LOOP (max 10 iterations)                   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     ITERATION N                                   │   │
│  │                                                                   │   │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐    │   │
│  │   │  THINK      │───►│  DECIDE     │───►│  ACT (or END)   │    │   │
│  │   │  Call LLM   │    │  Parse JSON │    │  Execute tool   │    │   │
│  │   └─────────────┘    └─────────────┘    └─────────────────┘    │   │
│  │         │                                        │               │   │
│  │         │                                        │               │   │
│  │         │           ┌─────────────┐              │               │   │
│  │         └──────────►│  OBSERVE   │◄─────────────┘               │   │
│  │                     │  Add to     │                              │   │
│  │                     │  context    │                              │   │
│  │                     └─────────────┘                              │   │
│  │                                                                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                       ┌────────────┴────────────┐                     │
│                       │                         │                     │
│                       ▼                         ▼                     │
│              ┌─────────────────┐       ┌─────────────────┐           │
│              │ action = "tool" │       │ action = "final" │           │
│              │ Continue loop   │       │ Return response │           │
│              └─────────────────┘       └─────────────────┘           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Data Flow (Iteration 1)

### Step 1: Agent.run() — Initialization

```
INPUT
────────────────────────────
task: "Write hello world to test.txt"
────────────────────────────
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Agent.__init__()                                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  self.tools = ToolRegistry()     → 8 tools registered               │
│  self.memory = MemorySystem()     → working + persistent loaded       │
│  self.react = LLMReActEngine()   → empty history, step = 0          │
│  self.executor = ToolExecutor()  → wraps tool registry               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Agent.run() — Context Gathering                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  memory_context = memory.get_system_context()                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ {                                                             │    │
│  │   "recent_conversation": [...],                               │    │
│  │   "user_preferences": [...],                                  │    │
│  │   "knowledge_base_keys": [...]                                │    │
│  │ }                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  available_tools = tools.list_tools()                                 │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ [                                                            │    │
│  │   {"name": "file_write", "description": "...", "params": {}}│    │
│  │   {"name": "read_workspace_file", "description": "...", ...}│    │
│  │   {"name": "command", "description": "...", ...},            │    │
│  │   ... (8 total)                                               │    │
│  │ ]                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
```

### Step 2: Loop Iteration 1 — THINK

```
┌─────────────────────────────────────────────────────────────────────┐
│  LLMReActEngine.think()                                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INPUT                                                               │
│  ─────                                                               │
│  task: "Write hello world to test.txt"                              │
│  available_tools: [list of 8 tools]                                │
│  context: {memory_context}                                           │
│  step: 1                                                             │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  2.1. Build System Prompt                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ You are Obsidian, an AI agent.                               │    │
│  │                                                              │    │
│  │ AVAILABLE TOOLS:                                             │    │
│  │ - file_write(path: string, content: string)                  │    │
│  │ - read_workspace_file(path: string)                          │    │
│  │ - command(command: string)                                    │    │
│  │ - list_files(path: string)                                    │    │
│  │ - create_directory(path: string)                              │    │
│  │ - get_env(key: string)                                        │    │
│  │                                                              │    │
│  │ MEMORY CONTEXT:                                               │    │
│  │ - Recent: [recent conversation items]                        │    │
│  │ - Preferences: [user preferences]                           │    │
│  │                                                              │    │
│  │ OUTPUT FORMAT (JSON only):                                   │    │
│  │ {"action": "tool_name", "action_input": {...}}               │    │
│  │ OR when done:                                                 │    │
│  │ {"action": "final", "content": "response to user"}           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  2.2. Build Task Prompt                                             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Task: Write hello world to test.txt                          │    │
│  │                                                              │    │
│  │ Step 1 of 10.                                                │    │
│  │ Previous observations: None                                  │    │
│  │                                                              │    │
│  │ What should I do first? Output JSON only.                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  2.3. Call OpenRouter API                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ POST https://openrouter.ai/api/v1/chat/completions          │    │
│  │                                                              │    │
│  │ {                                                            │    │
│  │   "model": "anthropic/claude-3-haiku",                     │    │
│  │   "messages": [                                              │    │
│  │     {"role": "system", "content": "<system_prompt>"},       │    │
│  │     {"role": "user", "content": "<task_prompt>"}            │    │
│  │   ]                                                          │    │
│  │ }                                                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ LLM RESPONSE (example)                                       │    │
│  │ {                                                           │    │
│  │   "action": "file_write",                                    │    │
│  │   "action_input": {                                         │    │
│  │     "path": "test.txt",                                      │    │
│  │     "content": "hello world"                                │    │
│  │   }                                                         │    │
│  │ }                                                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  2.4. Parse Response                                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ _parse_response(raw_json) → ParsedDecision                  │    │
│  │ {                                                           │    │
│  │   "action": "file_write",                                   │    │
│  │   "action_input": {"path": "test.txt", "content": "..."}   │    │
│  │ }                                                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  OUTPUT                                                              │
│  ──────                                                              │
│  return ParsedDecision(action="file_write", input={...})            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 3: Loop Iteration 1 — ACT

```
┌─────────────────────────────────────────────────────────────────────┐
│  Agent.run() — Execute Tool                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INPUT                                                               │
│  ─────                                                               │
│  decision = {                                                       │
│    "action": "file_write",                                          │
│    "action_input": {"path": "test.txt", "content": "hello world"}  │
│  }                                                                   │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  ToolExecutor.execute("file_write", {path, content})                 │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ tool_registry.execute("file_write", path="test.txt",        │    │
│  │                           content="hello world")             │    │
│  │                                                             │    │
│  │ FileWriteTool._write()                                      │    │
│  │   → open("test.txt", "w")                                  │    │
│  │   → write("hello world")                                   │    │
│  │   → return "Successfully wrote to test.txt"                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                           │                                          │
│                           ▼                                          │
│  OBSERVATION = "Successfully wrote to test.txt"                     │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  react.add_observation(1, observation)                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ thought_history[0].observation = "Successfully wrote..."   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
```

### Step 4: Loop Iteration 2 — THINK (with observation)

```
┌─────────────────────────────────────────────────────────────────────┐
│  LLMReActEngine.think() — Iteration 2                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INPUT                                                               │
│  ─────                                                               │
│  task: "Write hello world to test.txt"                              │
│  step: 2                                                             │
│  observations_so_far: [                                              │
│    {step: 1, action: "file_write", result: "Successfully wrote..."} │
│  ]                                                                   │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Build Task Prompt with observations:                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Task: Write hello world to test.txt                          │    │
│  │                                                              │    │
│  │ Step 2 of 10.                                                │    │
│  │ Previous observations:                                        │    │
│  │ - Step 1: file_write → "Successfully wrote to test.txt"     │    │
│  │                                                              │    │
│  │ The file has been written. Is the task complete?            │    │
│  │ Output JSON only.                                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Call LLM → Get response:                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ {                                                           │    │
│  │   "action": "final",                                         │    │
│  │   "content": "Done! I've written 'hello world' to test.txt" │    │
│  │ }                                                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  OUTPUT                                                              │
│  ──────                                                              │
│  ParsedDecision(action="final", content="Done!...")                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
```

### Step 5: Agent.run() — Complete

```
┌─────────────────────────────────────────────────────────────────────┐
│  Agent.run() — Exit Loop                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  decision.action == "final"                                         │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Return: "Done! I've written 'hello world' to test.txt"     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Post-processing:                                                    │
│  memory.working.add("assistant", response)                          │
│  (Optionally store in persistent memory if important)               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         USER RESPONSE                               │
│            "Done! I've written 'hello world' to test.txt"           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Complete Data Flow Diagram

```
USER INPUT
     │
     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║                        AGENT Orchestrator                              ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                        ║  │
│  ║   workspace ──────────┐                                                ║  │
│  ║                       │                                                ║  │
│  ║                       ▼                                                ║  │
│  ║   ┌───────────────────────────────────────────────────────────────┐   ║  │
│  ║   │ 1. Gather Context                                            │   ║  │
│  ║   │                                                               │   ║  │
│  ║   │ memory.get_system_context() ──► context_dict                 │   ║  │
│  ║   │ tools.list_tools() ───────────► available_tools             │   ║  │
│  ║   └───────────────────────────────────────────────────────────────┘   ║  │
│  ║                              │                                        ║  │
│  ║                              ▼                                        ║  │
│  ║   ┌───────────────────────────────────────────────────────────────┐   ║  │
│  ║   │ 2. Enter Reasoning Loop (while step < max_steps)              │   ║  │
│  ║   │                                                               │   ║  │
│  ║   │    ┌──────────────────────────────────────────────────────┐   │   ║  │
│  ║   │    │ ITERATION N                                          │   │   ║  │
│  ║   │    │                                                      │   │   ║  │
│  ║   │    │ ┌─────────────────────────────────────────────────┐ │   │   ║  │
│  ║   │    │ │ THINK                                            │ │   │   ║  │
│  ║   │    │ │                                                 │ │   │   ║  │
│  ║   │    │ │ react.think(task, tools, context, observations) │ │   │   ║  │
│  ║   │    │ │         │                                        │ │   │   ║  │
│  ║   │    │ │         ▼                                        │ │   │   ║  │
│  ║   │    │ │ ┌─────────────────────────────────────────────┐  │ │   │   ║  │
│  ║   │    │ │ │ PromptBuilder.build_system_prompt()        │  │ │   │   ║  │
│  ║   │    │ │ │   + build_step_prompt()                    │  │ │   │   ║  │
│  ║   │    │ │ └─────────────────────────────────────────────┘  │ │   │   ║  │
│  ║   │    │ │         │                                        │ │   │   ║  │
│  ║   │    │ │         ▼                                        │ │   │   ║  │
│  ║   │    │ │ ┌─────────────────────────────────────────────┐  │ │   │   ║  │
│  ║   │    │ │ │ LLMProvider.complete(system, user)           │  │ │   │   ║  │
│  ║   │    │ │ │         │                                    │  │ │   │   ║  │
│  ║   │    │ │ │         ▼                                    │  │ │   │   ║  │
│  ║   │    │ │ │ ┌─────────────────────────────────────────┐  │  │ │   │   ║  │
│  ║   │    │ │ │ │ OpenRouter API                          │  │  │ │   │   ║  │
│  ║   │    │ │ │ │ POST /chat/completions                  │  │  │ │   │   ║  │
│  ║   │    │ │ │ │ model: claude-3-haiku                   │  │  │ │   │   ║  │
│  ║   │    │ │ │ └─────────────────────────────────────────┘  │  │ │   │   ║  │
│  ║   │    │ │ │         │                                    │  │ │   │   ║  │
│  ║   │    │ │ │         ▼                                    │  │ │   │   ║  │
│  ║   │    │ │ │ ┌─────────────────────────────────────────┐  │  │ │   │   ║  │
│  ║   │    │ │ │ │ ResponseParser.parse()                  │  │  │ │   │   ║  │
│  ║   │    │ │ │ │ → {action, action_input} or {final}     │  │  │ │   │   ║  │
│  ║   │    │ │ │ └─────────────────────────────────────────┘  │  │ │   │   ║  │
│  ║   │    │ │ └─────────────────────────────────────────────────┘ │   │   ║  │
│  ║   │    │ └──────────────────────────────────────────────────────┘   │   ║  │
│  ║   │    │                        │                                   │   ║  │
│  ║   │    │                        ▼                                   │   ║  │
│  ║   │    │    ┌──────────────────────────────────────────────────┐   │   ║  │
│  ║   │    │    │ DECIDE                                              │   │   ║  │
│  ║   │    │    │                                                      │   │   ║  │
│  ║   │    │    │    action == "tool" ──────────────────────────┐    │   │   ║  │
│  ║   │    │    │    action == "final" ───────────┐             │    │   │   ║  │
│  ║   │    │    │    action == "clarify" ──┐      │             │    │   │   ║  │
│  ║   │    │    │                            │      │             │    │   │   ║  │
│  ║   │    │    └────────────────────────────│──────│─────────────┘    │   ║  │
│  ║   │    │                                 │      │                    │   ║  │
│  ║   │    │         ┌───────────────────────┘      │                    │   ║  │
│  ║   │    │         │                              │                    │   ║  │
│  ║   │    │         ▼                              ▼                    │   ║  │
│  ║   │    │    ┌─────────────────┐       ┌─────────────────┐         │   ║  │
│  ║   │    │    │ EXECUTE TOOL     │       │ RETURN TO USER  │         │   ║  │
│  ║   │    │    │                 │       │ (exit loop)     │         │   ║  │
│  ║   │    │    │ executor.execute│       │                 │         │   ║  │
│  ║   │    │    │ (action, input) │       │ content string  │         │   ║  │
│  ║   │    │    │       │          │       └─────────────────┘         │   ║  │
│  ║   │    │    │       ▼          │                                  │   ║  │
│  ║   │    │    │ ┌─────────────┐  │                                  │   ║  │
│  ║   │    │    │ │ ToolRegistry│  │                                  │   │   ║  │
│  ║   │    │    │ │ .execute()  │  │                                  │   │   ║  │
│  ║   │    │    │ │             │  │                                  │   │   ║  │
│  ║   │    │    │ │ ┌─────────┐ │  │                                  │   │   ║  │
│  ║   │    │    │ │ │file_write│ │  │                                  │   │   │   ║  │
│  ║   │    │    │ │ │read_file │ │  │                                  │   │   │   ║  │
│  ║   │    │    │ │ │command   │ │  │                                  │   │   │   ║  │
│  ║   │    │    │ │ │...       │ │  │                                  │   │   │   ║  │
│  ║   │    │    │ │ └─────────┘ │  │                                  │   │   │   ║  │
│  ║   │    │    │ └─────────────┘  │                                  │   │   ║  │
│  ║   │    │    │       │          │                                  │   │   ║  │
│  ║   │    │    │       ▼          │                                  │   │   ║  │
│  ║   │    │    │ ┌─────────────┐  │                                  │   │   ║  │
│  ║   │    │    │ │ OBSERVATION │  │                                  │   │   ║  │
│  ║   │    │    │ │ "Success..."│  │                                  │   │   ║  │
│  ║   │    │    │ └─────────────┘  │                                  │   │   ║  │
│  ║   │    │    │       │          │                                  │   │   ║  │
│  ║   │    │    │       └──────────┼──────────────────────────────────┘   │   ║  │
│  ║   │    │    │                  │                                      │   ║  │
│  ║   │    │    │                  ▼                                      │   │   ║  │
│  ║   │    │    │    ┌─────────────────────────────────────────────────┐│   │   ║  │
│  ║   │    │    │    │ ADD OBSERVATION                                 ││   │   ║  │
│  ║   │    │    │    │                                                 ││   │   ║  │
│  ║   │    │    │    │ react.add_observation(step, observation)      ││   │   ║  │
│  ║   │    │    │    │ observations.append({step, action, result})    ││   │   ║  │
│  ║   │    │    │    └─────────────────────────────────────────────────┘│   │   ║  │
│  ║   │    │    │                  │                                      │   │   ║  │
│  ║   │    │    │                  │  Next iteration ◄──────────────────┘   ║  │
│  ║   │    │    │                  │                                      │   ║  │
│  ║   │    │    └──────────────────┴──────────────────────────────────────┘   ║  │
│  ║   │    └──────────────────────────────────────────────────────────────┘   ║  │
│  ║   │                                                                   │   ║  │
│  ║   └───────────────────────────────────────────────────────────────────┘   ║  │
│  ║                                                                       │   ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │   USER OUTPUT   │
                               │ "Done! Wrote..." │
                               └─────────────────┘
```

---

## Data Structures per Step

### Input to `think()`

```python
@dataclass
class ThinkInput:
    task: str                    # "Write hello world to test.txt"
    available_tools: List[Dict] # [{"name": "file_write", ...}, ...]
    context: Dict               # Memory context from get_system_context()
    observations: List[Dict]    # Previous step results
    step: int                    # Current step number (1-indexed)
```

### Output from `think()`

```python
@dataclass
class Decision:
    action: str                 # "file_write" | "final" | "clarify"
    action_input: Dict | None  # {"path": "test.txt", "content": "..."}
    content: str | None         # For "final" action only
    question: str | None        # For "clarify" action only
```

### Observation (internal)

```python
@dataclass
class Observation:
    step: int                   # 1, 2, 3...
    action: str                  # Tool that was called
    input: Dict                  # Arguments passed
    result: str                 # Tool output
    error: str | None            # If tool failed
```

---

## Error Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ERROR SCENARIOS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SCENARIO 1: LLM API Error                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ OpenRouter returns error                                    │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ Retry with exponential backoff (3 attempts)                  │    │
│  │     │                                                        │    │
│  │     ├── Success → continue                                  │    │
│  │     │                                                        │    │
│  │     └── Failure → Return error to user                      │    │
│  │                    "LLM unavailable, please try again"      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  SCENARIO 2: Invalid LLM Response                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ LLM returns non-JSON or invalid format                       │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ Ask LLM to retry with format hint                           │    │
│  │ "Please output valid JSON: {\"action\": \"...\", ...}"        │    │
│  │     │                                                        │    │
│  │     ├── Success → continue                                   │    │
│  │     └── Failure → continue to next iteration                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  SCENARIO 3: Unknown Tool                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ LLM requests "delete_file" (not in available tools)         │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ executor.execute() raises ValueError                          │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ Observation = "Error: Unknown tool 'delete_file'"            │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ LLM sees error, can try different tool in next iteration     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  SCENARIO 4: Tool Execution Error                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ file_write fails (permission denied)                        │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ Observation = "Error: Permission denied"                     │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ LLM sees error, can try:                                     │    │
│  │   - Use command tool instead                                 │    │
│  │   - Ask user for clarification                              │    │
│  │   - Report failure                                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  SCENARIO 5: Max Steps Reached                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ 10 iterations completed, no final response                    │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ Generate summary of all observations                          │    │
│  │     │                                                        │    │
│  │     ▼                                                        │    │
│  │ Return: "Completed X steps but task may be incomplete.       │    │
│  │         Here's what was done: ..."                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Summary

| Phase | Component | Input | Output |
|-------|-----------|-------|--------|
| Init | Agent | task string | context + tools |
| Think | PromptBuilder | task, tools, context, obs | formatted prompt |
| Think | LLMProvider | prompt | LLM response text |
| Think | ResponseParser | raw text | Decision object |
| Decide | Agent | Decision | action type |
| Act | ToolExecutor | action, args | observation string |
| Observe | LLMReActEngine | observation | updated context |
| Complete | Agent | final content | response to user |

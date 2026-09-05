# Tool-Calling Protocol

## Overview

The protocol defines how the LLM:
1. Receives tool descriptions
2. Selects a tool
3. Provides arguments
4. Receives results

---

## Protocol Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           TOOL-CALLING PROTOCOL                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ STEP 1: PROVIDE TOOLS                                             │   │
│  │                                                                    │   │
│  │ System prompt includes formatted tool descriptions:                 │   │
│  │                                                                    │   │
│  │ AVAILABLE TOOLS:                                                  │   │
│  │ - file_write(path: string, content: string)                        │   │
│  │   Writes content to a file. Creates if not exists.                 │   │
│  │                                                                    │   │
│  │ - read_workspace_file(path: string)                                 │   │
│  │   Reads file content. Returns error if not found.                   │   │
│  │                                                                    │   │
│  │ - command(command: string)                                          │   │
│  │   Executes terminal command. Returns stdout/stderr.                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ STEP 2: LLM DECIDES                                                │   │
│  │                                                                    │   │
│  │ User: "Write hello world to test.txt"                            │   │
│  │                                                                    │   │
│  │ LLM thinks: "User wants to write to a file. The file_write tool   │   │
│  │            can do this. I need to provide path and content."      │   │
│  │                                                                    │   │
│  │ LLM outputs:                                                       │   │
│  │   {                                                               │   │
│  │     "action": "file_write",                                        │   │
│  │     "action_input": {                                             │   │
│  │       "path": "test.txt",                                         │   │
│  │       "content": "hello world"                                    │   │
│  │     }                                                             │   │
│  │   }                                                               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ STEP 3: VALIDATE & EXECUTE                                        │   │
│  │                                                                    │   │
│  │ Parse JSON → Validate tool exists → Validate arguments → Execute    │   │
│  │                                                                    │   │
│  │   ┌─────────────────────────────────────────────────────────┐     │   │
│  │   │ ToolExecutor.execute("file_write", {                    │     │   │
│  │   │   path: "test.txt",                                     │     │   │
│  │   │   content: "hello world"                               │     │   │
│  │   │ })                                                      │     │   │
│  │   │       │                                                 │     │   │
│  │   │       ▼                                                 │     │   │
│  │   │   ┌─────────────────────────────────────────────────┐ │     │   │
│  │   │   │ ToolRegistry.execute("file_write",              │ │     │   │
│  │   │   │   path="test.txt",                               │ │     │   │
│  │   │   │   content="hello world")                         │ │     │   │
│  │   │   └─────────────────────────────────────────────────┘ │     │   │
│  │   └─────────────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ STEP 4: RETURN OBSERVATION                                         │   │
│  │                                                                    │   │
│  │ Success: "Successfully wrote to test.txt"                         │   │
│  │ Error: "Error: Permission denied"                                 │   │
│  │                                                                    │   │
│  │ Observation fed back to LLM for next iteration                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Tool Description Format

### Structure

Each tool is described with:
1. **Name** - Function identifier
2. **Parameters** - Input schema with types
3. **Description** - What the tool does

### Prompt Format

```python
AVAILABLE TOOLS:

- file_write(path: string, content: string)
  Writes content to a file. Creates new file or overwrites existing.
  Parameters:
    - path: Relative path from workspace root
    - content: Text content to write

- read_workspace_file(path: string)
  Reads the entire content of a file.
  Parameters:
    - path: Relative path from workspace root

- command(command: string)
  Executes a terminal command and returns output.
  Parameters:
    - command: Shell command to execute

- list_files(path: string)
  Lists all files and directories in a path.
  Parameters:
    - path: Directory path to list (default: current directory)

- create_directory(path: string)
  Creates a new directory and any necessary parent directories.
  Parameters:
    - path: Directory path to create

- get_env(key: string)
  Retrieves an environment variable value.
  Parameters:
    - key: Name of the environment variable
```

### JSON Schema Format (Alternative)

```json
{
  "tools": [
    {
      "name": "file_write",
      "description": "Writes content to a file",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "File path"
          },
          "content": {
            "type": "string",
            "description": "Content to write"
          }
        },
        "required": ["path", "content"]
      }
    }
  ]
}
```

---

## LLM Response Format

### Tool Action

```json
{
  "action": "file_write",
  "action_input": {
    "path": "test.txt",
    "content": "hello world"
  }
}
```

### Final Response

```json
{
  "action": "final",
  "content": "I've written 'hello world' to test.txt successfully."
}
```

### Ask for Clarification

```json
{
  "action": "clarify",
  "question": "Which directory should I create the file in?"
}
```

---

## Argument Validation

### Process

```
LLM Output
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Parse JSON                                               │
│    └─► Success: continue                                    │
│    └─► Fail: Return parse error to LLM, ask to retry       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Validate Tool Exists                                     │
│    └─► Yes: continue                                        │
│    └─► No: Return "Unknown tool" error, LLM can retry      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Validate Required Arguments                               │
│    └─► All present: continue                               │
│    └─► Missing: Return "Missing argument" error            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Validate Argument Types                                   │
│    └─► Valid: execute                                       │
│    └─► Invalid: Return "Invalid type" error                │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Execute Tool                                              │
│    └─► Success: Return result                              │
│    └─► Error: Return error message                         │
└─────────────────────────────────────────────────────────────┘
```

### Validation Examples

| Scenario | LLM Output | Validation | Result |
|----------|------------|------------|--------|
| Valid | `{"action": "file_write", "action_input": {"path": "a.txt", "content": "hi"}}` | All present | ✅ Execute |
| Missing arg | `{"action": "file_write", "action_input": {"path": "a.txt"}}` | Missing `content` | ❌ Error |
| Unknown tool | `{"action": "delete_file", "action_input": {}}` | Tool not found | ❌ Error |
| Wrong type | `{"action": "list_files", "action_input": {"path": 123}}` | Expected string | ❌ Error |

---

## Current Tools Registry

```python
# agent_core/tools.py

TOOLS = [
    {
        "name": "file_write",
        "description": "Write content to a file (creates or overwrites)",
        "params": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Content to write"}
        }
    },
    {
        "name": "read_workspace_file",
        "description": "Read a file from the workspace",
        "params": {
            "path": {"type": "string", "description": "Workspace-relative file path"}
        }
    },
    {
        "name": "command",
        "description": "Execute a terminal command",
        "params": {
            "command": {"type": "string", "description": "Command to execute"}
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory",
        "params": {
            "path": {"type": "string", "description": "Directory path"}
        }
    },
    {
        "name": "create_directory",
        "description": "Create a new directory",
        "params": {
            "path": {"type": "string", "description": "Directory path"}
        }
    },
    {
        "name": "get_env",
        "description": "Get environment variable",
        "params": {
            "key": {"type": "string", "description": "Environment variable name"}
        }
    }
]
```

---

## Error Handling

### Tool Execution Errors

| Error Type | Example | LLM Response |
|------------|---------|---------------|
| Unknown tool | `"delete_file"` not registered | `"Error: Unknown tool 'delete_file'"` |
| Missing argument | `path` not provided | `"Error: Missing required argument 'path'"` |
| Invalid type | `path: 123` when string expected | `"Error: Invalid type for 'path': expected string"` |
| Execution failure | File permission denied | `"Error: Permission denied"` |
| Timeout | Command takes >30s | `"Error: Tool execution timed out"` |

### How LLM Recovers

```
LLM sees error observation
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ "Error: Unknown tool 'delete_file'"                        │
│                                                              │
│ LLM can:                                                     │
│   - Try different tool (e.g., "file_write" with delete mode)│
│   - Use "command" to run rm/deltree instead                │
│   - Ask user for clarification                              │
│   - Return final answer with error                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Adding New Tools

### 1. Register in ToolRegistry

```python
# agent_core/tools.py

class SearchWebTool(Tool):
    def __init__(self):
        super().__init__(
            name="search_web",
            description="Search the web for information",
            func=self._search,
            input_schema={
                "query": {"type": "string", "description": "Search query"}
            }
        )
    
    def _search(self, query: str) -> str:
        # Implementation
        return f"Search results for: {query}"

# In _register_default_tools():
self.register(SearchWebTool())
```

### 2. Update Tool Description in Prompt

```python
def _format_tools_description(self) -> str:
    # Tools are automatically formatted from registry
    # No manual update needed if using list_tools()
    pass
```

---

## Multi-Tool Sequences

### Example: Read file → Modify → Write back

```
Step 1: LLM decides to read
  {"action": "read_workspace_file", "action_input": {"path": "config.py"}}

Step 2: Observation
  "MAX_CONNECTIONS = 100\n..."

Step 3: LLM decides to modify and write
  {"action": "file_write", "action_input": {
    "path": "config.py",
    "content": "MAX_CONNECTIONS = 200\n..."
  }}

Step 4: Observation
  "Successfully wrote to config.py"

Step 5: LLM returns final
  {"action": "final", "content": "Updated MAX_CONNECTIONS from 100 to 200"}
```

---

## Best Practices

### 1. Tool Descriptions Should Be Clear

```python
# ❌ Bad - vague
"file_write": "Writes stuff to a file"

# ✅ Good - specific
"file_write": "Writes text content to a file at the given path. Creates the file if it doesn't exist, overwrites if it does."
```

### 2. Parameter Types Should Match

```python
# ❌ Bad - inconsistent
{"path": {"type": "string", ...}}
{"count": {"type": "int", ...}}  # Use "integer" for JSON schema

# ✅ Good - consistent
{"path": {"type": "string", ...}}
{"count": {"type": "integer", ...}}
```

### 3. Required vs Optional Parameters

```python
# Explicitly mark required parameters
"required": ["path", "content"]  # Both required

# Mark optional with default
{"timeout": {"type": "integer", "description": "...", "default": 30}}
```

### 4. Observations Should Be Informative

```python
# ❌ Bad - cryptic
"Done"

# ✅ Good - descriptive
"Successfully wrote 256 bytes to test.txt"
"Error: File 'missing.txt' not found"
"Listed 12 files in directory"
```

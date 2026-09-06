import os
import json
import subprocess
from pathlib import Path

import requests

from memory_system import MemorySystem


# ============================================================
# OBSIDIAN AI — CONTROLLED CODING AGENT
# ============================================================

API_KEY = os.getenv("OPENROUTER_API_KEY")
URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL = "minimax/minimax-m2.7:free"

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = BASE_DIR / "workspace"

WORKSPACE.mkdir(exist_ok=True)

memory = MemorySystem(WORKSPACE)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = f"""
You are Obsidian AI, a highly capable autonomous software
engineering assistant.

Your primary mission is to BUILD working software.

You are exceptionally strong at:

- Python
- JavaScript
- TypeScript
- HTML
- CSS
- React
- Node.js
- APIs
- databases
- web applications
- automation
- debugging
- software architecture
- UI/UX
- system design

You have access to a controlled workspace:

{WORKSPACE}

IMPORTANT:
You may ONLY create, read, modify, or delete files inside this
workspace.

You cannot access arbitrary files outside the workspace.

You have tools for:
- listing files
- reading files
- writing files
- creating directories
- running commands
- remembering facts permanently (persists after this session ends)
- recalling previously remembered facts

Use "remember" whenever the user states a durable preference, project
decision, or fact worth keeping across sessions. Use "recall_memory"
when a past fact would help you answer the current request.

ENVIRONMENT:
- Windows
- Python is launched with "py", not "python".
- The working directory is the Obsidian workspace.
- Prefer commands that work in Windows CMD.

When building software:
1. Understand the user's objective.
2. Plan the architecture.
3. Create the necessary folders and files.
4. Write complete working code.
5. Inspect files when necessary.
6. Run appropriate commands/tests.
7. Read errors carefully.
8. Fix problems.
9. Test again.
10. Continue until the requested task is reasonably complete.

Do not merely explain how to build something when you have the
ability to build it yourself.

Do not claim that something works unless you actually tested it.

Keep responses concise while working.
"""

# ============================================================
# SECURITY
# ============================================================

def safe_path(relative_path):
    """
    Convert a workspace-relative path into an absolute path and
    prevent access outside the workspace.
    """

    relative_path = relative_path.replace("\\", "/").strip()

    target = (WORKSPACE / relative_path).resolve()
    workspace_root = WORKSPACE.resolve()

    try:
        target.relative_to(workspace_root)
    except ValueError:
        raise Exception("Access denied: path is outside the workspace.")

    return target


# ============================================================
# FILE TOOLS
# ============================================================

def list_files(path="."):
    directory = safe_path(path)

    if not directory.exists():
        return f"Directory does not exist: {path}"

    if not directory.is_dir():
        return f"Not a directory: {path}"

    results = []

    for item in sorted(directory.iterdir()):
        if item.is_dir():
            results.append(f"[DIR]  {item.name}")
        else:
            results.append(f"[FILE] {item.name}")

    return "\n".join(results) if results else "(empty directory)"


def read_file(path):
    file_path = safe_path(path)

    if not file_path.exists():
        return f"File does not exist: {path}"

    if not file_path.is_file():
        return f"Not a file: {path}"

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "Cannot read this file as UTF-8 text."


def write_file(path, content):
    file_path = safe_path(path)

    file_path.parent.mkdir(parents=True, exist_ok=True)

    file_path.write_text(content, encoding="utf-8")

    return f"File written successfully: {path}"


def create_directory(path):
    directory = safe_path(path)

    directory.mkdir(parents=True, exist_ok=True)

    return f"Directory created successfully: {path}"


# ============================================================
# COMMAND TOOL
# ============================================================

def run_command(command):
    """
    Run a command from inside the workspace.

    Commands execute with the workspace as the working directory.
    """

    print(f"\n[COMMAND] {command}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=120
        )

        output = ""

        if result.stdout:
            output += result.stdout

        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr

        output += f"\n[EXIT CODE] {result.returncode}"

        return output[-12000:]

    except subprocess.TimeoutExpired:
        return "Command timed out after 120 seconds."

    except Exception as e:
        return f"Command execution error: {e}"


# ============================================================
# ACTION GATE — BLOCK / APPROVAL / ALLOW
# ============================================================
#
# Classification logic lives in action_gate.py (pure functions,
# safely importable for testing). This wrapper adds the actual
# execution + terminal approval prompt, which needs run_command
# and input() and so can't live in the side-effect-free module.

from action_gate import classify_command


def gated_run_command(command: str) -> str:
    """
    Action-gated wrapper around run_command. This is what the
    tool executor calls — run_command() itself is unchanged and
    still does the actual execution once cleared.
    """

    tier, reason = classify_command(command)

    if tier == "BLOCK":
        print(f"\n[ACTION GATE] BLOCKED — {reason}")
        return (
            f"BLOCKED: This command was not executed because it matched "
            f"a hard-blocked destructive pattern ({reason}). "
            f"No override is possible for BLOCK-tier commands."
        )

    if tier == "APPROVAL":
        print(f"\n[ACTION GATE] APPROVAL REQUIRED — {reason}")
        print(f"Command: {command}")
        answer = input("Allow this command to run? (yes/no): ").strip().lower()

        if answer not in ("yes", "y"):
            print("[ACTION GATE] Denied by user.")
            return "DENIED: User did not approve this command. It was not executed."

        print("[ACTION GATE] Approved by user.")

    return run_command(command)


# ============================================================
# TOOL DEFINITIONS FOR THE MODEL
# ============================================================

TOOLS = [

    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories inside the Obsidian workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative directory path."
                    }
                },
                "required": ["path"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file inside the Obsidian workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path."
                    }
                },
                "required": ["path"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or completely replace a text file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path."
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file contents."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative directory path."
                    }
                },
                "required": ["path"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a terminal command from inside the Obsidian workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute."
                    }
                },
                "required": ["command"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Permanently store an important fact so it is still known in future sessions, after this terminal is closed and reopened. Use for user preferences, project decisions, or anything worth not forgetting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The fact to remember, written clearly and completely."
                    },
                    "importance": {
                        "type": "integer",
                        "description": "How important this is to recall later, 1 (minor) to 5 (critical). Default 3."
                    }
                },
                "required": ["content"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Search previously remembered facts by keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword or phrase to search stored memories for."
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(name, arguments):

    try:

        if name == "list_files":
            return list_files(arguments["path"])

        if name == "read_file":
            return read_file(arguments["path"])

        if name == "write_file":
            return write_file(
                arguments["path"],
                arguments["content"]
            )

        if name == "create_directory":
            return create_directory(arguments["path"])

        if name == "run_command":
            return gated_run_command(arguments["command"])

        if name == "remember":
            mem_id = memory.remember(
                arguments["content"],
                importance=arguments.get("importance", 3)
            )
            return f"Remembered (id={mem_id}): {arguments['content']}"

        if name == "recall_memory":
            return memory.recall(arguments["query"])

        return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error: {e}"


# ============================================================
# API
# ============================================================

def ask_model(messages):

    response = requests.post(
        URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto"
        },
        timeout=180
    )

    try:
        data = response.json()
    except Exception:
        raise Exception(
            f"Invalid response from OpenRouter: {response.text}"
        )

    if response.status_code != 200:
        raise Exception(json.dumps(data, indent=2))

    return data


# ============================================================
# MAIN AGENT LOOP
# ============================================================

if not API_KEY:
    print("ERROR: OpenRouter API key not found.")
    print("Close and reopen Command Prompt, then try again.")
    raise SystemExit


print("=" * 64)
print("                    OBSIDIAN AI")
print("                    MiniMax M2.7")
print("=" * 64)

print("CONTROLLED CODING AGENT")
print()
print(f"Workspace: {WORKSPACE}")
print()
print("Type 'exit' to quit.")
print()


messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]

_startup_memories = memory.startup_context()

if _startup_memories:
    messages.append({
        "role": "system",
        "content": (
            "MEMORY CONTEXT — facts remembered from previous sessions:\n"
            f"{_startup_memories}"
        )
    })


while True:

    try:
        user_input = input("You: ")

    except KeyboardInterrupt:
        print("\n\nObsidian AI shutting down.")
        break

    if not user_input.strip():
        continue

    if user_input.lower().strip() == "exit":
        print("\nObsidian AI shutting down.")
        break

    messages.append({
        "role": "user",
        "content": user_input
    })

    print("\nObsidian AI is working...\n")

    try:

        MAX_ITERATIONS = 15
        iteration = 0

        while True:

            iteration += 1

            if iteration > MAX_ITERATIONS:
                print(
                    "\n[STOPPED] Hit the safety limit of "
                    f"{MAX_ITERATIONS} tool-call rounds for this "
                    "turn without a final answer. Type another "
                    "message to continue, or 'exit' to quit."
                )
                break

            data = ask_model(messages)

            message = data["choices"][0]["message"]

            messages.append(message)

            # ------------------------------------------------
            # MODEL WANTS TO USE TOOLS
            # ------------------------------------------------

            tool_calls = message.get("tool_calls")

            if tool_calls:

                for tool_call in tool_calls:

                    function = tool_call["function"]

                    name = function["name"]

                    arguments = json.loads(
                        function["arguments"]
                    )

                    print(
                        f"[TOOL] {name} "
                        f"{arguments}"
                    )

                    result = execute_tool(
                        name,
                        arguments
                    )

                    print(
                        f"[RESULT] {str(result)[:500]}"
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result
                    })

                continue

            # ------------------------------------------------
            # NORMAL RESPONSE
            # ------------------------------------------------

            answer = message.get("content", "")

            print("\nObsidian AI:")
            print(answer)
            print()

            break

    except Exception as e:

        print("\nERROR:")
        print(e)
        print()

        if messages and messages[-1].get("role") == "user":
            messages.pop()
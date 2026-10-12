import os
import json
import subprocess
from pathlib import Path

import requests

from memory_system import MemorySystem
from audit_log import AuditLog
from web_tools import fetch_url, web_search
from killswitch import is_killed, killswitch_path
from llm_client import call_model, models_from_env, build_tool_messages


# ============================================================
# OBSIDIAN AI — CONTROLLED CODING AGENT
# ============================================================

API_KEY = os.getenv("OPENROUTER_API_KEY")
URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL = "minimax/minimax-m2.7"

# Fallback chain: first model is tried first. To add fallbacks, set the
# environment variable OBSIDIAN_MODELS to a comma-separated list.
MODELS = models_from_env([MODEL])

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = BASE_DIR / "workspace"

WORKSPACE.mkdir(exist_ok=True)

memory = MemorySystem(WORKSPACE)
audit = AuditLog(WORKSPACE / "logs")


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
            env=scrubbed_env(os.environ),
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

from action_gate import classify_command, scrubbed_env


def gated_run_command(command: str) -> str:
    """
    Action-gated wrapper around run_command. This is what the
    tool executor calls — run_command() itself is unchanged and
    still does the actual execution once cleared.
    """

    tier, reason = classify_command(command, workspace_path=str(WORKSPACE))

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
            "name": "fetch_url",
            "description": "Fetch a real, live web page or API endpoint and read its text content. Use this to verify facts, check real API documentation, or read a page the user gives you — instead of guessing from memory. Cannot search the web or discover URLs, only read a URL it's given. Refuses internal/private network addresses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL to fetch, including https:// or http://"
                    }
                },
                "required": ["url"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web to find and discover relevant URLs, then use fetch_url to read the most promising one. IMPORTANT LIMITATION: this only searches a small, curated set of reference sites (Wikipedia, GitHub, Stack Overflow, MDN, Python/NASA/Open-Meteo docs, etc.) configured in advance — it is NOT unrestricted whole-web search. If nothing relevant turns up, say so plainly rather than guessing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query, kept short and specific"
                    }
                },
                "required": ["query"]
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

    tier = None
    success = True
    output = ""

    if is_killed(BASE_DIR):
        output = (
            "KILLED: Emergency kill switch is active. No tool will execute "
            f"until {killswitch_path(BASE_DIR)} is removed."
        )
        audit.record(tool_name=name, arguments=arguments, success=False, output=output, tier="KILLED")
        return output

    try:

        if name == "list_files":
            output = list_files(arguments["path"])

        elif name == "read_file":
            output = read_file(arguments["path"])

        elif name == "write_file":
            output = write_file(
                arguments["path"],
                arguments["content"]
            )

        elif name == "create_directory":
            output = create_directory(arguments["path"])

        elif name == "run_command":
            tier, _ = classify_command(arguments["command"], workspace_path=str(WORKSPACE))
            output = gated_run_command(arguments["command"])
            if output.startswith("BLOCKED:") or output.startswith("DENIED:"):
                success = False

        elif name == "fetch_url":
            output = fetch_url(arguments["url"])
            if output.startswith("BLOCKED:") or output.startswith("Error"):
                success = False

        elif name == "web_search":
            output = web_search(arguments["query"])
            if output.startswith("Error") or output.startswith("Search API error") or output.startswith("Search not configured"):
                success = False

        elif name == "remember":
            mem_id = memory.remember(
                arguments["content"],
                importance=arguments.get("importance", 3)
            )
            output = f"Remembered (id={mem_id}): {arguments['content']}"

        elif name == "recall_memory":
            output = memory.recall(arguments["query"])

        else:
            output = f"Unknown tool: {name}"
            success = False

    except Exception as e:
        output = f"Tool error: {e}"
        success = False

    audit.record(
        tool_name=name,
        arguments=arguments,
        success=success,
        output=output,
        tier=tier
    )

    return output


# ============================================================
# API
# ============================================================

def ask_model(messages):

    data, model_used = call_model(
        messages,
        TOOLS,
        api_key=API_KEY,
        url=URL,
        models=MODELS,
    )

    if model_used != MODELS[0]:
        print(f"[MODEL] Primary model unavailable - answered by {model_used}")

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
print(f"                    {MODELS[0]}")
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

    if is_killed(BASE_DIR):
        print(
            f"\n[KILL SWITCH ACTIVE] Found {killswitch_path(BASE_DIR)} — "
            "halting immediately. Delete that file to resume."
        )
        break

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

                messages.extend(
                    build_tool_messages(tool_calls, execute_tool)
                )

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
"""
Tool Executor - Safe tool execution wrapper

Phase 3: Executes LLM-decided tools with error handling.
Phase 5: Three-tier Action Gate (BLOCK / APPROVAL / ALLOW) before execution.
Phase 6: Every action is recorded to a durable audit log.
Wraps the existing ToolRegistry with additional safety features.
"""

from typing import Dict, Any, List, Optional, Callable
import re
import time
import threading
from dataclasses import dataclass

from agent_core.audit_log import AuditLog


@dataclass
class ExecutionResult:
    """Result of a tool execution"""
    success: bool
    output: str
    tool_name: str
    duration: float
    error: Optional[str] = None


BLOCKED_COMMAND_PATTERNS = [
    r"\bformat\s+[a-zA-Z]:",
    r"\bdiskpart\b",
    r"\bshutdown\b",
    r"\bdel\s+/s\s+/q\s+[a-zA-Z]:\\",
    r"\breg\s+delete\b",
    r"\bnet\s+user\b",
    r":\(\)\{.*\};:",
]

APPROVAL_COMMAND_PATTERNS = [
    r"\bdel\b",
    r"\berase\b",
    r"\brd\b",
    r"\brmdir\b",
    r"\brm\b",
    r"\bgit\s+push\s+.*--force",
    r"\bgit\s+reset\s+--hard",
    r"\bgit\s+clean\s+-[a-z]*f",
    r">\s*[a-zA-Z]:\\",
]

_BLOCKED_RE = re.compile("|".join(BLOCKED_COMMAND_PATTERNS), re.IGNORECASE)
_APPROVAL_RE = re.compile("|".join(APPROVAL_COMMAND_PATTERNS), re.IGNORECASE)


def default_confirm(action: str, action_input: Dict[str, Any], reason: str) -> bool:
    print(f"\n[APPROVAL REQUIRED] {reason}")
    print(f"  Tool: {action}")
    print(f"  Args: {action_input}")
    answer = input("  Proceed? [y/N]: ").strip().lower()
    return answer == "y"


class ToolExecutor:
    """
    Executes tools chosen by LLM safely, through a three-tier Action Gate
    (BLOCK / APPROVAL / ALLOW), with every action recorded to an audit log.
    """

    def __init__(
        self,
        tool_registry,
        default_timeout: int = 30,
        confirm_callback: Optional[Callable[[str, Dict[str, Any], str], bool]] = None,
        audit_log: Optional[AuditLog] = None
    ):
        self.registry = tool_registry
        self.default_timeout = default_timeout
        self.confirm_callback = confirm_callback or default_confirm
        self.audit = audit_log or AuditLog()
        self._execution_count = 0
        self._total_duration = 0.0
        self._cancelled_count = 0
        self._blocked_count = 0

    def _gate_check(self, action: str, action_input: Dict[str, Any]):
        if action != "command":
            return ("allow", None)
        command_str = str(action_input.get("command", ""))
        if _BLOCKED_RE.search(command_str):
            return ("block", f"Blocked: this command is never permitted: {command_str}")
        if _APPROVAL_RE.search(command_str):
            return ("approval", f"This command looks destructive/irreversible: {command_str}")
        return ("allow", None)

    def execute(
        self,
        action: str,
        action_input: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> str:
        timeout = timeout or self.default_timeout
        start_time = time.time()
        self._execution_count += 1

        if not self.can_execute(action):
            available = self.get_available_tools()
            msg = f"Error: Unknown tool '{action}'. Available tools: {', '.join(available)}"
            self.audit.record(action, action_input, tier="error", success=False, error=msg, duration=0.0)
            return msg

        tier, reason = self._gate_check(action, action_input)

        if tier == "block":
            self._blocked_count += 1
            duration = time.time() - start_time
            self._total_duration += duration
            msg = f"Blocked by Action Gate: {reason}"
            self.audit.record(action, action_input, tier="block", success=False, error=msg, duration=duration)
            return msg

        if tier == "approval":
            approved = self.confirm_callback(action, action_input, reason)
            if not approved:
                self._cancelled_count += 1
                duration = time.time() - start_time
                self._total_duration += duration
                msg = f"Cancelled by user: {reason}"
                self.audit.record(action, action_input, tier="cancelled", success=False, error=msg, duration=duration)
                return msg

        try:
            result = self._execute_with_timeout(action, action_input, timeout)
            duration = time.time() - start_time
            self._total_duration += duration
            self.audit.record(action, action_input, tier=tier, success=True, output=result, duration=duration)
            if duration > 5:
                return f"[Slow: {duration:.1f}s] {result}"
            return result

        except TimeoutError:
            duration = time.time() - start_time
            self._total_duration += duration
            msg = f"Error: Tool '{action}' timed out after {timeout}s"
            self.audit.record(action, action_input, tier=tier, success=False, error=msg, duration=duration)
            return msg

        except TypeError as e:
            duration = time.time() - start_time
            self._total_duration += duration
            msg = f"Error: Invalid arguments for '{action}': {str(e)}"
            self.audit.record(action, action_input, tier=tier, success=False, error=msg, duration=duration)
            return msg

        except Exception as e:
            duration = time.time() - start_time
            self._total_duration += duration
            msg = f"Error executing {action}: {str(e)}"
            self.audit.record(action, action_input, tier=tier, success=False, error=msg, duration=duration)
            return msg

    def execute_result(
        self,
        action: str,
        action_input: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        timeout = timeout or self.default_timeout
        start_time = time.time()

        if not self.can_execute(action):
            duration = time.time() - start_time
            err = f"Unknown tool '{action}'"
            self.audit.record(action, action_input, tier="error", success=False, error=err, duration=duration)
            return ExecutionResult(success=False, output="", tool_name=action, duration=duration, error=err)

        tier, reason = self._gate_check(action, action_input)

        if tier == "block":
            self._blocked_count += 1
            duration = time.time() - start_time
            err = f"Blocked by Action Gate: {reason}"
            self.audit.record(action, action_input, tier="block", success=False, error=err, duration=duration)
            return ExecutionResult(success=False, output="", tool_name=action, duration=duration, error=err)

        if tier == "approval":
            approved = self.confirm_callback(action, action_input, reason)
            if not approved:
                self._cancelled_count += 1
                duration = time.time() - start_time
                err = f"Cancelled by user: {reason}"
                self.audit.record(action, action_input, tier="cancelled", success=False, error=err, duration=duration)
                return ExecutionResult(success=False, output="", tool_name=action, duration=duration, error=err)

        try:
            output = self._execute_with_timeout(action, action_input, timeout)
            duration = time.time() - start_time
            self.audit.record(action, action_input, tier=tier, success=True, output=output, duration=duration)
            return ExecutionResult(success=True, output=output, tool_name=action, duration=duration)

        except TimeoutError:
            duration = time.time() - start_time
            err = f"Timed out after {timeout}s"
            self.audit.record(action, action_input, tier=tier, success=False, error=err, duration=duration)
            return ExecutionResult(success=False, output="", tool_name=action, duration=duration, error=err)

        except Exception as e:
            duration = time.time() - start_time
            self.audit.record(action, action_input, tier=tier, success=False, error=str(e), duration=duration)
            return ExecutionResult(success=False, output="", tool_name=action, duration=duration, error=str(e))

    def _execute_with_timeout(self, action: str, action_input: Dict[str, Any], timeout: int) -> str:
        result = [None]
        error = [None]

        def target():
            try:
                result[0] = self.registry.execute(action, **action_input)
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise TimeoutError(f"Execution exceeded {timeout}s")
        if error[0]:
            raise error[0]
        return str(result[0])

    def can_execute(self, action: str) -> bool:
        return action in [t["name"] for t in self.registry.list_tools()]

    def get_available_tools(self) -> List[str]:
        return [t["name"] for t in self.registry.list_tools()]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_executions": self._execution_count,
            "total_duration": self._total_duration,
            "avg_duration": self._total_duration / max(1, self._execution_count),
            "cancelled": self._cancelled_count,
            "blocked": self._blocked_count
        }

    def reset_stats(self):
        self._execution_count = 0
        self._total_duration = 0.0
        self._cancelled_count = 0
        self._blocked_count = 0

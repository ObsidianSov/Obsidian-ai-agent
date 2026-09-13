"""
Obsidian Tool Executor
M0.3: Single execution authority.

Flow:
    Reasoning -> Executor -> Action Gate -> Tool
                           -> Audit

The Executor is the only component responsible for deciding whether a
tool action may actually execute.
"""

from typing import Dict, Any, List, Optional, Callable
import time
import threading
from dataclasses import dataclass
from pathlib import Path

from action_gate import classify_command
from audit_log import AuditLog


@dataclass
class ExecutionResult:
    """Structured result of a tool execution."""
    success: bool
    output: str
    tool_name: str
    duration: float
    error: Optional[str] = None


def default_confirm(
    action: str,
    action_input: Dict[str, Any],
    reason: str
) -> bool:
    print(f"\n[APPROVAL REQUIRED] {reason}")
    print(f"  Tool: {action}")
    print(f"  Args: {action_input}")
    answer = input("  Proceed? [y/N]: ").strip().lower()
    return answer == "y"


class ToolExecutor:
    """
    Single execution authority for Obsidian.

    Every tool action passes through:
        1. Tool existence check
        2. Canonical Action Gate
        3. Optional user approval
        4. Tool execution
        5. Canonical audit logging
    """

    def __init__(
        self,
        tool_registry,
        workspace: Optional[Path] = None,
        default_timeout: int = 30,
        confirm_callback: Optional[
            Callable[[str, Dict[str, Any], str], bool]
        ] = None,
        audit_log: Optional[AuditLog] = None
    ):
        self.registry = tool_registry
        self.workspace = Path(workspace or self._default_workspace()).resolve()
        self.default_timeout = default_timeout
        self.confirm_callback = confirm_callback or default_confirm

        # Canonical audit log: workspace/logs/audit_log.jsonl
        self.audit = audit_log or AuditLog(self.workspace / "logs")

        self._execution_count = 0
        self._total_duration = 0.0
        self._cancelled_count = 0
        self._blocked_count = 0

    @staticmethod
    def _default_workspace() -> Path:
        import os

        configured = os.environ.get("OBSIDIAN_WORKSPACE")
        if configured:
            return Path(configured)

        return Path.cwd() / "workspace"

    def _gate_check(
        self,
        action: str,
        action_input: Dict[str, Any]
    ):
        """
        Use the ONE canonical Action Gate.

        Non-command tools are currently allowed by the command gate.
        Command tools are classified using the workspace boundary too.
        """
        if action != "command":
            return ("allow", None)

        command_str = str(action_input.get("command", ""))

        return classify_command(
            command_str,
            workspace_path=self.workspace
        )

    def _record(
        self,
        action: str,
        action_input: Dict[str, Any],
        tier: str,
        success: bool,
        duration: float,
        output: str = "",
        error: Optional[str] = None
    ):
        """Audit logging must never break tool execution."""
        try:
            self.audit.record(
                action,
                action_input,
                success=success,
                output=output,
                tier=tier,
                error=error,
                duration=duration
            )
        except TypeError:
            # Compatibility with the older root AuditLog signature.
            try:
                self.audit.record(
                    action,
                    action_input,
                    success,
                    output,
                    tier
                )
            except Exception:
                pass
        except Exception:
            pass

    def _prepare(
        self,
        action: str,
        action_input: Dict[str, Any],
        start_time: float
    ):
        """Validate tool existence and apply the canonical Action Gate."""

        if not self.can_execute(action):
            available = self.get_available_tools()
            msg = (
                f"Error: Unknown tool '{action}'. "
                f"Available tools: {', '.join(available)}"
            )
            duration = time.time() - start_time
            self._record(
                action,
                action_input,
                "error",
                False,
                duration,
                error=msg
            )
            return False, None, msg

        tier, reason = self._gate_check(action, action_input)

        if tier == "block":
            self._blocked_count += 1
            duration = time.time() - start_time
            msg = f"Blocked by Action Gate: {reason}"
            self._record(
                action,
                action_input,
                "block",
                False,
                duration,
                error=msg
            )
            return False, tier, msg

        if tier == "approval":
            approved = self.confirm_callback(
                action,
                action_input,
                reason
            )

            if not approved:
                self._cancelled_count += 1
                duration = time.time() - start_time
                msg = f"Cancelled by user: {reason}"
                self._record(
                    action,
                    action_input,
                    "cancelled",
                    False,
                    duration,
                    error=msg
                )
                return False, tier, msg

        return True, tier, None

    def _run(
        self,
        action: str,
        action_input: Dict[str, Any],
        timeout: int
    ) -> str:
        """Execute the actual registry operation with a timeout."""

        result = [None]
        error = [None]

        def target():
            try:
                result[0] = self.registry.execute(
                    action,
                    **action_input
                )
            except Exception as exc:
                error[0] = exc

        thread = threading.Thread(
            target=target,
            name=f"obsidian-tool-{action}",
            daemon=True
        )

        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise TimeoutError(
                f"Execution exceeded {timeout}s"
            )

        if error[0] is not None:
            raise error[0]

        return str(result[0])

    def execute(
        self,
        action: str,
        action_input: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> str:
        """Execute a tool and return its textual result."""

        timeout = timeout or self.default_timeout
        start_time = time.time()
        self._execution_count += 1

        allowed, tier, early_result = self._prepare(
            action,
            action_input,
            start_time
        )

        if not allowed:
            return early_result

        try:
            output = self._run(
                action,
                action_input,
                timeout
            )

            duration = time.time() - start_time
            self._total_duration += duration

            self._record(
                action,
                action_input,
                tier,
                True,
                duration,
                output=output
            )

            if duration > 5:
                return f"[Slow: {duration:.1f}s] {output}"

            return output

        except TimeoutError:
            duration = time.time() - start_time
            self._total_duration += duration

            msg = (
                f"Error: Tool '{action}' "
                f"timed out after {timeout}s"
            )

            self._record(
                action,
                action_input,
                tier,
                False,
                duration,
                error=msg
            )

            return msg

        except TypeError as exc:
            duration = time.time() - start_time
            self._total_duration += duration

            msg = (
                f"Error: Invalid arguments for "
                f"'{action}': {exc}"
            )

            self._record(
                action,
                action_input,
                tier,
                False,
                duration,
                error=msg
            )

            return msg

        except Exception as exc:
            duration = time.time() - start_time
            self._total_duration += duration

            msg = f"Error executing {action}: {exc}"

            self._record(
                action,
                action_input,
                tier,
                False,
                duration,
                error=msg
            )

            return msg

    def execute_result(
        self,
        action: str,
        action_input: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """Structured version of execute()."""

        timeout = timeout or self.default_timeout
        start_time = time.time()

        allowed, tier, early_result = self._prepare(
            action,
            action_input,
            start_time
        )

        if not allowed:
            duration = time.time() - start_time

            return ExecutionResult(
                success=False,
                output="",
                tool_name=action,
                duration=duration,
                error=early_result
            )

        try:
            output = self._run(
                action,
                action_input,
                timeout
            )

            duration = time.time() - start_time
            self._execution_count += 1
            self._total_duration += duration

            self._record(
                action,
                action_input,
                tier,
                True,
                duration,
                output=output
            )

            return ExecutionResult(
                success=True,
                output=output,
                tool_name=action,
                duration=duration
            )

        except Exception as exc:
            duration = time.time() - start_time
            self._execution_count += 1
            self._total_duration += duration

            error = str(exc)

            self._record(
                action,
                action_input,
                tier,
                False,
                duration,
                error=error
            )

            return ExecutionResult(
                success=False,
                output="",
                tool_name=action,
                duration=duration,
                error=error
            )

    def can_execute(self, action: str) -> bool:
        return action in [
            tool["name"]
            for tool in self.registry.list_tools()
        ]

    def get_available_tools(self) -> List[str]:
        return [
            tool["name"]
            for tool in self.registry.list_tools()
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_executions": self._execution_count,
            "total_duration": self._total_duration,
            "avg_duration": (
                self._total_duration /
                max(1, self._execution_count)
            ),
            "cancelled": self._cancelled_count,
            "blocked": self._blocked_count
        }

    def reset_stats(self):
        self._execution_count = 0
        self._total_duration = 0.0
        self._cancelled_count = 0
        self._blocked_count = 0

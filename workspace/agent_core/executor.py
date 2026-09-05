"""
Tool Executor - Safe tool execution wrapper

Phase 3: Executes LLM-decided tools with error handling.
Wraps the existing ToolRegistry with additional safety features.
"""

from typing import Dict, Any, List, Optional
import time
import threading
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result of a tool execution"""
    success: bool
    output: str
    tool_name: str
    duration: float
    error: Optional[str] = None


class ToolExecutor:
    """
    Executes tools chosen by LLM safely.
    
    Features:
    - Timeout support per execution
    - Error handling and recovery
    - Execution time tracking
    - Tool validation
    
    Usage:
        executor = ToolExecutor(tool_registry)
        result = executor.execute("file_write", {"path": "test.txt", "content": "hi"})
        
        if result.success:
            print(result.output)
        else:
            print(f"Error: {result.error}")
    """
    
    def __init__(
        self,
        tool_registry,
        default_timeout: int = 30
    ):
        """
        Initialize executor.
        
        Args:
            tool_registry: ToolRegistry instance
            default_timeout: Default timeout for tool execution (seconds)
        """
        self.registry = tool_registry
        self.default_timeout = default_timeout
        self._execution_count = 0
        self._total_duration = 0.0
    
    def execute(
        self,
        action: str,
        action_input: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> str:
        """
        Execute a tool and return observation string.
        
        Args:
            action: Tool name
            action_input: Tool arguments
            timeout: Optional override for default timeout
            
        Returns:
            Observation string (success or error message)
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()
        self._execution_count += 1
        
        # Validate tool exists
        if not self.can_execute(action):
            available = self.get_available_tools()
            return f"Error: Unknown tool '{action}'. Available tools: {', '.join(available)}"
        
        # Execute with timeout
        try:
            result = self._execute_with_timeout(
                action,
                action_input,
                timeout
            )
            
            duration = time.time() - start_time
            self._total_duration += duration
            
            # Add timing info for slow operations
            if duration > 5:
                return f"[Slow: {duration:.1f}s] {result}"
            
            return result
            
        except TimeoutError:
            duration = time.time() - start_time
            self._total_duration += duration
            return f"Error: Tool '{action}' timed out after {timeout}s"
            
        except TypeError as e:
            # Wrong arguments
            duration = time.time() - start_time
            self._total_duration += duration
            return f"Error: Invalid arguments for '{action}': {str(e)}"
            
        except Exception as e:
            # Any other error
            duration = time.time() - start_time
            self._total_duration += duration
            return f"Error executing {action}: {str(e)}"
    
    def execute_result(
        self,
        action: str,
        action_input: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute a tool and return detailed result.
        
        Args:
            action: Tool name
            action_input: Tool arguments  
            timeout: Optional override for default timeout
            
        Returns:
            ExecutionResult with full details
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()
        
        # Validate tool exists
        if not self.can_execute(action):
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                output="",
                tool_name=action,
                duration=duration,
                error=f"Unknown tool '{action}'"
            )
        
        # Execute
        try:
            output = self._execute_with_timeout(action, action_input, timeout)
            duration = time.time() - start_time
            
            return ExecutionResult(
                success=True,
                output=output,
                tool_name=action,
                duration=duration
            )
            
        except TimeoutError:
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                output="",
                tool_name=action,
                duration=duration,
                error=f"Timed out after {timeout}s"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                output="",
                tool_name=action,
                duration=duration,
                error=str(e)
            )
    
    def _execute_with_timeout(
        self,
        action: str,
        action_input: Dict[str, Any],
        timeout: int
    ) -> str:
        """Execute tool with timeout using threading"""
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
            # Thread is still running, execution timed out
            raise TimeoutError(f"Execution exceeded {timeout}s")
        
        if error[0]:
            raise error[0]
        
        return str(result[0])
    
    def can_execute(self, action: str) -> bool:
        """Check if tool exists"""
        return action in [t["name"] for t in self.registry.list_tools()]
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return [t["name"] for t in self.registry.list_tools()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return {
            "total_executions": self._execution_count,
            "total_duration": self._total_duration,
            "avg_duration": self._total_duration / max(1, self._execution_count)
        }
    
    def reset_stats(self):
        """Reset execution statistics"""
        self._execution_count = 0
        self._total_duration = 0.0

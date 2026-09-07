"""
LLM-ReAct Engine - Universal Tool Calling

Phase 2 Updated: Works with both native function calling and JSON fallback.
Automatically uses the best available method.

M0.1 Fix: Every LLM-generated tool call is evaluated by the Action Gate
BEFORE execution. Gate implementation reused from executor.py.

M0.2 Fix: LLM retains conversation context across iterations via:
- reset=False to keep _messages accumulated
- add_tool_result() to feed tool results back to LLM
- Proper conversation flow without redundant message building

M0.3 Fix: Simple conversational requests (hi, hello, casual questions)
are handled directly without unnecessary tool calls.
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import json
import os
import re

from agent_core.memory import MemorySystem
from agent_core.llm import (
    OpenRouterProvider,
    ToolDefinition,
    ToolCall,
    LLMResponse,
    JSONParser
)


# M0.1: Action Gate patterns (reused from executor.py)
_BLOCKED_COMMAND_PATTERNS = [
    r"\bformat\s+[a-zA-Z]:",
    r"\bdiskpart\b",
    r"\bshutdown\b",
    r"\bdel\s+/s\s+/q\s+[a-zA-Z]:\\",
    r"\breg\s+delete\b",
    r"\bnet\s+user\b",
    r":\(\)\{.*\};:",
]

_APPROVAL_COMMAND_PATTERNS = [
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

_BLOCKED_RE = re.compile("|".join(_BLOCKED_COMMAND_PATTERNS), re.IGNORECASE)
_APPROVAL_RE = re.compile("|".join(_APPROVAL_COMMAND_PATTERNS), re.IGNORECASE)


def gate_check(action: str, action_input: Dict[str, Any]) -> tuple:
    """
    M0.1: Action Gate check - evaluates if a tool call should proceed.
    Returns (tier, reason) where:
      - ("block", reason): Never permitted
      - ("approval", reason): Requires user confirmation
      - ("allow", None): Can proceed
    """
    if action != "command":
        return ("allow", None)
    
    command_str = str(action_input.get("command", ""))
    
    if _BLOCKED_RE.search(command_str):
        return ("block", f"Blocked: this command is never permitted: {command_str}")
    
    if _APPROVAL_RE.search(command_str):
        return ("approval", f"This command looks destructive/irreversible: {command_str}")
    
    return ("allow", None)


@dataclass
class Decision:
    """Represents LLM's decision"""
    action: str  # Tool name or "final"
    action_input: Optional[Dict] = None
    content: Optional[str] = None
    question: Optional[str] = None
    raw_response: Optional[LLMResponse] = None


@dataclass
class Observation:
    """Represents a tool execution result"""
    step: int
    tool_name: str
    arguments: Dict[str, Any]
    result: str
    success: bool = True


class UniversalReActEngine:
    """
    LLM-driven ReAct that works with both:
    1. Native function calling (if model supports it)
    2. JSON parsing fallback (for other models)
    
    M0.1: All tool calls pass through Action Gate before execution.
    M0.2: LLM retains conversation context across iterations.
    M0.3: Simple requests handled directly without tools.
    """
    
    def __init__(
        self,
        llm_provider: OpenRouterProvider,
        max_steps: int = 10,
        system_prompt: Optional[str] = None
    ):
        self.llm = llm_provider
        self.max_steps = max_steps
        self.system_prompt = system_prompt or self._default_system_prompt()
        
        # State
        self.task: str = ""
        self.tools: List[ToolDefinition] = []
        self.context: Dict = {}
        self.memory: Optional[MemorySystem] = None
        self.observations: List[Observation] = []
        self._is_complete: bool = False
        self._current_step: int = 0
        self._tool_executor: Optional[Callable] = None
        self._gate_callback: Optional[Callable] = None  # M0.1: For custom approval handling
        self._tool_call_id_counter: int = 0
    
    def set_gate_callback(self, callback: Callable[[str, Dict, str], bool]):
        """
        M0.1: Set a callback for approval-tier actions.
        Called with (action, action_input, reason), returns True if approved.
        If not set, approval-tier actions are blocked.
        """
        self._gate_callback = callback
    
    def reset(
        self,
        task: str,
        tools: List[Dict],
        context: Dict = None,
        memory: MemorySystem = None
    ):
        """Initialize for a new task"""
        self.task = task
        self.tools = self._convert_tools(tools)
        self.context = context or {}
        self.memory = memory
        self.observations = []
        self._is_complete = False
        self._current_step = 0
        self._tool_call_id_counter = 0
        
        # Reset LLM conversation for new task
        self.llm.reset_conversation()
    
    def run(self, task: Optional[str] = None) -> str:
        """
        Run the full ReAct loop until completion.
        Handles both native function calling and JSON fallback modes.
        
        M0.2: Uses reset=False to maintain conversation context.
        Tool results are fed back via add_tool_result() so LLM
        knows what happened in previous steps.
        M0.3: Simple conversational requests are handled directly.
        """
        if task:
            self.task = task
        
        # M0.3: Check if task is trivially answerable without tools
        trivial_result = self._check_trivial_task(self.task)
        if trivial_result:
            return trivial_result
        
        # Build initial prompt
        tool_instructions = self._build_tool_instructions()
        initial_prompt = f"{tool_instructions}\n\nTask: {self.task}"
        
        # M0.2: Reset=False so conversation accumulates across iterations
        while not self._is_complete and self._current_step < self.max_steps:
            self._current_step += 1
            
            # Get LLM response
            try:
                response = self.llm.complete_with_tools(
                    prompt=self._build_step_prompt(),
                    tools=self.tools,
                    system_prompt=self.system_prompt,
                    reset=False  # M0.2: Keep conversation history
                )
            except Exception as e:
                return f"Error communicating with LLM: {str(e)}"
            
            # Process response
            result = self._process_response(response)
            
            if result is None:
                # No action needed, we're done
                self._is_complete = True
                return response.content or "No response"
            
            if result == "STOP":
                self._is_complete = True
                return response.content or "Done"
            
            if result == "CONTINUE":
                # More steps needed, loop continues with accumulated context
                continue
        
        # Max steps reached
        return self._summarize()
    
    def _check_trivial_task(self, task: str) -> Optional[str]:
        """
        M0.3: Check if task is trivially answerable without tools.
        Returns a direct response if no tools are needed, otherwise None.
        """
        if not task:
            return None
            
        task_lower = task.lower().strip()
        
        # Greetings - answer directly
        greeting_patterns = [
            r"^(hi|hello|hey|hi!|hello!|hey!|hi\?|hello\?|hey\?|howdy|greetings)$",
            r"^(good morning|good afternoon|good evening|good night)$",
            r"^what'?s up\??$",
            r"^how are you(\?|)?$",
            r"^how'?s it going(\?|)?$",
        ]
        
        for pattern in greeting_patterns:
            if re.match(pattern, task_lower):
                return self._generate_greeting_response(task)
        
        # Simple questions that don't need tools
        simple_question_patterns = [
            r"^(yes|no|okay|ok|sure|yeah|yep|nope|nah)$",
            r"^thank(s| you)\??$",
            r"^(thanks|thank you)$",
            r"^bye(\?|)$",
            r"^(see you|talk later|catch you)$",
            r"^what can you do(\?|)$",
            r"^who are you(\?|)$",
        ]
        
        for pattern in simple_question_patterns:
            if re.match(pattern, task_lower):
                return self._generate_simple_response(task)
        
        return None
    
    def _generate_greeting_response(self, task: str) -> str:
        """M0.3: Generate a greeting response without tools."""
        task_lower = task.lower().strip()
        
        if task_lower in ["hi", "hello", "hey", "hi!", "hello!", "hey!", "hi?", "hello?", "hey?", "howdy", "greetings"]:
            return "Hi! I'm Obsidian, your AI coding assistant. How can I help you today?"
        
        if task_lower in ["good morning", "good afternoon", "good evening", "good night"]:
            time_greeting = task_lower.replace("good ", "").title()
            return f"Good {time_greeting}! I'm Obsidian, your AI coding assistant. What can I help you with?"
        
        if task_lower in ["what's up", "whats up", "what's up?", "whats up?"]:
            return "Not much! I'm here and ready to help. What would you like to work on?"
        
        if task_lower in ["how are you", "how are you?", "how's it going", "how's it going?"]:
            return "I'm doing well, thanks for asking! I'm here and ready to help with coding tasks, file operations, or anything else you need."
        
        return f"Hello! I'm Obsidian, your AI coding assistant. How can I help you?"
    
    def _generate_simple_response(self, task: str) -> str:
        """M0.3: Generate a simple response without tools."""
        task_lower = task.lower().strip()
        
        if task_lower in ["yes", "yeah", "yep", "sure", "okay", "ok"]:
            return "Great! What would you like me to help you with?"
        
        if task_lower in ["no", "nope", "nah"]:
            return "No problem! Let me know if you need anything else."
        
        if task_lower in ["thanks", "thank you", "thank you!"]:
            return "You're welcome! Is there anything else I can help with?"
        
        if task_lower in ["bye", "bye!", "see you", "talk later", "catch you"]:
            return "Goodbye! Feel free to come back anytime you need help."
        
        if task_lower in ["what can you do", "what can you do?", "who are you", "who are you?"]:
            return "I'm Obsidian, an AI coding assistant. I can help you: read and write files, run terminal commands, search the web, and reason through complex tasks step by step. What would you like to work on?"
        
        return "Got it! How can I help you?"
    
    def _process_response(self, response: LLMResponse) -> Optional[str]:
        """
        Process LLM response and execute tool if needed.
        M0.1: ALL tool calls pass through Action Gate BEFORE execution.
        M0.2: Tool results are fed back to LLM via add_tool_result().
        Returns: None (done), "CONTINUE" (need more steps), or "STOP" (done with content)
        """
        # M0.2: Track if we executed any tools this turn
        executed_any = False
        
        # Check for native tool calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if isinstance(tool_call, dict):
                    # JSON fallback mode - convert dict to ToolCall
                    name = tool_call.get("action") or tool_call.get("name", "")
                    args = tool_call.get("action_input") or tool_call.get("arguments", {})
                    tc_id = tool_call.get("id", f"call_{self._tool_call_id_counter}")
                else:
                    name = tool_call.name
                    args = tool_call.arguments
                    tc_id = tool_call.id
                
                self._tool_call_id_counter += 1
                
                # M0.1: Action Gate check BEFORE execution
                tier, reason = gate_check(name, args)
                
                if tier == "block":
                    # Blocked by Action Gate - feed back error and skip
                    self.observations.append(Observation(
                        step=self._current_step,
                        tool_name=name,
                        arguments=args,
                        result=f"Blocked by Action Gate: {reason}",
                        success=False
                    ))
                    self.llm.add_tool_result(tc_id, f"Blocked by Action Gate: {reason}")
                    continue
                
                if tier == "approval":
                    # Approval required - use callback or block
                    if self._gate_callback:
                        approved = self._gate_callback(name, args, reason)
                        if not approved:
                            self.observations.append(Observation(
                                step=self._current_step,
                                tool_name=name,
                                arguments=args,
                                result=f"Cancelled by user: {reason}",
                                success=False
                            ))
                            self.llm.add_tool_result(tc_id, f"Cancelled by user: {reason}")
                            continue
                    else:
                        # No callback set - block by default
                        self.observations.append(Observation(
                            step=self._current_step,
                            tool_name=name,
                            arguments=args,
                            result=f"Blocked by Action Gate (requires approval): {reason}",
                            success=False
                        ))
                        self.llm.add_tool_result(tc_id, f"Blocked by Action Gate (requires approval): {reason}")
                        continue
                
                # tier == "allow" - proceed with execution
                if self._tool_executor:
                    result = self._tool_executor(name, args)
                else:
                    result = f"Would execute {name} with {args}"
                
                # M0.2: Feed result back to LLM conversation
                self.llm.add_tool_result(tc_id, result)
                executed_any = True
                
                # Record observation locally
                self.observations.append(Observation(
                    step=self._current_step,
                    tool_name=name,
                    arguments=args,
                    result=result
                ))
            
            return "CONTINUE"
        
        # Check for final response
        if response.content:
            # Check if it's actually a tool call in JSON format
            try:
                parsed = JSONParser.extract_json(response.content)
                action = parsed.get("action", "")
                
                if action == "final":
                    return "STOP"
                
                if action and action != "final":
                    # It's a tool call, not final
                    args = parsed.get("action_input") or {}
                    tc_id = f"call_{self._tool_call_id_counter}"
                    self._tool_call_id_counter += 1
                    
                    # M0.1: Action Gate check BEFORE execution
                    tier, reason = gate_check(action, args)
                    
                    if tier == "block":
                        self.observations.append(Observation(
                            step=self._current_step,
                            tool_name=action,
                            arguments=args,
                            result=f"Blocked by Action Gate: {reason}",
                            success=False
                        ))
                        self.llm.add_tool_result(tc_id, f"Blocked by Action Gate: {reason}")
                        return "CONTINUE"
                    
                    if tier == "approval":
                        if self._gate_callback:
                            approved = self._gate_callback(action, args, reason)
                            if not approved:
                                self.observations.append(Observation(
                                    step=self._current_step,
                                    tool_name=action,
                                    arguments=args,
                                    result=f"Cancelled by user: {reason}",
                                    success=False
                                ))
                                self.llm.add_tool_result(tc_id, f"Cancelled by user: {reason}")
                                return "CONTINUE"
                        else:
                            self.observations.append(Observation(
                                step=self._current_step,
                                tool_name=action,
                                arguments=args,
                                result=f"Blocked by Action Gate (requires approval): {reason}",
                                success=False
                            ))
                            self.llm.add_tool_result(tc_id, f"Blocked by Action Gate (requires approval): {reason}")
                            return "CONTINUE"
                    
                    # tier == "allow" - proceed with execution
                    if self._tool_executor:
                        result = self._tool_executor(action, args)
                    else:
                        result = f"Would execute {action} with {args}"
                    
                    # M0.2: Feed result back to LLM conversation
                    self.llm.add_tool_result(tc_id, result)
                    executed_any = True
                    
                    self.observations.append(Observation(
                        step=self._current_step,
                        tool_name=action,
                        arguments=args,
                        result=result
                    ))
                    
                    return "CONTINUE"
                    
            except (ValueError, json.JSONDecodeError):
                # Not JSON, treat as final answer
                return "STOP"
        
        # Empty response - we're done
        return "STOP"
    
    def _build_tool_instructions(self) -> str:
        """Build tool usage instructions for the prompt"""
        if not self.tools:
            return ""
        
        lines = ["AVAILABLE TOOLS:"]
        for tool in self.tools:
            name = tool.name
            desc = tool.description
            params = tool.parameters.get("properties", {})
            
            param_parts = []
            for pname, pinfo in params.items():
                ptype = pinfo.get("type", "any")
                pdesc = pinfo.get("description", "")
                param_parts.append(f"{pname}: {ptype}")
                if pdesc:
                    lines.append(f"  - {pname}: {pdesc}")
            
            lines.append(f"- {name}({', '.join(param_parts)}): {desc}")
        
        lines.append("")
        lines.append("IMPORTANT: Only use a tool when the task REQUIRES it.")
        lines.append("Simple greetings, questions, or tasks that can be answered")
        lines.append("from general knowledge should be answered directly.")
        lines.append("")
        lines.append("Use a tool by outputting JSON:")
        lines.append('{"action": "tool_name", "action_input": {"param": "value"}}')
        lines.append("")
        lines.append("When done, output:")
        lines.append('{"action": "final", "content": "your answer"}')
        
        return "\n".join(lines)
    
    def _build_step_prompt(self) -> str:
        """
        Build the user prompt for each step.
        M0.2: Simplified - conversation context is maintained via reset=False,
        so we don't need to repeat all previous observations here.
        The LLM sees the full conversation history.
        M0.3: Added hint to avoid unnecessary tool use.
        """
        prompt = f"Step {self._current_step} of {self.max_steps}."
        
        if self._current_step == 1:
            # First step - include the task
            prompt = f"Task: {self.task}\n\n{prompt}"
        
        # Add hint about context on subsequent steps
        if self._current_step > 1:
            obs_count = len(self.observations)
            prompt += f"\n\nNote: {obs_count} tool result(s) shown in conversation above."
            prompt += "\nIf the task is complete, respond with final answer."
        
        return prompt
    
    def think(self) -> Decision:
        """
        Single step reasoning - call in a loop.
        M0.1: Includes Action Gate check.
        M0.2: Maintains conversation context.
        M0.3: Simple tasks handled directly.
        """
        # M0.3: Check for trivial task first
        trivial_result = self._check_trivial_task(self.task)
        if trivial_result:
            return Decision(
                action="final",
                content=trivial_result
            )
        
        self._current_step += 1
        
        try:
            response = self.llm.complete_with_tools(
                prompt=self._build_step_prompt(),
                tools=self.tools,
                system_prompt=self.system_prompt,
                reset=False  # M0.2: Keep conversation history
            )
        except Exception as e:
            return Decision(
                action="final",
                content=f"Error: {str(e)}"
            )
        
        # Check for native tool calls
        if response.tool_calls:
            tc = response.tool_calls[0]
            if isinstance(tc, dict):
                name = tc.get("action", tc.get("name", ""))
                args = tc.get("action_input") or tc.get("arguments", {})
                tc_id = tc.get("id", f"call_{self._tool_call_id_counter}")
            else:
                name = tc.name
                args = tc.arguments
                tc_id = tc.id
            
            self._tool_call_id_counter += 1
            
            # M0.1: Action Gate check
            tier, reason = gate_check(name, args)
            
            if tier == "block":
                self.llm.add_tool_result(tc_id, f"Blocked by Action Gate: {reason}")
                return Decision(
                    action=name,
                    action_input=args,
                    content=f"Blocked by Action Gate: {reason}",
                    raw_response=response
                )
            
            if tier == "approval":
                if self._gate_callback:
                    approved = self._gate_callback(name, args, reason)
                    if not approved:
                        self.llm.add_tool_result(tc_id, f"Cancelled by user: {reason}")
                        return Decision(
                            action=name,
                            action_input=args,
                            content=f"Cancelled by user: {reason}",
                            raw_response=response
                        )
                else:
                    self.llm.add_tool_result(tc_id, f"Blocked by Action Gate (requires approval): {reason}")
                    return Decision(
                        action=name,
                        action_input=args,
                        content=f"Blocked by Action Gate (requires approval): {reason}",
                        raw_response=response
                    )
            
            # Allow - execute
            if self._tool_executor:
                result = self._tool_executor(name, args)
            else:
                result = f"Would execute {name} with {args}"
            
            # M0.2: Feed result back to LLM
            self.llm.add_tool_result(tc_id, result)
            
            self.observations.append(Observation(
                step=self._current_step,
                tool_name=name,
                arguments=args,
                result=result
            ))
            
            return Decision(
                action=name,
                action_input=args,
                raw_response=response
            )
        
        # Try JSON parsing
        if response.content:
            try:
                parsed = JSONParser.extract_json(response.content)
                action = parsed.get("action", "")
                
                if action == "final":
                    return Decision(
                        action="final",
                        content=parsed.get("content", response.content),
                        raw_response=response
                    )
                
                if action and action != "final":
                    args = parsed.get("action_input", {})
                    tc_id = f"call_{self._tool_call_id_counter}"
                    self._tool_call_id_counter += 1
                    
                    # M0.1: Action Gate check
                    tier, reason = gate_check(action, args)
                    
                    if tier == "block":
                        self.llm.add_tool_result(tc_id, f"Blocked by Action Gate: {reason}")
                        self.observations.append(Observation(
                            step=self._current_step,
                            tool_name=action,
                            arguments=args,
                            result=f"Blocked by Action Gate: {reason}",
                            success=False
                        ))
                        return Decision(
                            action=action,
                            action_input=args,
                            content=f"Blocked by Action Gate: {reason}",
                            raw_response=response
                        )
                    
                    if tier == "approval":
                        if self._gate_callback:
                            approved = self._gate_callback(action, args, reason)
                            if not approved:
                                self.llm.add_tool_result(tc_id, f"Cancelled by user: {reason}")
                                self.observations.append(Observation(
                                    step=self._current_step,
                                    tool_name=action,
                                    arguments=args,
                                    result=f"Cancelled by user: {reason}",
                                    success=False
                                ))
                                return Decision(
                                    action=action,
                                    action_input=args,
                                    content=f"Cancelled by user: {reason}",
                                    raw_response=response
                                )
                        else:
                            self.llm.add_tool_result(tc_id, f"Blocked by Action Gate (requires approval): {reason}")
                            self.observations.append(Observation(
                                step=self._current_step,
                                tool_name=action,
                                arguments=args,
                                result=f"Blocked by Action Gate (requires approval): {reason}",
                                success=False
                            ))
                            return Decision(
                                action=action,
                                action_input=args,
                                content=f"Blocked by Action Gate (requires approval): {reason}",
                                raw_response=response
                            )
                    
                    # Allow - execute
                    if self._tool_executor:
                        result = self._tool_executor(action, args)
                    else:
                        result = f"Would execute {action} with {args}"
                    
                    # M0.2: Feed result back to LLM
                    self.llm.add_tool_result(tc_id, result)
                    
                    self.observations.append(Observation(
                        step=self._current_step,
                        tool_name=action,
                        arguments=args,
                        result=result
                    ))
                    
                    return Decision(
                        action=action,
                        action_input=args,
                        raw_response=response
                    )
            except (ValueError, json.JSONDecodeError):
                pass
        
        # Return as final
        return Decision(
            action="final",
            content=response.content or "No response",
            raw_response=response
        )
    
    def add_observation(self, tool_name: str, arguments: Dict, result: str):
        """Record an observation"""
        self.observations.append(Observation(
            step=self._current_step,
            tool_name=tool_name,
            arguments=arguments,
            result=result
        ))
    
    def is_complete(self) -> bool:
        return self._is_complete
    
    def get_current_step(self) -> bool:
        return self._current_step
    
    def get_summary(self) -> str:
        return self._summarize()
    
    def get_observations(self) -> List[Observation]:
        return self.observations.copy()
    
    def set_tool_executor(self, executor: Callable[[str, Dict], str]):
        """Set custom tool executor"""
        self._tool_executor = executor
    
    def _convert_tools(self, tools: List[Dict]) -> List[ToolDefinition]:
        """Convert ToolRegistry format to ToolDefinition"""
        converted = []
        for tool in tools:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            params = tool.get("params", {})
            
            properties = {}
            required = []
            
            for param_name, param_info in params.items():
                properties[param_name] = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", "")
                }
                required.append(param_name)
            
            converted.append(ToolDefinition(
                name=name,
                description=desc,
                parameters={
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            ))
        
        return converted
    
    def _summarize(self) -> str:
        """Generate summary when max steps reached"""
        if not self.observations:
            return "No actions were completed."
        
        summary = f"Completed {len(self.observations)} step(s):\n"
        for obs in self.observations:
            summary += f"- {obs.tool_name}({obs.arguments}) -> {obs.result[:50]}...\n"
        
        summary += f"\nReached maximum steps ({self.max_steps})."
        return summary
    
    def _default_system_prompt(self) -> str:
        """Default system prompt"""
        return """You are Obsidian, an AI coding assistant.

You have access to tools to perform actions like reading files, writing files, running commands, and searching.

IMPORTANT - Tool Usage Rules:
- Use tools ONLY when the task genuinely requires it (file operations, commands, web searches, etc.)
- For simple greetings like "hi", "hello", "how are you" - respond directly without tools
- For simple questions that can be answered from general knowledge - respond directly
- For "what can you do" or "who are you" - respond directly describing your capabilities
- Think step by step for complex tasks, but don't over-engineer simple requests
- When using a tool, output ONLY the JSON format specified
- When the task is complete, output {"action": "final", "content": "your answer"}"""


# Aliases for compatibility
LLMReActEngine = UniversalReActEngine
ReActEngine = UniversalReActEngine
NativeReActEngine = UniversalReActEngine

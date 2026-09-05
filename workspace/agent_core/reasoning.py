"""
LLM-ReAct Engine - Reasoning + Acting with OpenRouter

Phase 2: Replaces rule-based decision making with LLM-driven reasoning.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import os
import re

from agent_core.memory import MemorySystem


@dataclass
class Decision:
    """Represents LLM's decision after thinking"""
    action: str  # "tool_name" | "final" | "clarify"
    action_input: Optional[Dict] = None  # Tool arguments
    content: Optional[str] = None  # For "final"
    question: Optional[str] = None  # For "clarify"
    raw_thought: Optional[str] = None  # LLM's reasoning text


class LLMReActEngine:
    """
    LLM-driven ReAct implementation.
    Replaces the old _decide_action() pattern matching.
    
    Usage:
        engine = LLMReActEngine(llm_provider=provider)
        engine.reset(task="...", tools=[...], context={})
        
        while not engine.is_complete():
            decision = engine.think()
            if decision.action == "final":
                print(decision.content)
                break
            # Execute tool, then:
            engine.add_observation(tool_result)
    """
    
    def __init__(
        self,
        llm_provider,  # Injected OpenRouterProvider
        max_steps: int = 10,
        max_retries: int = 3
    ):
        self.llm = llm_provider
        self.max_steps = max_steps
        self.max_retries = max_retries
        
        # State
        self.task: str = ""
        self.available_tools: List[Dict] = []
        self.context: Dict = {}
        self.step: int = 0
        self.observations: List[Dict] = []
        self.thought_history: List[Dict] = []
        self._is_complete: bool = False
        self._memory: Optional[MemorySystem] = None
    
    def reset(self, task: str, tools: List[Dict], context: Dict, memory: MemorySystem = None):
        """Initialize or reset for new task"""
        self.task = task
        self.available_tools = tools
        self.context = context
        self.step = 0
        self.observations = []
        self.thought_history = []
        self._is_complete = False
        self._memory = memory
    
    def think(self) -> Decision:
        """
        Think about next action.
        Called each iteration of the ReAct loop.
        """
        self.step += 1
        
        # Build prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_step_prompt()
        
        # Call LLM with retry
        try:
            raw_response = self._call_llm(system_prompt, user_prompt)
        except Exception as e:
            # If LLM fails, return error decision
            return Decision(
                action="final",
                content=f"I encountered an error while reasoning: {str(e)}",
                raw_thought=str(e)
            )
        
        # Parse response
        try:
            decision = self._parse_response(raw_response)
        except Exception as e:
            # If parsing fails, try to recover
            return Decision(
                action="final",
                content=f"I had trouble understanding my own reasoning. Here's what I know: {self._get_summary_text()}",
                raw_thought=f"Parse error: {str(e)}\nRaw: {raw_response[:200]}"
            )
        
        # Record thought
        self.thought_history.append({
            "step": self.step,
            "action": decision.action,
            "thought": decision.raw_thought
        })
        
        # Check if done
        if decision.action == "final":
            self._is_complete = True
        
        return decision
    
    def add_observation(self, observation: str):
        """Add tool result to context for next iteration"""
        last_action = self.thought_history[-1] if self.thought_history else {}
        
        self.observations.append({
            "step": self.step,
            "action": last_action.get("action"),
            "result": observation[:500] if observation else "No result"  # Truncate long outputs
        })
    
    def is_complete(self) -> bool:
        """Check if reasoning is done"""
        return self._is_complete
    
    def get_current_step(self) -> int:
        """Get current step number"""
        return self.step
    
    def get_summary(self) -> str:
        """Get summary when max steps reached"""
        return self._get_summary_text()
    
    def _get_summary_text(self) -> str:
        """Internal summary generation"""
        if not self.observations:
            return "No observations recorded."
        
        summary = f"Completed {len(self.observations)} step(s). Summary:\n"
        for obs in self.observations:
            action = obs.get('action', 'unknown')
            result = obs.get('result', 'No result')
            # Truncate result for summary
            if len(result) > 100:
                result = result[:100] + "..."
            summary += f"- Step {obs['step']}: {action} → {result}\n"
        
        if self.step >= self.max_steps:
            summary += f"\nNote: Reached maximum steps limit ({self.max_steps})."
        
        return summary
    
    # ─────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with tools and instructions"""
        tools_desc = self._format_tools_description()
        context_desc = self._format_context()
        
        return f"""You are Obsidian, an AI agent that reasons step-by-step using tools.

AVAILABLE TOOLS:
{tools_desc}

MEMORY CONTEXT:
{context_desc}

RESPONSE INSTRUCTIONS:
- You MUST output valid JSON only - no additional text
- Think carefully about which tool to use, if any
- If the task is complete, respond with action "final" and your response content
- If you need clarification, respond with action "clarify" and your question
- When using a tool, provide accurate parameters based on the user's request

OUTPUT FORMATS:

Tool action:
{{"action": "tool_name", "action_input": {{"param1": "value1", "param2": "value2"}}}}

Final answer:
{{"action": "final", "content": "Your response to the user here"}}

Request clarification:
{{"action": "clarify", "question": "What specifically do you mean?"}}"""
    
    def _build_step_prompt(self) -> str:
        """Build prompt for current step"""
        prompt = f"""Task: {self.task}

Step {self.step} of {self.max_steps}."""
        
        if self.observations:
            prompt += "\n\nPrevious observations:"
            for obs in self.observations:
                action = obs.get('action', 'unknown')
                result = obs.get('result', 'No result')
                # Truncate for prompt
                if len(result) > 200:
                    result = result[:200] + "..."
                prompt += f"\n- Step {obs['step']}: {action} returned: {result}"
        
        prompt += "\n\nWhat should I do next? Output JSON only."
        return prompt
    
    def _format_tools_description(self) -> str:
        """Format tools for prompt"""
        if not self.available_tools:
            return "No tools available."
        
        lines = []
        for tool in self.available_tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            params = tool.get("params", {})
            
            if params:
                param_parts = []
                for param_name, param_info in params.items():
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "")
                    param_parts.append(f"{param_name}: {param_type}")
                    if param_desc:
                        lines.append(f"  - {param_name}: {param_type} - {param_desc}")
                
                lines.append(f"- {name}({', '.join(param_parts)}): {desc}")
            else:
                lines.append(f"- {name}: {desc}")
        
        return "\n".join(lines)
    
    def _format_context(self) -> str:
        """Format memory/extra context"""
        parts = []
        
        # From memory system
        if self._memory:
            try:
                context = self._memory.get_system_context()
                if context.get("recent_conversation"):
                    parts.append(f"Recent: {context['recent_conversation'][-2:]}")
                if context.get("user_preferences"):
                    parts.append(f"Preferences: {context['user_preferences']}")
            except Exception:
                pass
        
        # From passed context
        if self.context:
            for key, value in self.context.items():
                if key not in ["recent_conversation", "user_preferences"]:
                    if isinstance(value, str) and len(value) < 200:
                        parts.append(f"{key}: {value}")
        
        return "\n".join(parts) if parts else "No context available"
    
    def _call_llm(self, system: str, user: str):
        """Call LLM with retry logic"""
        from agent_core.llm import LLMResponse
        
        for attempt in range(self.max_retries):
            try:
                response = self.llm.complete(user, system_prompt=system)
                if isinstance(response, LLMResponse):
                    return response.content
                return response
            except Exception as e:
                if attempt < self.max_retries - 1:
                    import time
                    wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                    time.sleep(wait_time)
                else:
                    raise LLMError(f"LLM call failed after {self.max_retries} attempts: {e}")
    
    def _parse_response(self, raw: str) -> Decision:
        """Parse LLM JSON response"""
        json_data = self._extract_json(raw)
        
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            # Try to fix common issues
            try:
                # Handle single quotes
                data = json.loads(json_data.replace("'", '"'))
            except json.JSONDecodeError:
                raise ParseError(f"Invalid JSON from LLM: {raw[:200]}")
        
        # Validate and extract
        action = data.get("action", "")
        
        if not action:
            raise ParseError(f"No 'action' field in response: {data}")
        
        if action == "final":
            return Decision(
                action="final",
                content=data.get("content", ""),
                raw_thought=raw
            )
        
        if action == "clarify":
            return Decision(
                action="clarify",
                question=data.get("question", ""),
                raw_thought=raw
            )
        
        # Tool action
        return Decision(
            action=action,
            action_input=data.get("action_input", {}),
            raw_thought=raw
        )
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response text"""
        text = text.strip()
        
        # Handle markdown code blocks
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1)
        
        # Try to find JSON object
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start != -1 and end > start:
            return text[start:end]
        
        # Return original if no braces found
        return text


class LLMError(Exception):
    """LLM-related errors"""
    pass


class ParseError(Exception):
    """Response parsing errors"""
    pass


# Backward compatibility - keep old class name as alias
ReActEngine = LLMReActEngine

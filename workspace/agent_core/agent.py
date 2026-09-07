"""
Agent Orchestrator - Universal Tool Calling with M0.2 Context Integration

Phase 4 Updated: Works with both native function calling and JSON fallback.
M0.1: All LLM-generated tool calls pass through Action Gate before execution.
M0.2: Integrates Identity, Owner Profile, and Grounded Context.
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import json
import os
import sys

try:
    from agent_core.tools import ToolRegistry, tools
    from agent_core.memory import MemorySystem
    from agent_core.reasoning import UniversalReActEngine, LLMReActEngine, gate_check
    from agent_core.executor import ToolExecutor
    from agent_core.llm import (
        OpenRouterProvider,
        ToolDefinition,
        ConfigurationError,
        JSONParser
    )
    # M0.2: Context modules
    from agent_core.identity import AgentIdentity
    from agent_core.owner_profile import OwnerProfileManager
    from agent_core.grounded_context import GroundedContextProvider
    from agent_core.context_injector import ContextInjector, InjectionConfig
except ImportError:
    from tools import ToolRegistry, tools
    from memory import MemorySystem
    from reasoning import UniversalReActEngine, LLMReActEngine, gate_check
    from executor import ToolExecutor
    from llm import OpenRouterProvider, ToolDefinition, ConfigurationError, JSONParser
    # M0.2: Context modules
    from identity import AgentIdentity
    from owner_profile import OwnerProfileManager
    from grounded_context import GroundedContextProvider
    from context_injector import ContextInjector, InjectionConfig


@dataclass
class AgentConfig:
    name: str = "Obsidian"
    max_steps: int = 10
    verbose: bool = True
    store_memory: bool = True
    reflection_enabled: bool = True
    llm_model: Optional[str] = None
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024
    # M0.2: Context settings
    context_enabled: bool = True
    context_max_length: int = 3000


class Agent:
    """
    Main Agent class with universal tool calling and M0.2 context support.
    
    M0.2 adds:
    - Identity: The agent knows who it is
    - Owner Profile: The agent knows about the user
    - Grounded Context: The agent is grounded in reality (time, place, state)
    """
    
    def __init__(self, config: AgentConfig = None, workspace: str = "."):
        self.config = config or AgentConfig()
        self.workspace = workspace
        
        # Initialize components
        self.tools = ToolRegistry()
        self.memory = MemorySystem(workspace)
        self.executor = ToolExecutor(self.tools)
        
        # M0.2: Initialize context system
        self._init_context_system()
        
        # Initialize LLM
        try:
            self.llm = OpenRouterProvider(
                model=self.config.llm_model,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens
            )
            self.llm_available = True
        except ConfigurationError as e:
            print(f"[!] LLM not available: {e}")
            self.llm = None
            self.llm_available = False
        
        # Initialize ReAct engine
        if self.llm:
            self.react = UniversalReActEngine(
                llm_provider=self.llm,
                max_steps=self.config.max_steps,
                system_prompt=self._build_system_prompt()
            )
            self.react.set_tool_executor(self._execute_tool)
            self.react.set_gate_callback(self._gate_approval_callback)
        else:
            self.react = None
    
    def _init_context_system(self):
        """M0.2: Initialize the identity, owner profile, and context system"""
        # Identity
        self.identity = AgentIdentity()
        
        # Owner profile
        self.owner_profile = OwnerProfileManager(
            profile_path=os.path.join(self.workspace, "knowledge/owner.json")
        )
        
        # Grounded context
        self.grounded_context = GroundedContextProvider(
            owner_profile=self.owner_profile,
            memory_system=self.memory,
            workspace=self.workspace
        )
        
        # Context injector
        context_config = InjectionConfig(
            max_context_length=self.config.context_max_length,
            include_identity=True,
            include_owner_profile=True,
            include_time_context=True,
            include_workspace=True,
            include_memory=True,
            include_capabilities=True,
            include_limitations=True,
            include_key_facts=True
        )
        
        self.context_injector = ContextInjector(
            identity=self.identity,
            owner_profile=self.owner_profile,
            grounded_context=self.grounded_context,
            config=context_config
        )
    
    def _gate_approval_callback(self, action: str, action_input: Dict, reason: str) -> bool:
        """Handle approval-tier actions from the Action Gate."""
        return self.executor.confirm_callback(action, action_input, reason)
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with M0.2 context injection"""
        base = f"""You are {self.config.name}, an AI agent with access to tools.

Use tools when you need to read files, write files, run commands, or search.
For simple questions, provide the answer directly.
Think step by step for complex tasks."""
        
        if self.config.context_enabled:
            return self.context_injector.inject_system_prompt(base)
        
        return base
    
    def _build_tool_instructions(self) -> str:
        """Build tool usage instructions"""
        lines = ["\nAVAILABLE TOOLS:"]
        
        for tool in self.tools.list_tools():
            name = tool["name"]
            desc = tool.get("description", "")
            params = tool.get("params", {})
            
            if params:
                param_parts = []
                for pname, pinfo in params.items():
                    ptype = pinfo.get("type", "any")
                    pdesc = pinfo.get("description", "")
                    param_parts.append(f"{pname}: {ptype}")
                    if pdesc:
                        lines.append(f"  - {pname}: {pdesc}")
                
                lines.append(f"- {name}({', '.join(param_parts)}): {desc}")
            else:
                lines.append(f"- {name}: {desc}")
        
        lines.append("\nTo use a tool, output ONLY this JSON:")
        lines.append('{"action": "tool_name", "action_input": {"param": "value"}}')
        lines.append("\nWhen done, output:")
        lines.append('{"action": "final", "content": "your answer"}')
        
        return "\n".join(lines)
    
    def _execute_tool(self, tool_name: str, arguments: Dict) -> str:
        """Execute a tool (M0.1: already gate-checked by reasoning engine)"""
        return self.executor.execute(tool_name, arguments)
    
    def run(self, task: str, context: Dict = None) -> str:
        """Run a task using the ReAct loop"""
        if not self.llm_available:
            return "Error: LLM not available. Set OPENROUTER_API_KEY."
        
        if self.config.verbose:
            print(f"\n[*] {self.config.name} processing: {task}")
        
        self.memory.working.add("user", task)
        self.owner_profile.record_interaction()
        
        available_tools = self.tools.list_tools()
        
        self.react.reset(
            task=task,
            tools=available_tools,
            context=context or {}
        )
        
        result = self.react.run()
        
        self.memory.working.add("assistant", result)
        
        if self.config.store_memory:
            for obs in self.react.get_observations():
                self.memory.remember(
                    f"Tool {obs.tool_name}: {obs.result[:100]}",
                    importance=2
                )
        
        if self.config.verbose:
            preview = result[:200] + "..." if len(result) > 200 else result
            print(f"[OK] {preview}")
        
        return result
    
    def run_with_trace(self, task: str, context: Dict = None) -> tuple:
        """Run task and return (response, trace)"""
        if not self.llm_available:
            return "Error: LLM not available.", []
        
        if self.config.verbose:
            print(f"\n[*] {self.config.name} processing: {task}")
        
        self.memory.working.add("user", task)
        self.owner_profile.record_interaction()
        available_tools = self.tools.list_tools()
        
        self.react.reset(task, available_tools, context or {})
        
        trace = []
        step = 0
        
        # Build tool instructions
        tool_instructions = self._build_tool_instructions()
        system_prompt = self._build_system_prompt() + "\n" + tool_instructions
        
        while step < self.config.max_steps:
            step += 1
            
            # Build prompt for this step
            prompt = f"Task: {task}\n\nStep {step} of {self.config.max_steps}."
            
            # Add previous observations
            observations = self.react.get_observations()
            if observations:
                prompt += "\n\nPrevious results:"
                for obs in observations:
                    result = obs.result[:80] + "..." if len(obs.result) > 80 else obs.result
                    prompt += f"\n- {obs.tool_name}: {result}"
            
            prompt += "\n\nWhat should I do next? Output JSON only."
            
            try:
                response = self.llm.complete_with_tools(
                    prompt=prompt,
                    tools=self.react.tools,
                    system_prompt=system_prompt
                )
            except Exception as e:
                return f"Error: {str(e)}", trace
            
            trace_entry = {"step": step, "response": response}
            
            tool_called = False
            
            if response.tool_calls:
                for tc in response.tool_calls:
                    if isinstance(tc, dict):
                        name = tc.get("action") or tc.get("name", "")
                        args = tc.get("action_input") or tc.get("arguments") or {}
                    else:
                        name = tc.name
                        args = tc.arguments
                    
                    # M0.1: Gate check
                    tier, reason = gate_check(name, args)
                    
                    if tier == "block":
                        trace_entry["tool_call"] = {
                            "name": name,
                            "arguments": args,
                            "result": f"Blocked by Action Gate: {reason}",
                            "blocked": True
                        }
                        self.react.add_observation(name, args, f"Blocked by Action Gate: {reason}")
                        tool_called = True
                        continue
                    
                    if tier == "approval":
                        approved = self._gate_approval_callback(name, args, reason)
                        if not approved:
                            trace_entry["tool_call"] = {
                                "name": name,
                                "arguments": args,
                                "result": f"Cancelled by user: {reason}",
                                "cancelled": True
                            }
                            self.react.add_observation(name, args, f"Cancelled by user: {reason}")
                            tool_called = True
                            continue
                    
                    result = self._execute_tool(name, args)
                    
                    trace_entry["tool_call"] = {
                        "name": name,
                        "arguments": args,
                        "result": result
                    }
                    
                    self.react.add_observation(name, args, result)
                    tool_called = True
            
            elif response.content:
                try:
                    parsed = JSONParser.extract_json(response.content)
                    action = parsed.get("action", "")
                    
                    if action == "final":
                        trace_entry["final"] = parsed.get("content", response.content)
                        self.memory.working.add("assistant", trace_entry["final"])
                        return trace_entry["final"], trace + [trace_entry]
                    
                    if action and action != "final":
                        args = parsed.get("action_input") or {}
                        
                        tier, reason = gate_check(action, args)
                        
                        if tier == "block":
                            trace_entry["tool_call"] = {
                                "name": action,
                                "arguments": args,
                                "result": f"Blocked by Action Gate: {reason}",
                                "blocked": True
                            }
                            self.react.add_observation(action, args, f"Blocked by Action Gate: {reason}")
                            tool_called = True
                        elif tier == "approval":
                            approved = self._gate_approval_callback(action, args, reason)
                            if not approved:
                                trace_entry["tool_call"] = {
                                    "name": action,
                                    "arguments": args,
                                    "result": f"Cancelled by user: {reason}",
                                    "cancelled": True
                                }
                                self.react.add_observation(action, args, f"Cancelled by user: {reason}")
                                tool_called = True
                            else:
                                result = self._execute_tool(action, args)
                                trace_entry["tool_call"] = {
                                    "name": action,
                                    "arguments": args,
                                    "result": result
                                }
                                self.react.add_observation(action, args, result)
                                tool_called = True
                        else:
                            result = self._execute_tool(action, args)
                            trace_entry["tool_call"] = {
                                "name": action,
                                "arguments": args,
                                "result": result
                            }
                            self.react.add_observation(action, args, result)
                            tool_called = True
                        
                except (ValueError, json.JSONDecodeError):
                    self.memory.working.add("assistant", response.content)
                    return response.content, trace + [trace_entry]
            
            if tool_called:
                trace.append(trace_entry)
                continue
            
            if response.content:
                self.memory.working.add("assistant", response.content)
                return response.content, trace + [trace_entry]
            
            break
        
        summary = self.react.get_summary()
        self.memory.working.add("assistant", summary)
        return summary, trace
    
    # === M0.2: Context System Methods ===
    
    def get_identity(self) -> AgentIdentity:
        """Get the agent's identity"""
        return self.identity
    
    def get_owner_profile(self) -> OwnerProfileManager:
        """Get the owner profile manager"""
        return self.owner_profile
    
    def get_grounded_context(self) -> GroundedContextProvider:
        """Get the grounded context provider"""
        return self.grounded_context
    
    def refresh_context(self) -> Dict[str, Any]:
        """Refresh all context and return as dict"""
        ctx = self.grounded_context.refresh()
        return ctx.to_dict()
    
    def set_owner_name(self, name: str):
        """Set the owner's name"""
        self.owner_profile.profile.name = name
        self.owner_profile.save()
    
    def add_key_fact(self, fact: str):
        """Add a key fact about the owner"""
        self.owner_profile.add_key_fact(fact)
    
    def set_current_project(self, project: str):
        """Set the current project context"""
        self.owner_profile.set_current_project(project)
    
    def add_active_task(self, task: str):
        """Add an active task"""
        self.owner_profile.add_active_task(task)
    
    def get_context_summary(self) -> str:
        """Get a summary of all context"""
        return self.grounded_context.get_context_summary()
    
    # === Memory Methods ===
    
    def remember(self, fact: str, importance: int = 3):
        """Store a fact in memory"""
        return self.memory.remember(fact, importance=importance)
    
    def recall(self, query: str) -> str:
        """Search memory"""
        return self.memory.recall(query)
    
    def forget(self, memory_id: str):
        """Forget a memory"""
        return self.memory.persistent.forget(memory_id)
    
    # === Tool & State Methods ===
    
    def get_tools(self) -> List[Dict]:
        """List available tools"""
        return self.tools.list_tools()
    
    def inspect(self) -> Dict:
        """Get agent state including M0.2 context"""
        state = {
            "name": self.config.name,
            "identity": self.identity.config.name,
            "owner_name": self.owner_profile.get_name(),
            "llm_available": self.llm_available,
            "llm_model": self.config.llm_model,
            "config": self.config.__dict__,
            "recent_memories": len(self.memory.working.items),
            "persistent_memories": len(self.memory.persistent.memories),
            "knowledge_base": self.memory.knowledge.list_keys(),
            "available_tools": len(self.tools.list_tools()),
            "context": {
                "timezone": self.grounded_context.default_timezone,
                "workspace": self.grounded_context.workspace,
                "current_project": self.owner_profile.get_current_project(),
                "active_tasks": self.owner_profile.get_active_tasks(),
                "interactions": self.owner_profile.get_interaction_count()
            }
        }
        return state


def create_agent(
    name: str = "Obsidian",
    workspace: str = ".",
    verbose: bool = True,
    context_enabled: bool = True
) -> Agent:
    """Create a configured agent instance with M0.2 context support"""
    config = AgentConfig(
        name=name,
        verbose=verbose,
        store_memory=True,
        reflection_enabled=True,
        context_enabled=context_enabled
    )
    return Agent(config, workspace)

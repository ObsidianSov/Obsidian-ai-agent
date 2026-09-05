"""
Agent Orchestrator - Main agent class combining all components

Phase 4: Integration of LLM provider, ReAct engine, and tool executor.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import os
import sys

# Handle imports whether run as package or script
try:
    from agent_core.tools import ToolRegistry, tools
    from agent_core.memory import MemorySystem
    from agent_core.reasoning import LLMReActEngine, ReActEngine
    from agent_core.executor import ToolExecutor
    from agent_core.llm import OpenRouterProvider, ConfigurationError
except ImportError:
    from tools import ToolRegistry, tools
    from memory import MemorySystem
    from reasoning import LLMReActEngine, ReActEngine
    from executor import ToolExecutor
    from llm import OpenRouterProvider, ConfigurationError


@dataclass
class AgentConfig:
    name: str = "Obsidian"
    max_steps: int = 10
    verbose: bool = True
    store_memory: bool = True
    reflection_enabled: bool = True
    # LLM settings
    llm_model: str = "anthropic/claude-3-haiku"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024


class Agent:
    """
    Main Agent class - LLM-powered ReAct reasoning with tools and memory.
    
    Phase 4: Integrates OpenRouterProvider, LLMReActEngine, and ToolExecutor.
    """
    
    def __init__(self, config: AgentConfig = None, workspace: str = "."):
        self.config = config or AgentConfig()
        self.workspace = workspace
        
        # Initialize components
        self.tools = ToolRegistry()
        self.memory = MemorySystem(workspace)
        
        # Initialize LLM provider (Phase 1)
        try:
            self.llm = OpenRouterProvider(
                model=self.config.llm_model,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens
            )
            self.llm_available = True
        except ConfigurationError as e:
            print(f"[!] LLM not available: {e}")
            print("[!] Agent will use fallback reasoning (limited capabilities)")
            self.llm = None
            self.llm_available = False
        
        # Initialize ReAct engine (Phase 2)
        if self.llm:
            self.react = LLMReActEngine(
                llm_provider=self.llm,
                max_steps=self.config.max_steps
            )
        else:
            # Fallback to basic engine
            self.react = ReActEngine(max_steps=self.config.max_steps)
        
        # Initialize tool executor (Phase 3)
        self.executor = ToolExecutor(self.tools)
    
    def run(self, task: str, context: Dict = None) -> str:
        """
        Main entry point - process a task through the LLM ReAct loop.
        
        Phase 4: True observe-think-act loop with LLM-driven decisions.
        """
        if self.config.verbose:
            print(f"\n[*] {self.config.name} Agent processing: {task}")
        
        # Add to working memory
        self.memory.working.add("user", task)
        
        # Get system context from memory
        sys_context = self.memory.get_system_context()
        
        # Get available tools
        available_tools = self.tools.list_tools()
        
        # Merge context
        merged_context = {}
        if context:
            merged_context.update(context)
        merged_context.update(sys_context)
        
        # Initialize reasoning engine
        self.react.reset(
            task=task,
            tools=available_tools,
            context=merged_context,
            memory=self.memory
        )
        
        # TRUE ReAct loop: Think -> Act -> Observe -> Repeat
        response = None
        
        while not self.react.is_complete() and self.react.get_current_step() < self.config.max_steps:
            # THINK: Get next action from LLM
            decision = self.react.think()
            
            if decision.action == "final":
                # Task complete
                response = decision.content
                if self.config.verbose:
                    print(f"[OK] Final answer: {response[:200]}")
                break
            
            if decision.action == "clarify":
                # Need clarification from user
                response = f"I need clarification: {decision.question}"
                if self.config.verbose:
                    print(f"[?] Clarification needed: {decision.question}")
                break
            
            # ACT: Execute tool
            if self.config.verbose:
                print(f"[>] Executing {decision.action}...")
            
            observation = self.executor.execute(
                decision.action,
                decision.action_input or {}
            )
            
            if self.config.verbose:
                # Show truncated result
                obs_preview = observation[:100] + "..." if len(observation) > 100 else observation
                print(f"[<] Result: {obs_preview}")
            
            # OBSERVE: Feed result back to reasoning
            self.react.add_observation(observation)
            
            # Store important results in memory
            if self.config.store_memory and len(str(observation)) < 500:
                self.memory.remember(
                    f"Task '{task}' - {decision.action} returned: {observation[:200]}",
                    importance=2
                )
        
        # Check if max steps reached
        if response is None:
            response = self.react.get_summary()
            if self.config.verbose:
                print(f"[!] Max steps reached: {response[:200]}")
        
        # Add to working memory
        self.memory.working.add("assistant", response)
        
        return response
    
    def run_with_trace(self, task: str, context: Dict = None) -> tuple:
        """
        Run task and return (response, trace) for debugging.
        """
        if self.config.verbose:
            print(f"\n[*] {self.config.name} Agent processing: {task}")
        
        self.memory.working.add("user", task)
        sys_context = self.memory.get_system_context()
        available_tools = self.tools.list_tools()
        
        merged_context = {}
        if context:
            merged_context.update(context)
        merged_context.update(sys_context)
        
        self.react.reset(
            task=task,
            tools=available_tools,
            context=merged_context,
            memory=self.memory
        )
        
        trace = []
        response = None
        
        while not self.react.is_complete() and self.react.get_current_step() < self.config.max_steps:
            decision = self.react.think()
            
            trace.append({
                "step": self.react.get_current_step(),
                "decision": {
                    "action": decision.action,
                    "action_input": decision.action_input,
                    "content": decision.content,
                    "question": decision.question
                }
            })
            
            if decision.action == "final":
                response = decision.content
                break
            
            if decision.action == "clarify":
                response = f"I need clarification: {decision.question}"
                break
            
            observation = self.executor.execute(
                decision.action,
                decision.action_input or {}
            )
            
            trace[-1]["observation"] = observation
            
            self.react.add_observation(observation)
        
        if response is None:
            response = self.react.get_summary()
        
        self.memory.working.add("assistant", response)
        
        return response, trace
    
    def remember(self, fact: str, importance: int = 3):
        """Explicitly store a fact in persistent memory"""
        return self.memory.remember(fact, importance=importance)
    
    def recall(self, query: str) -> str:
        """Search long-term memory"""
        return self.memory.recall(query)
    
    def forget(self, memory_id: str):
        """Forget a specific memory"""
        return self.memory.persistent.forget(memory_id)
    
    def get_tools(self) -> List[Dict]:
        """List available tools"""
        return self.tools.list_tools()
    
    def inspect(self) -> Dict:
        """Get agent state for inspection"""
        return {
            "name": self.config.name,
            "llm_available": self.llm_available,
            "llm_model": self.config.llm_model,
            "config": self.config.__dict__,
            "recent_memories": len(self.memory.working.items),
            "persistent_memories": len(self.memory.persistent.memories),
            "knowledge_base": self.memory.knowledge.list_keys(),
            "available_tools": len(self.tools.list_tools())
        }


# === Factory Function ===
def create_agent(name: str = "Obsidian", workspace: str = ".", verbose: bool = True) -> Agent:
    """Create a configured agent instance"""
    config = AgentConfig(
        name=name,
        verbose=verbose,
        store_memory=True,
        reflection_enabled=True
    )
    return Agent(config, workspace)

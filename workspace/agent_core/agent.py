"""
Obsidian Agent Orchestrator

M0.3 Architecture Consolidation
--------------------------------
Reasoning -> Agent -> Executor -> Action Gate -> Tool
                                  -> Audit

Responsibilities:
- Agent: orchestration, context, memory, and public API
- Reasoning: planning / ReAct loop / LLM interaction
- Executor: tool execution and safety enforcement
- Action Gate: command safety classification
- Audit Log: execution recording

M0.2:
- Identity
- Owner Profile
- Grounded Context
- Context Injection

M0.3:
- Removed duplicate Action Gate logic from Agent
- Executor is the single execution/safety authority
- Native tool calls and JSON fallback use the same execution path
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import os
import json


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

try:
    from agent_core.tools import ToolRegistry
    from agent_core.memory import MemorySystem
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.executor import ToolExecutor
    from agent_core.llm import (
        OpenRouterProvider,
        ConfigurationError,
        JSONParser,
    )

    # M0.2 Context System
    from agent_core.identity import AgentIdentity, IdentityConfig
    from agent_core.owner_profile import OwnerProfileManager
    from agent_core.grounded_context import GroundedContextProvider
    from agent_core.context_injector import ContextInjector, InjectionConfig

except ImportError:
    from tools import ToolRegistry
    from memory import MemorySystem
    from reasoning import UniversalReActEngine
    from executor import ToolExecutor
    from llm import (
        OpenRouterProvider,
        ConfigurationError,
        JSONParser,
    )

    # M0.2 Context System
    from identity import AgentIdentity, IdentityConfig
    from owner_profile import OwnerProfileManager
    from grounded_context import GroundedContextProvider
    from context_injector import ContextInjector, InjectionConfig


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    """Configuration for an Obsidian Agent instance."""

    name: str = "Obsidian"

    # ReAct
    max_steps: int = 10

    # Output / behavior
    verbose: bool = True
    store_memory: bool = True
    reflection_enabled: bool = True

    # LLM
    llm_model: Optional[str] = None
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024

    # M0.2 Context
    context_enabled: bool = True
    context_max_length: int = 3000


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class Agent:
    """
    Main Obsidian Agent.

    The Agent is responsible for orchestration.

    It does NOT perform Action Gate checks itself.

    All tool execution follows:

        Agent
          |
          v
        Executor
          |
          v
      Action Gate
          |
          v
         Tool

    This prevents multiple components from implementing different
    versions of the safety policy.
    """

    def __init__(
        self,
        config: AgentConfig = None,
        workspace: str = ".",
    ):
        self.config = config or AgentConfig()
        self.workspace = workspace

        # ---------------------------------------------------------------
        # Core systems
        # ---------------------------------------------------------------

        self.tools = ToolRegistry()

        self.memory = MemorySystem(
            workspace
        )

        self.executor = ToolExecutor(
            self.tools,
            workspace=workspace,
        )

        # ---------------------------------------------------------------
        # M0.2 Context System
        # ---------------------------------------------------------------

        self._init_context_system()

        # ---------------------------------------------------------------
        # LLM
        # ---------------------------------------------------------------

        try:
            self.llm = OpenRouterProvider(
                model=self.config.llm_model,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
            )

            self.llm_available = True

        except ConfigurationError as e:
            if self.config.verbose:
                print(f"[!] LLM not available: {e}")

            self.llm = None
            self.llm_available = False

        # ---------------------------------------------------------------
        # ReAct Engine
        # ---------------------------------------------------------------

        if self.llm is not None:

            self.react = UniversalReActEngine(
                llm_provider=self.llm,
                max_steps=self.config.max_steps,
                system_prompt=self._build_system_prompt(),
            )

            # IMPORTANT:
            # The ReAct engine delegates tool execution to the Agent,
            # which delegates it to the Executor.
            #
            # The Executor is therefore the single Action Gate authority.
            self.react.set_tool_executor(
                self._execute_tool
            )

        else:
            self.react = None

    # -------------------------------------------------------------------
    # M0.2 Context System
    # -------------------------------------------------------------------

    def _init_context_system(self):
        """Initialize Identity, Owner Profile, and Grounded Context."""

        # ---------------------------------------------------------------
        # Identity
        # ---------------------------------------------------------------

        identity_config = IdentityConfig(
            name=self.config.name
        )

        self.identity = AgentIdentity(
            config=identity_config
        )

        # ---------------------------------------------------------------
        # Owner Profile
        # ---------------------------------------------------------------

        owner_profile_path = os.path.join(
            self.workspace,
            "knowledge",
            "owner.json",
        )

        self.owner_profile = OwnerProfileManager(
            profile_path=owner_profile_path
        )

        # ---------------------------------------------------------------
        # Grounded Context
        # ---------------------------------------------------------------

        self.grounded_context = GroundedContextProvider(
            owner_profile=self.owner_profile,
            memory_system=self.memory,
            workspace=self.workspace,
        )

        # ---------------------------------------------------------------
        # Context Injector
        # ---------------------------------------------------------------

        context_config = InjectionConfig(
            max_context_length=self.config.context_max_length,

            include_identity=True,
            include_owner_profile=True,
            include_time_context=True,
            include_workspace=True,
            include_memory=True,
            include_capabilities=True,
            include_limitations=True,
            include_key_facts=True,
        )

        self.context_injector = ContextInjector(
            identity=self.identity,
            owner_profile=self.owner_profile,
            grounded_context=self.grounded_context,
            config=context_config,
        )

    # -------------------------------------------------------------------
    # System Prompt
    # -------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt.

        M0.2 context is injected here so the LLM receives identity,
        owner, workspace, memory, and grounded context.
        """

        base = f"""
You are {self.config.name}, an AI agent with access to tools.

Use tools when you need to:
- read files
- write files
- create directories
- run commands
- search the web
- retrieve information

For simple questions, answer directly.

For complex tasks, reason carefully and use the available tools when
necessary.

Do not claim that an action was performed unless the corresponding
tool actually executed successfully.
""".strip()

        if self.config.context_enabled:
            return self.context_injector.inject_system_prompt(
                base
            )

        return base

    # -------------------------------------------------------------------
    # Tool Instructions
    # -------------------------------------------------------------------

    def _build_tool_instructions(self) -> str:
        """Build instructions describing the available tools."""

        lines = [
            "",
            "AVAILABLE TOOLS:",
        ]

        for tool in self.tools.list_tools():

            name = tool.get("name", "")
            description = tool.get("description", "")
            params = tool.get("params", {})

            if params:

                param_parts = []

                for param_name, param_info in params.items():

                    param_type = param_info.get(
                        "type",
                        "any",
                    )

                    param_description = param_info.get(
                        "description",
                        "",
                    )

                    param_parts.append(
                        f"{param_name}: {param_type}"
                    )

                    if param_description:
                        lines.append(
                            f"  - {param_name}: "
                            f"{param_description}"
                        )

                lines.append(
                    f"- {name}"
                    f"({', '.join(param_parts)}): "
                    f"{description}"
                )

            else:
                lines.append(
                    f"- {name}: {description}"
                )

        lines.extend(
            [
                "",
                "For JSON fallback tool calls, output ONLY:",
                '{"action": "tool_name", '
                '"action_input": {"param": "value"}}',
                "",
                "When finished, output:",
                '{"action": "final", '
                '"content": "your answer"}',
            ]
        )

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Tool Execution
    # -------------------------------------------------------------------

    def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict,
    ) -> str:
        """
        Execute a tool through the canonical Executor.

        IMPORTANT:
        No Action Gate logic belongs here.

        Executor handles:
            tool validation
                ->
            Action Gate
                ->
            approval
                ->
            execution
                ->
            audit
        """

        return self.executor.execute(
            tool_name,
            arguments,
        )

    # -------------------------------------------------------------------
    # Standard Run
    # -------------------------------------------------------------------

    def run(
        self,
        task: str,
        context: Dict = None,
    ) -> str:
        """Run a task through the ReAct engine."""

        if not self.llm_available:
            return (
                "Error: LLM not available. "
                "Set OPENROUTER_API_KEY."
            )

        if self.config.verbose:
            print(
                f"\n[*] {self.config.name} processing: "
                f"{task}"
            )

        # ---------------------------------------------------------------
        # Record user interaction
        # ---------------------------------------------------------------

        self.memory.working.add(
            "user",
            task,
        )

        self.owner_profile.record_interaction()

        # ---------------------------------------------------------------
        # Reset ReAct state
        # ---------------------------------------------------------------

        available_tools = self.tools.list_tools()

        self.react.reset(
            task=task,
            tools=available_tools,
            context=context or {},
        )

        # ---------------------------------------------------------------
        # Run reasoning loop
        # ---------------------------------------------------------------

        result = self.react.run()

        # ---------------------------------------------------------------
        # Store response
        # ---------------------------------------------------------------

        self.memory.working.add(
            "assistant",
            result,
        )

        # ---------------------------------------------------------------
        # Persist useful tool observations
        # ---------------------------------------------------------------

        if self.config.store_memory:

            for observation in self.react.get_observations():

                self.memory.remember(
                    (
                        f"Tool "
                        f"{observation.tool_name}: "
                        f"{observation.result[:100]}"
                    ),
                    importance=2,
                )

        # ---------------------------------------------------------------
        # Output
        # ---------------------------------------------------------------

        if self.config.verbose:

            preview = (
                result[:200] + "..."
                if len(result) > 200
                else result
            )

            print(
                f"[OK] {preview}"
            )

        return result

    # -------------------------------------------------------------------
    # Run With Trace
    # -------------------------------------------------------------------

    def run_with_trace(
        self,
        task: str,
        context: Dict = None,
    ) -> tuple:
        """
        Run a task and return:

            (response, trace)

        Both native tool calls and JSON fallback calls use the same
        Executor path.

        There is intentionally NO Action Gate logic here.
        """

        if not self.llm_available:
            return (
                "Error: LLM not available.",
                [],
            )

        if self.config.verbose:
            print(
                f"\n[*] {self.config.name} processing: "
                f"{task}"
            )

        # ---------------------------------------------------------------
        # Record interaction
        # ---------------------------------------------------------------

        self.memory.working.add(
            "user",
            task,
        )

        self.owner_profile.record_interaction()

        available_tools = self.tools.list_tools()

        # ---------------------------------------------------------------
        # Reset reasoning state
        # ---------------------------------------------------------------

        self.react.reset(
            task,
            available_tools,
            context or {},
        )

        # ---------------------------------------------------------------
        # Trace state
        # ---------------------------------------------------------------

        trace = []
        step = 0

        # ---------------------------------------------------------------
        # Prompt configuration
        # ---------------------------------------------------------------

        tool_instructions = (
            self._build_tool_instructions()
        )

        system_prompt = (
            self._build_system_prompt()
            + "\n"
            + tool_instructions
        )

        # ---------------------------------------------------------------
        # ReAct loop
        # ---------------------------------------------------------------

        while step < self.config.max_steps:

            step += 1

            # -----------------------------------------------------------
            # Build step prompt
            # -----------------------------------------------------------

            prompt = (
                f"Task: {task}\n\n"
                f"Step {step} of "
                f"{self.config.max_steps}."
            )

            observations = (
                self.react.get_observations()
            )

            if observations:

                prompt += (
                    "\n\nPrevious results:"
                )

                for observation in observations:

                    result_preview = (
                        observation.result[:80]
                        + "..."
                        if len(observation.result) > 80
                        else observation.result
                    )

                    prompt += (
                        f"\n- "
                        f"{observation.tool_name}: "
                        f"{result_preview}"
                    )

            prompt += (
                "\n\nWhat should I do next? "
                "Output JSON only."
            )

            # -----------------------------------------------------------
            # Ask LLM
            # -----------------------------------------------------------

            try:

                response = (
                    self.llm.complete_with_tools(
                        prompt=prompt,
                        tools=self.react.tools,
                        system_prompt=system_prompt,
                    )
                )

            except Exception as e:

                return (
                    f"Error: {str(e)}",
                    trace,
                )

            trace_entry = {
                "step": step,
                "response": response,
            }

            tool_called = False

            # ===========================================================
            # NATIVE TOOL CALLS
            # ===========================================================

            if response.tool_calls:

                for tool_call in response.tool_calls:

                    # ---------------------------------------------------
                    # Normalize native tool call format
                    # ---------------------------------------------------

                    if isinstance(
                        tool_call,
                        dict,
                    ):

                        name = (
                            tool_call.get("action")
                            or tool_call.get("name")
                            or ""
                        )

                        args = (
                            tool_call.get(
                                "action_input"
                            )
                            or tool_call.get(
                                "arguments"
                            )
                            or {}
                        )

                    else:

                        name = tool_call.name
                        args = tool_call.arguments

                    # ---------------------------------------------------
                    # Canonical execution path
                    #
                    # Executor performs:
                    #   validation
                    #   Action Gate
                    #   approval
                    #   execution
                    #   audit
                    # ---------------------------------------------------

                    result = self._execute_tool(
                        name,
                        args,
                    )

                    # ---------------------------------------------------
                    # Trace
                    # ---------------------------------------------------

                    trace_entry["tool_call"] = {
                        "name": name,
                        "arguments": args,
                        "result": result,
                    }

                    # ---------------------------------------------------
                    # Observation
                    # ---------------------------------------------------

                    self.react.add_observation(
                        name,
                        args,
                        result,
                    )

                    tool_called = True

            # ===========================================================
            # JSON FALLBACK
            # ===========================================================

            elif response.content:

                try:

                    parsed = (
                        JSONParser.extract_json(
                            response.content
                        )
                    )

                    action = parsed.get(
                        "action",
                        "",
                    )

                    # ---------------------------------------------------
                    # Final response
                    # ---------------------------------------------------

                    if action == "final":

                        final_content = (
                            parsed.get(
                                "content",
                                response.content,
                            )
                        )

                        trace_entry["final"] = (
                            final_content
                        )

                        self.memory.working.add(
                            "assistant",
                            final_content,
                        )

                        return (
                            final_content,
                            trace + [trace_entry],
                        )

                    # ---------------------------------------------------
                    # JSON tool call
                    # ---------------------------------------------------

                    if action and action != "final":

                        args = (
                            parsed.get(
                                "action_input"
                            )
                            or {}
                        )

                        # -----------------------------------------------
                        # Canonical execution path.
                        #
                        # NO gate_check() here.
                        # Executor owns the gate.
                        # -----------------------------------------------

                        result = self._execute_tool(
                            action,
                            args,
                        )

                        # -----------------------------------------------
                        # Trace
                        # -----------------------------------------------

                        trace_entry["tool_call"] = {
                            "name": action,
                            "arguments": args,
                            "result": result,
                        }

                        # -----------------------------------------------
                        # Observation
                        # -----------------------------------------------

                        self.react.add_observation(
                            action,
                            args,
                            result,
                        )

                        tool_called = True

                except (
                    ValueError,
                    json.JSONDecodeError,
                ):

                    # ---------------------------------------------------
                    # Plain-text fallback
                    # ---------------------------------------------------

                    self.memory.working.add(
                        "assistant",
                        response.content,
                    )

                    return (
                        response.content,
                        trace + [trace_entry],
                    )

            # -----------------------------------------------------------
            # Continue after tool execution
            # -----------------------------------------------------------

            if tool_called:

                trace.append(
                    trace_entry
                )

                continue

            # -----------------------------------------------------------
            # Return plain response
            # -----------------------------------------------------------

            if response.content:

                self.memory.working.add(
                    "assistant",
                    response.content,
                )

                return (
                    response.content,
                    trace + [trace_entry],
                )

            # Nothing happened
            break

        # ----------------------------------------------------------------
        # Max-step summary
        # ----------------------------------------------------------------

        summary = self.react.get_summary()

        self.memory.working.add(
            "assistant",
            summary,
        )

        return (
            summary,
            trace,
        )

    # ===================================================================
    # M0.2 CONTEXT API
    # ===================================================================

    def get_identity(self) -> AgentIdentity:
        """Return the agent identity."""

        return self.identity

    def get_owner_profile(
        self,
    ) -> OwnerProfileManager:
        """Return the owner profile manager."""

        return self.owner_profile

    def get_grounded_context(
        self,
    ) -> GroundedContextProvider:
        """Return the grounded context provider."""

        return self.grounded_context

    def refresh_context(
        self,
    ) -> Dict[str, Any]:
        """Refresh grounded context and return it as a dictionary."""

        context = (
            self.grounded_context.refresh()
        )

        return context.to_dict()

    def set_owner_name(
        self,
        name: str,
    ):
        """Set and persist the owner's name."""

        self.owner_profile.profile.name = name
        self.owner_profile.save()

    def add_key_fact(
        self,
        fact: str,
    ):
        """Add a persistent key fact about the owner."""

        self.owner_profile.add_key_fact(
            fact
        )

    def set_current_project(
        self,
        project: str,
    ):
        """Set the current project."""

        self.owner_profile.set_current_project(
            project
        )

    def add_active_task(
        self,
        task: str,
    ):
        """Add an active owner task."""

        self.owner_profile.add_active_task(
            task
        )

    def get_context_summary(
        self,
    ) -> str:
        """Return a human-readable context summary."""

        return (
            self.grounded_context
            .get_context_summary()
        )

    # ===================================================================
    # MEMORY API
    # ===================================================================

    def remember(
        self,
        fact: str,
        importance: int = 3,
    ):
        """Store a fact in persistent memory."""

        return self.memory.remember(
            fact,
            importance=importance,
        )

    def recall(
        self,
        query: str,
    ) -> str:
        """Search persistent memory."""

        return self.memory.recall(
            query
        )

    def forget(
        self,
        memory_id: str,
    ):
        """Forget a persistent memory."""

        return self.memory.persistent.forget(
            memory_id
        )

    # ===================================================================
    # TOOL / STATE API
    # ===================================================================

    def get_tools(
        self,
    ) -> List[Dict]:
        """Return the available tools."""

        return self.tools.list_tools()

    def inspect(self) -> Dict:
        """
        Return the current Agent state.

        Useful for diagnostics and future control interfaces.
        """

        return {
            "name": self.config.name,

            "identity": (
                self.identity.config.name
            ),

            "owner_name": (
                self.owner_profile.get_name()
            ),

            "llm_available": (
                self.llm_available
            ),

            "llm_model": (
                self.config.llm_model
            ),

            "config": (
                self.config.__dict__
            ),

            "recent_memories": (
                len(
                    self.memory.working.items
                )
            ),

            "persistent_memories": (
                len(
                    self.memory.persistent.memories
                )
            ),

            "knowledge_base": (
                self.memory.knowledge.list_keys()
            ),

            "available_tools": (
                len(
                    self.tools.list_tools()
                )
            ),

            "context": {
                "timezone": (
                    self.grounded_context
                    .default_timezone
                ),

                "workspace": (
                    self.grounded_context
                    .workspace
                ),

                "current_project": (
                    self.owner_profile
                    .get_current_project()
                ),

                "active_tasks": (
                    self.owner_profile
                    .get_active_tasks()
                ),

                "interactions": (
                    self.owner_profile
                    .get_interaction_count()
                ),
            },
        }


# =========================================================================
# FACTORY
# =========================================================================

def create_agent(
    name: str = "Obsidian",
    workspace: str = ".",
    verbose: bool = True,
    context_enabled: bool = True,
) -> Agent:
    """
    Create a configured Obsidian Agent.
    """

    config = AgentConfig(
        name=name,
        verbose=verbose,
        store_memory=True,
        reflection_enabled=True,
        context_enabled=context_enabled,
    )

    return Agent(
        config=config,
        workspace=workspace,
    )
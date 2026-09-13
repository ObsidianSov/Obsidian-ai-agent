"""
Context Injector - Integrates identity, owner profile, and grounded context

M0.2: Provides utilities to inject contextual information into:
- System prompts
- Task prompts
- Memory system
- Tool execution context
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import json


@dataclass
class InjectionConfig:
    """Configuration for context injection"""
    include_identity: bool = True
    include_owner_profile: bool = True
    include_time_context: bool = True
    include_workspace: bool = True
    include_memory: bool = True
    include_capabilities: bool = True
    include_limitations: bool = True
    include_key_facts: bool = True
    include_preferences: bool = False  # Usually not needed in prompts
    max_context_length: int = 3000


class ContextInjector:
    """
    Injects contextual information into agent prompts and operations.
    
    Combines identity, owner profile, and grounded context into a
    coherent context that grounds the agent's responses.
    """
    
    def __init__(
        self,
        identity=None,
        owner_profile=None,
        grounded_context=None,
        config: InjectionConfig = None
    ):
        self.identity = identity
        self.owner_profile = owner_profile
        self.grounded_context = grounded_context
        self.config = config or InjectionConfig()
        
        # Callbacks for lazy loading
        self._identity_loader: Optional[Callable[[], Any]] = None
        self._owner_loader: Optional[Callable[[], Any]] = None
        self._context_loader: Optional[Callable[[], Any]] = None
    
    def set_identity_loader(self, loader: Callable[[], Any]):
        """Set lazy loader for identity"""
        self._identity_loader = loader
    
    def set_owner_loader(self, loader: Callable[[], Any]):
        """Set lazy loader for owner profile"""
        self._owner_loader = loader
    
    def set_context_loader(self, loader: Callable[[], Any]):
        """Set lazy loader for grounded context"""
        self._context_loader = loader
    
    def _get_identity(self):
        """Get identity with lazy loading"""
        if self.identity is None and self._identity_loader:
            self.identity = self._identity_loader()
        return self.identity
    
    def _get_owner_profile(self):
        """Get owner profile with lazy loading"""
        if self.owner_profile is None and self._owner_loader:
            self.owner_profile = self._owner_loader()
        return self.owner_profile
    
    def _get_grounded_context(self):
        """Get grounded context with lazy loading"""
        if self.grounded_context is None and self._context_loader:
            self.grounded_context = self._context_loader()
        return self.grounded_context
    
    def inject_system_prompt(self, base_prompt: str) -> str:
        """Inject context into a system prompt"""
        parts = []
        
        # Identity
        if self.config.include_identity:
            identity = self._get_identity()
            if identity:
                parts.append(identity.get_system_prompt_fragment())
        
        # Time context
        if self.config.include_time_context:
            ctx = self._get_grounded_context()
            if ctx:
                parts.append(f"\nCURRENT TIME AND DATE:\n{ctx.get_context_summary()}")
        
        # Owner profile
        if self.config.include_owner_profile:
            owner = self._get_owner_profile()
            if owner:
                parts.append(f"\n{owner.get_summary()}")
        
        # Capabilities and limitations
        if self.config.include_capabilities or self.config.include_limitations:
            identity = self._get_identity()
            if identity:
                if self.config.include_capabilities:
                    caps = "\n".join(f"- {c}" for c in identity.config.core_capabilities)
                    parts.append(f"\nYOUR CAPABILITIES:\n{caps}")
                
                if self.config.include_limitations:
                    lims = "\n".join(f"- {l}" for l in identity.config.limitations)
                    parts.append(f"\nIMPORTANT LIMITATIONS:\n{lims}")
        
        # Key facts about owner
        if self.config.include_key_facts:
            owner = self._get_owner_profile()
            if owner and owner.profile.key_facts:
                facts = "\n".join(f"- {f}" for f in owner.profile.key_facts[:5])
                parts.append(f"\nIMPORTANT FACTS ABOUT YOU:\n{facts}")
        
        # Combine
        context_text = "\n\n".join(parts)
        
        if not context_text:
            return base_prompt
        
        result = f"{base_prompt}\n\n{'='*50}\nCONTEXT\n{'='*50}\n{context_text}\n{'='*50}"
        
        # Truncate if needed
        if len(result) > self.config.max_context_length:
            result = result[:self.config.max_context_length] + "\n...[context truncated]"
        
        return result
    
    def inject_task_prompt(self, task: str, context: Dict = None) -> str:
        """Create a task prompt with full context"""
        parts = [f"Task: {task}"]
        
        # Add context dict if provided
        if context:
            if self.config.include_time_context:
                if "timestamp" in context:
                    parts.append(f"\nCurrent time: {context['timestamp']}")
            
            if self.config.include_workspace:
                if "workspace" in context:
                    parts.append(f"Working directory: {context['workspace']}")
            
            if self.config.include_owner_profile:
                if "owner_name" in context:
                    parts.append(f"Working with: {context['owner_name']}")
                
                if "active_tasks" in context and context["active_tasks"]:
                    tasks = ", ".join(context["active_tasks"][:3])
                    parts.append(f"Active tasks: {tasks}")
        
        return "\n".join(parts)
    
    def get_full_context(self) -> Dict[str, Any]:
        """Get complete context as dict"""
        context = {}
        
        # Identity
        identity = self._get_identity()
        if identity:
            context["identity"] = identity.to_dict()
        
        # Owner profile
        owner = self._get_owner_profile()
        if owner:
            context["owner"] = owner.get_context_dict()
        
        # Grounded context
        grounded = self._get_grounded_context()
        if grounded:
            context["grounded"] = grounded.get_context_dict()
        
        return context
    
    def get_context_for_tools(self) -> Dict[str, Any]:
        """Get context relevant for tool execution"""
        return {
            "workspace": self._get_grounded_context().workspace if self._get_grounded_context() else ".",
            "timezone": self._get_owner_profile().get_timezone() if self._get_owner_profile() else "UTC",
            "preferences": self._get_owner_profile().profile.preferences if self._get_owner_profile() else {}
        }
    
    def format_for_memory(self) -> str:
        """Format context for memory storage"""
        parts = []

        # Current state
        provider = self._get_grounded_context()
        if provider:
            ctx = provider.refresh()
            parts.append(f"Time: {ctx.timestamp}")
            parts.append(f"Workspace: {ctx.workspace}")

        # Owner info
        owner = self._get_owner_profile()
        if owner:
            parts.append(f"Owner: {owner.get_name()}")
            if owner.profile.current_project:
                parts.append(f"Project: {owner.profile.current_project}")

        return "\n".join(parts)  
    
    def create_task_context(self, task: str) -> Dict[str, Any]:
        """Create context dict for a specific task"""
        return {
            "task": task,
            "identity": self._get_identity().to_dict() if self._get_identity() else {},
            "owner": self._get_owner_profile().get_context_dict() if self._get_owner_profile() else {},
            "grounded": self._get_grounded_context().get_context_dict() if self._get_grounded_context() else {}
        }


class ContextualAgentMixin:
    """
    Mixin class that adds context injection to an agent.
    
    Usage:
        class MyAgent(ContextualAgentMixin, BaseAgent):
            pass
    """
    
    def __init__(self, *args, **kwargs):
        # Store context config before init
        self._context_config = kwargs.pop("context_config", None)
        super().__init__(*args, **kwargs)
        
        # Initialize context system
        self._init_context_system()
    
    def _init_context_system(self):
        """Initialize the context injection system"""
        from agent_core.identity import AgentIdentity
        from agent_core.owner_profile import OwnerProfileManager
        from agent_core.grounded_context import GroundedContextProvider
        
        # Create components
        self.identity = AgentIdentity()
        self.owner_profile = OwnerProfileManager()
        self.grounded_context = GroundedContextProvider(
            owner_profile=self.owner_profile,
            memory_system=getattr(self, 'memory', None),
            workspace=self.workspace
        )
        
        # Create injector
        config = self._context_config or InjectionConfig()
        self.context_injector = ContextInjector(
            identity=self.identity,
            owner_profile=self.owner_profile,
            grounded_context=self.grounded_context,
            config=config
        )
        
        # Wire up memory callbacks
        self.memory.persistent.register_update_callback(self._on_memory_update)
        self.owner_profile.register_update_callback(self._on_profile_update)
    
    def _on_memory_update(self, memory):
        """Handle memory updates"""
        self.grounded_context.refresh()
    
    def _on_profile_update(self, profile):
        """Handle profile updates"""
        self.grounded_context.refresh()
    
    def get_system_prompt(self) -> str:
        """Get system prompt with context injection"""
        base = super().get_system_prompt()
        return self.context_injector.inject_system_prompt(base)
    
    def get_context_for_task(self, task: str) -> Dict[str, Any]:
        """Get context dict for a specific task"""
        return self.context_injector.create_task_context(task)


def inject_context(
    base_prompt: str,
    identity_path: str = "knowledge/identity.json",
    owner_path: str = "knowledge/owner.json",
    workspace: str = "."
) -> str:
    """
    Standalone function to inject context into any prompt.
    
    Usage:
        enhanced_prompt = inject_context("Your task is to...")
    """
    from agent_core.identity import AgentIdentity
    from agent_core.owner_profile import OwnerProfileManager
    from agent_core.grounded_context import GroundedContextProvider
    
    identity = AgentIdentity(identity_path=identity_path)
    owner = OwnerProfileManager(profile_path=owner_path)
    context = GroundedContextProvider(owner_profile=owner, workspace=workspace)
    
    injector = ContextInjector(
        identity=identity,
        owner_profile=owner,
        grounded_context=context
    )
    
    return injector.inject_system_prompt(base_prompt)

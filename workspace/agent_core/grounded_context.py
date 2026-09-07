"""
Grounded Context System - Dynamic context injection for agent grounding

M0.2: Provides dynamically generated context that grounds the agent
in the user's reality including:
- Current time and date
- System environment
- Workspace state
- Recent activities
- Memory context
- Owner profile data
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import platform
import socket


@dataclass
class ContextSource:
    """A source of context data"""
    name: str
    priority: int = 0  # Higher = more important
    data: Dict[str, Any] = field(default_factory=dict)
    ttl: int = 300  # Time-to-live in seconds
    last_updated: Optional[str] = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()
    
    def is_fresh(self) -> bool:
        """Check if context is still fresh"""
        if not self.last_updated:
            return False
        last = datetime.fromisoformat(self.last_updated)
        age = (datetime.now() - last).total_seconds()
        return age < self.ttl
    
    def update(self, data: Dict[str, Any]):
        """Update context data"""
        self.data = data
        self.last_updated = datetime.now().isoformat()


@dataclass
class GroundedContext:
    """Complete grounded context for an agent"""
    timestamp: str = ""
    timezone: str = "UTC"
    hostname: str = ""
    platform: str = ""
    workspace: str = ""
    python_version: str = ""
    environment: Dict[str, str] = field(default_factory=dict)
    owner_context: Dict[str, Any] = field(default_factory=dict)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    recent_observations: List[str] = field(default_factory=list)
    active_tasks: List[str] = field(default_factory=list)
    project_context: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "timezone": self.timezone,
            "hostname": self.hostname,
            "platform": self.platform,
            "workspace": self.workspace,
            "python_version": self.python_version,
            "environment": self.environment,
            "owner_context": self.owner_context,
            "memory_context": self.memory_context,
            "recent_observations": self.recent_observations,
            "active_tasks": self.active_tasks,
            "project_context": self.project_context
        }


class GroundedContextProvider:
    """
    Provides dynamically grounded context for the agent.
    
    This helps the agent stay grounded in reality by providing:
    - Accurate time information
    - System/environment details
    - User context from profile
    - Memory context
    - Workspace state
    """
    
    def __init__(
        self,
        owner_profile=None,
        memory_system=None,
        workspace: str = ".",
        default_timezone: str = "UTC"
    ):
        self.owner_profile = owner_profile
        self.memory_system = memory_system
        self.workspace = workspace
        self.default_timezone = default_timezone
        
        # Context sources
        self._sources: Dict[str, ContextSource] = {}
        self._register_default_sources()
        
        # Callbacks
        self._on_context_update: Optional[Callable[[GroundedContext], None]] = None
    
    def _register_default_sources(self):
        """Register default context sources"""
        self.register_source(ContextSource(
            name="system",
            priority=10,
            ttl=3600  # System info is stable
        ))
        self.register_source(ContextSource(
            name="time",
            priority=100,  # Time is most important
            ttl=60  # Refresh every minute
        ))
        self.register_source(ContextSource(
            name="workspace",
            priority=50,
            ttl=300
        ))
        self.register_source(ContextSource(
            name="owner",
            priority=80,
            ttl=600
        ))
        self.register_source(ContextSource(
            name="memory",
            priority=60,
            ttl=120
        ))
    
    def register_source(self, source: ContextSource):
        """Register a context source"""
        self._sources[source.name] = source
    
    def get_source(self, name: str) -> Optional[ContextSource]:
        """Get a context source by name"""
        return self._sources.get(name)
    
    def set_context_callback(self, callback: Callable[[GroundedContext], None]):
        """Set callback for context updates"""
        self._on_context_update = callback
    
    def refresh(self) -> GroundedContext:
        """Refresh all context sources and return complete context"""
        context = self._gather_context()
        
        if self._on_context_update:
            try:
                self._on_context_update(context)
            except Exception:
                pass
        
        return context
    
    def _gather_context(self) -> GroundedContext:
        """Gather all context data"""
        context = GroundedContext()
        
        # Time context
        self._update_time_context(context)
        
        # System context
        self._update_system_context(context)
        
        # Workspace context
        self._update_workspace_context(context)
        
        # Owner context
        self._update_owner_context(context)
        
        # Memory context
        self._update_memory_context(context)
        
        return context
    
    def _update_time_context(self, context: GroundedContext):
        """Update time-related context"""
        now = datetime.now(timezone.utc)
        
        timezone_name = self.default_timezone
        if self.owner_profile:
            timezone_name = self.owner_profile.get_timezone()
        
        # Try to get local time for timezone
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(timezone_name)
            local_time = now.astimezone(tz)
            time_str = local_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception:
            time_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        context.timestamp = time_str
        context.timezone = timezone_name
        
        # Update source
        self._sources["time"].update({
            "timestamp": time_str,
            "timezone": timezone_name,
            "iso": now.isoformat(),
            "day_of_week": now.strftime("%A"),
            "hour": now.hour
        })
    
    def _update_system_context(self, context: GroundedContext):
        """Update system/environment context"""
        context.hostname = socket.gethostname()
        context.platform = f"{platform.system()} {platform.release()}"
        context.python_version = platform.python_version()
        
        # Environment variables (only safe ones)
        safe_env = {}
        for key in ["PATH", "HOME", "USER", "USERNAME", "SHELL", "OBSIDIAN_WORKSPACE"]:
            if key in os.environ:
                safe_env[key] = os.environ[key]
        context.environment = safe_env
        
        # Update source
        self._sources["system"].update({
            "hostname": context.hostname,
            "platform": context.platform,
            "python_version": context.python_version
        })
    
    def _update_workspace_context(self, context: GroundedContext):
        """Update workspace context"""
        # Use the provider's workspace as the authoritative source
        # The owner profile workspace is just metadata for reference
        workspace_path = os.path.abspath(self.workspace)
        
        context.workspace = workspace_path
        
        # Try to get project info
        project_context = ""
        project_file = os.path.join(workspace_path, "PROJECT.md")
        if os.path.exists(project_file):
            try:
                with open(project_file, 'r') as f:
                    project_context = f.read()[:500]  # First 500 chars
            except Exception:
                pass
        
        context.project_context = project_context
        
        # List files in workspace
        try:
            files = os.listdir(workspace_path)[:20]  # First 20 items
            workspace_state = {
                "path": workspace_path,
                "files": files,
                "project_context": project_context
            }
        except Exception as e:
            workspace_state = {"path": workspace_path, "error": str(e)}
        
        # Update source
        self._sources["workspace"].update(workspace_state)
    
    def _update_owner_context(self, context: GroundedContext):
        """Update owner profile context"""
        if self.owner_profile:
            profile = self.owner_profile.get_profile()
            context.owner_context = {
                "name": profile.name,
                "timezone": profile.timezone,
                "language": profile.language,
                "current_project": profile.current_project,
                "active_tasks": profile.active_tasks,
                "key_facts": profile.key_facts,
                "preferences": profile.preferences
            }
            context.active_tasks = profile.active_tasks
            
            # Update source
            self._sources["owner"].update(context.owner_context)
    
    def _update_memory_context(self, context: GroundedContext):
        """Update memory context"""
        if self.memory_system:
            # Get system context from memory
            try:
                sys_context = self.memory_system.get_system_context()
                context.memory_context = sys_context
                
                # Get recent observations from working memory
                recent = sys_context.get("recent_conversation", [])
                context.recent_observations = [
                    f"{r.get('role', 'unknown')}: {r.get('content', '')[:100]}"
                    for r in recent[-5:]
                ]
                
                # Update source
                self._sources["memory"].update(sys_context)
            except Exception:
                pass
    
    def get_context_summary(self, max_length: int = 2000) -> str:
        """Get a summary of current context for prompt injection"""
        context = self.refresh()
        lines = ["CURRENT CONTEXT:"]
        
        # Time
        lines.append(f"- Time: {context.timestamp}")
        
        # System
        lines.append(f"- System: {context.platform} on {context.hostname}")
        
        # Workspace
        lines.append(f"- Workspace: {context.workspace}")
        
        # Owner
        if context.owner_context.get("name"):
            lines.append(f"- Owner: {context.owner_context['name']}")
        
        if context.owner_context.get("current_project"):
            lines.append(f"- Project: {context.owner_context['current_project']}")
        
        # Active tasks
        if context.active_tasks:
            tasks = ", ".join(context.active_tasks[:3])
            lines.append(f"- Tasks: {tasks}")
        
        # Key facts
        if context.owner_context.get("key_facts"):
            lines.append("- Key facts:")
            for fact in context.owner_context["key_facts"][:3]:
                lines.append(f"  - {fact}")
        
        # Memory context
        if context.recent_observations:
            lines.append("- Recent activity:")
            for obs in context.recent_observations[-2:]:
                lines.append(f"  - {obs}")
        
        result = "\n".join(lines)
        
        # Truncate if too long
        if len(result) > max_length:
            result = result[:max_length] + "\n... (context truncated)"
        
        return result
    
    def get_context_dict(self) -> Dict[str, Any]:
        """Get context as dict for structured access"""
        context = self.refresh()
        return context.to_dict()
    
    def get_focused_context(self, focus: List[str]) -> Dict[str, Any]:
        """Get context focused on specific sources"""
        context = self.refresh()
        result = {}
        
        for key in focus:
            if hasattr(context, key):
                result[key] = getattr(context, key)
        
        return result


def create_context_provider(
    owner_profile=None,
    memory_system=None,
    workspace: str = "."
) -> GroundedContextProvider:
    """Factory to create a context provider"""
    return GroundedContextProvider(
        owner_profile=owner_profile,
        memory_system=memory_system,
        workspace=workspace
    )

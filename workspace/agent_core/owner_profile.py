"""
Owner Profile - Persistent storage of user preferences and context

M0.2: Stores and manages information about the owner/user including:
- Basic profile information
- Preferences and defaults
- Working context
- Historical interactions
- Custom knowledge
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class OwnerProfile:
    """Complete owner profile data"""
    id: str = "default"
    name: str = ""
    email: str = ""
    timezone: str = "UTC"
    language: str = "en"
    
    # Preferences
    preferences: Dict[str, Any] = field(default_factory=dict)
    default_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Working context
    workspace_root: str = "."
    current_project: str = ""
    active_tasks: List[str] = field(default_factory=list)
    
    # Knowledge
    custom_knowledge: Dict[str, str] = field(default_factory=dict)
    key_facts: List[str] = field(default_factory=list)
    
    # History
    interaction_count: int = 0
    last_seen: str = ""
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_seen:
            self.last_seen = now
        self.updated_at = now
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "timezone": self.timezone,
            "language": self.language,
            "preferences": self.preferences,
            "default_settings": self.default_settings,
            "workspace_root": self.workspace_root,
            "current_project": self.current_project,
            "active_tasks": self.active_tasks,
            "custom_knowledge": self.custom_knowledge,
            "key_facts": self.key_facts,
            "interaction_count": self.interaction_count,
            "last_seen": self.last_seen,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OwnerProfile':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class OwnerProfileManager:
    """
    Manages owner profile storage and retrieval.
    
    Provides a persistent store for user information that can be
    loaded at startup and updated throughout the session.
    """
    
    DEFAULT_PROFILE = OwnerProfile(
        id="default",
        name="User",
        timezone="UTC",
        language="en",
        preferences={
            "verbose": True,
            "confirm_destructive": True,
            "max_steps": 10,
            "store_memory": True
        },
        default_settings={
            "model": "anthropic/claude-3-haiku",
            "temperature": 0.7,
            "max_tokens": 1024
        }
    )
    
    def __init__(self, profile_path: str = "knowledge/owner.json"):
        self.profile_path = profile_path
        self.profile = self._load_or_default()
        self._on_update_callbacks: List[Callable[[OwnerProfile], None]] = []
    
    def _load_or_default(self) -> OwnerProfile:
        """Load profile from file or return default"""
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, 'r') as f:
                    data = json.load(f)
                    return OwnerProfile.from_dict(data)
            except Exception:
                pass
        return self.DEFAULT_PROFILE
    
    def save(self):
        """Save profile to file"""
        self.profile.updated_at = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.profile_path) or ".", exist_ok=True)
        with open(self.profile_path, 'w') as f:
            json.dump(self.profile.to_dict(), f, indent=2)
        self._notify_callbacks()
    
    def register_update_callback(self, callback: Callable[[OwnerProfile], None]):
        """Register callback for profile updates"""
        self._on_update_callbacks.append(callback)
    
    def _notify_callbacks(self):
        """Notify all registered callbacks of update"""
        for callback in self._on_update_callbacks:
            try:
                callback(self.profile)
            except Exception:
                pass
    
    # === Profile Access ===
    
    def get_profile(self) -> OwnerProfile:
        """Get the current owner profile"""
        return self.profile
    
    def get_name(self) -> str:
        """Get owner's name"""
        return self.profile.name or "User"
    
    def get_timezone(self) -> str:
        """Get owner's timezone"""
        return self.profile.timezone
    
    def get_language(self) -> str:
        """Get owner's language"""
        return self.profile.language
    
    # === Preference Management ===
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a preference value"""
        return self.profile.preferences.get(key, default)
    
    def set_preference(self, key: str, value: Any):
        """Set a preference value"""
        self.profile.preferences[key] = value
        self.save()
    
    def get_default_setting(self, key: str, default: Any = None) -> Any:
        """Get a default setting"""
        return self.profile.default_settings.get(key, default)
    
    def set_default_setting(self, key: str, value: Any):
        """Set a default setting"""
        self.profile.default_settings[key] = value
        self.save()
    
    # === Working Context ===
    
    def set_workspace(self, path: str):
        """Set the workspace root"""
        self.profile.workspace_root = path
        self.save()
    
    def get_workspace(self) -> str:
        """Get the workspace root"""
        return self.profile.workspace_root
    
    def set_current_project(self, project: str):
        """Set the current project context"""
        self.profile.current_project = project
        self.save()
    
    def get_current_project(self) -> str:
        """Get the current project context"""
        return self.profile.current_project
    
    def add_active_task(self, task: str):
        """Add an active task"""
        if task not in self.profile.active_tasks:
            self.profile.active_tasks.append(task)
            self.save()
    
    def remove_active_task(self, task: str):
        """Remove an active task"""
        if task in self.profile.active_tasks:
            self.profile.active_tasks.remove(task)
            self.save()
    
    def get_active_tasks(self) -> List[str]:
        """Get active tasks"""
        return self.profile.active_tasks.copy()
    
    # === Knowledge Management ===
    
    def add_knowledge(self, key: str, value: str):
        """Add custom knowledge"""
        self.profile.custom_knowledge[key] = value
        self.save()
    
    def get_knowledge(self, key: str) -> Optional[str]:
        """Get custom knowledge"""
        return self.profile.custom_knowledge.get(key)
    
    def get_all_knowledge(self) -> Dict[str, str]:
        """Get all custom knowledge"""
        return self.profile.custom_knowledge.copy()
    
    def remove_knowledge(self, key: str) -> bool:
        """Remove custom knowledge"""
        if key in self.profile.custom_knowledge:
            del self.profile.custom_knowledge[key]
            self.save()
            return True
        return False
    
    def add_key_fact(self, fact: str):
        """Add a key fact about the owner"""
        if fact not in self.profile.key_facts:
            self.profile.key_facts.append(fact)
            self.save()
    
    def get_key_facts(self) -> List[str]:
        """Get key facts"""
        return self.profile.key_facts.copy()
    
    # === Interaction Tracking ===
    
    def record_interaction(self):
        """Record an interaction"""
        self.profile.interaction_count += 1
        self.profile.last_seen = datetime.now().isoformat()
        self.save()
    
    def get_interaction_count(self) -> int:
        """Get total interaction count"""
        return self.profile.interaction_count
    
    # === Profile Summary ===
    
    def get_summary(self) -> str:
        """Get a summary of the profile for context injection"""
        parts = ["OWNER PROFILE:"]
        
        if self.profile.name:
            parts.append(f"- Name: {self.profile.name}")
        
        if self.profile.timezone:
            parts.append(f"- Timezone: {self.profile.timezone}")
        
        if self.profile.current_project:
            parts.append(f"- Current Project: {self.profile.current_project}")
        
        if self.profile.active_tasks:
            parts.append(f"- Active Tasks: {', '.join(self.profile.active_tasks[:5])}")
        
        if self.profile.key_facts:
            parts.append("- Key Facts:")
            for fact in self.profile.key_facts[:3]:
                parts.append(f"  • {fact}")
        
        if self.profile.custom_knowledge:
            parts.append("- Custom Knowledge:")
            for key, value in list(self.profile.custom_knowledge.items())[:3]:
                parts.append(f"  • {key}: {value}")
        
        parts.append(f"- Interactions: {self.profile.interaction_count}")
        
        return "\n".join(parts)
    
    def get_context_dict(self) -> Dict[str, Any]:
        """Get profile data as context dict for prompts"""
        return {
            "owner_name": self.profile.name,
            "owner_timezone": self.profile.timezone,
            "owner_language": self.profile.language,
            "workspace": self.profile.workspace_root,
            "current_project": self.profile.current_project,
            "active_tasks": self.profile.active_tasks,
            "preferences": self.profile.preferences,
            "custom_knowledge": self.profile.custom_knowledge,
            "key_facts": self.profile.key_facts
        }
    
    # === Full Update ===
    
    def update_profile(self, data: Dict[str, Any]):
        """Update multiple profile fields at once"""
        for key, value in data.items():
            if hasattr(self.profile, key):
                setattr(self.profile, key, value)
        self.save()


def create_owner_profile(
    name: str = "User",
    timezone: str = "UTC",
    workspace: str = ".",
    profile_path: str = "knowledge/owner.json",
    **kwargs
) -> OwnerProfileManager:
    """Factory to create a new owner profile"""
    profile = OwnerProfile(
        id="default",
        name=name,
        timezone=timezone,
        workspace_root=workspace,
        **kwargs
    )
    manager = OwnerProfileManager(profile_path)
    manager.profile = profile
    manager.save()
    return manager

"""
Identity System - Agent's own identity and self-awareness

M0.2: Provides the agent with a defined identity, persona, capabilities,
and self-understanding that can be injected into prompts.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class IdentityConfig:
    """Configuration for agent identity"""
    name: str = "Obsidian"
    title: str = "AI Assistant"
    version: str = "1.0.0"
    persona: str = "helpful, knowledgeable, precise"
    core_capabilities: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    behavioral_traits: Dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "version": self.version,
            "persona": self.persona,
            "core_capabilities": self.core_capabilities,
            "limitations": self.limitations,
            "behavioral_traits": self.behavioral_traits,
            "created_at": self.created_at,
            "last_updated": self.last_updated
        }


class AgentIdentity:
    """
    Manages the agent's own identity and self-awareness.
    
    This provides a grounded sense of "self" that the agent can
    reference and that helps it maintain consistent behavior.
    """
    
    # Default identity template
    DEFAULT_CONFIG = IdentityConfig(
        name="Obsidian",
        title="AI Agent",
        version="1.0.0",
        persona="helpful, knowledgeable, precise, thoughtful",
        core_capabilities=[
            "File operations (read, write, list, create directories)",
            "Terminal command execution",
            "Code generation and debugging",
            "Step-by-step reasoning with tool use",
            "Memory and knowledge management",
            "Web search integration"
        ],
        limitations=[
            "Cannot access the internet directly (unless web search tool available)",
            "Workspace-bounded - cannot access files outside designated workspace",
            "Limited to explicit tool actions - cannot take autonomous physical actions",
            "May not have real-time information unless explicitly searched"
        ],
        behavioral_traits={
            "communication": "Clear, concise, and informative",
            "problem_solving": "Systematic and thorough",
            "error_handling": "Transparent about errors and limitations",
            "user_interaction": "Helpful and anticipatory"
        }
    )
    
    def __init__(self, config: Optional[IdentityConfig] = None, identity_path: str = "knowledge/identity.json"):
        self.config = config or self._load_or_default(identity_path)
        self._identity_path = identity_path
    
    def _load_or_default(self, path: str) -> IdentityConfig:
        """Load from file or return default"""
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    return IdentityConfig(**data)
            except Exception:
                pass
        return self.DEFAULT_CONFIG
    
    def save(self):
        """Save identity to file"""
        os.makedirs(os.path.dirname(self._identity_path) or ".", exist_ok=True)
        with open(self._identity_path, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=2)
    
    def get_name(self) -> str:
        """Get agent name"""
        return self.config.name
    
    def get_title(self) -> str:
        """Get agent title"""
        return self.config.title
    
    def get_full_identity(self) -> str:
        """Get complete identity description"""
        parts = [
            f"I am {self.config.name}, a {self.config.title}.",
            f"Version: {self.config.version}",
            f"Persona: {self.config.persona}.",
            "",
            "Core Capabilities:",
        ]
        
        for cap in self.config.core_capabilities:
            parts.append(f"  • {cap}")
        
        if self.config.limitations:
            parts.append("")
            parts.append("Limitations:")
            for lim in self.config.limitations:
                parts.append(f"  • {lim}")
        
        parts.append("")
        parts.append("Behavioral Traits:")
        for trait, desc in self.config.behavioral_traits.items():
            parts.append(f"  • {trait}: {desc}")
        
        return "\n".join(parts)
    
    def get_system_prompt_fragment(self) -> str:
        """Get identity fragment for system prompts"""
        return f"""AGENT IDENTITY:
You are {self.config.name}, a {self.config.title}.
Your persona: {self.config.persona}.

Capabilities you have access to:
{chr(10).join(f'- {cap}' for cap in self.config.core_capabilities)}

Important behavioral guidelines:
{chr(10).join(f'- {trait.replace('_', ' ').title()}: {desc}' for trait, desc in self.config.behavioral_traits.items())}"""
    
    def update_capability(self, capability: str, add: bool = True):
        """Add or remove a capability"""
        if add:
            if capability not in self.config.core_capabilities:
                self.config.core_capabilities.append(capability)
                self.config.last_updated = datetime.now().isoformat()
        else:
            if capability in self.config.core_capabilities:
                self.config.core_capabilities.remove(capability)
                self.config.last_updated = datetime.now().isoformat()
    
    def update_persona(self, persona: str):
        """Update the agent's persona"""
        self.config.persona = persona
        self.config.last_updated = datetime.now().isoformat()
    
    def update_name(self, name: str):
        """Update the agent's name"""
        self.config.name = name
        self.config.last_updated = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Export full identity as dict"""
        return self.config.to_dict()


def create_identity(
    name: str = "Obsidian",
    persona: str = None,
    capabilities: List[str] = None,
    identity_path: str = "knowledge/identity.json"
) -> AgentIdentity:
    """Factory to create a custom identity"""
    config = IdentityConfig(
        name=name,
        persona=persona or AgentIdentity.DEFAULT_CONFIG.persona,
        core_capabilities=capabilities or AgentIdentity.DEFAULT_CONFIG.core_capabilities
    )
    identity = AgentIdentity(config, identity_path)
    identity.save()
    return identity

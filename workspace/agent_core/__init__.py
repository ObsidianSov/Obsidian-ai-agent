"""
Agent Core - Obsidian AI Agent System

M0.2: Identity, Owner Profile & Grounded Context
- AgentIdentity: Agent's own identity and self-awareness
- OwnerProfileManager: Persistent user profile management
- GroundedContextProvider: Dynamic context injection
- ContextInjector: Integrates context into prompts
"""

from agent_core.identity import AgentIdentity, IdentityConfig, create_identity
from agent_core.owner_profile import OwnerProfile, OwnerProfileManager, create_owner_profile
from agent_core.grounded_context import (
    GroundedContext,
    GroundedContextProvider,
    ContextSource,
    create_context_provider
)
from agent_core.context_injector import (
    ContextInjector,
    InjectionConfig,
    ContextualAgentMixin,
    inject_context
)

__all__ = [
    # Identity
    "AgentIdentity",
    "IdentityConfig",
    "create_identity",
    
    # Owner Profile
    "OwnerProfile",
    "OwnerProfileManager",
    "create_owner_profile",
    
    # Grounded Context
    "GroundedContext",
    "GroundedContextProvider",
    "ContextSource",
    "create_context_provider",
    
    # Context Injection
    "ContextInjector",
    "InjectionConfig",
    "ContextualAgentMixin",
    "inject_context",
]

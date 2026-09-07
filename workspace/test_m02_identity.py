"""
Test Suite for M0.2 - Identity, Owner Profile & Grounded Context

Tests all components of the M0.2 module.
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime

# Add agent_core to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_tests():
    """Run all M0.2 tests"""
    print("=" * 60)
    print("M0.2 - Identity, Owner Profile & Grounded Context Tests")
    print("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    # Create temp workspace
    temp_dir = tempfile.mkdtemp()
    workspace = os.path.join(temp_dir, "test_workspace")
    os.makedirs(workspace)
    
    try:
        # === Test Identity System ===
        print("\n[Testing Identity System]")
        
        from agent_core.identity import AgentIdentity, IdentityConfig, create_identity
        
        # Test 1: Default identity
        identity = AgentIdentity()
        assert identity.get_name() == "Obsidian"
        print("  [PASS] Default identity name")
        tests_passed += 1
        
        # Test 2: Custom identity
        config = IdentityConfig(
            name="TestBot",
            persona="friendly, helpful",
            core_capabilities=["coding", "testing"]
        )
        identity2 = AgentIdentity(config=config)
        assert identity2.get_name() == "TestBot"
        assert identity2.config.persona == "friendly, helpful"
        print("  [PASS] Custom identity config")
        tests_passed += 1
        
        # Test 3: Full identity string
        full = identity.get_full_identity()
        assert "Obsidian" in full
        assert "Capabilities" in full
        assert "Limitations" in full
        print("  [PASS] Full identity generation")
        tests_passed += 1
        
        # Test 4: System prompt fragment
        fragment = identity.get_system_prompt_fragment()
        assert "AGENT IDENTITY" in fragment
        assert "Obsidian" in fragment
        print("  [PASS] System prompt fragment")
        tests_passed += 1
        
        # Test 5: Save/load identity
        identity_path = os.path.join(workspace, "knowledge/identity.json")
        identity3 = create_identity(
            name="SavedBot",
            persona="persistent",
            identity_path=identity_path
        )
        identity4 = AgentIdentity(identity_path=identity_path)
        assert identity4.get_name() == "SavedBot"
        print("  [PASS] Identity persistence")
        tests_passed += 1
        
        # Test 6: Update capability
        identity.update_capability("new_skill")
        assert "new_skill" in identity.config.core_capabilities
        print("  [PASS] Update capability")
        tests_passed += 1
        
        # === Test Owner Profile System ===
        print("\n[Testing Owner Profile System]")
        
        from agent_core.owner_profile import OwnerProfile, OwnerProfileManager, create_owner_profile
        
        # Test 7: Default profile
        profile_path = os.path.join(workspace, "knowledge/owner.json")
        manager = OwnerProfileManager(profile_path=profile_path)
        assert manager.get_name() == "User"
        print("  [PASS] Default owner profile")
        tests_passed += 1
        
        # Test 8: Set preferences
        manager.set_preference("verbose", False)
        assert manager.get_preference("verbose") == False
        print("  [PASS] Preference management")
        tests_passed += 1
        
        # Test 9: Workspace
        manager.set_workspace("/test/path")
        assert manager.get_workspace() == "/test/path"
        print("  [PASS] Workspace setting")
        tests_passed += 1
        
        # Test 10: Custom knowledge
        manager.add_knowledge("favorite_language", "Python")
        assert manager.get_knowledge("favorite_language") == "Python"
        print("  [PASS] Custom knowledge")
        tests_passed += 1
        
        # Test 11: Key facts
        manager.add_key_fact("I am a software developer")
        facts = manager.get_key_facts()
        assert "I am a software developer" in facts
        print("  [PASS] Key facts")
        tests_passed += 1
        
        # Test 12: Active tasks
        manager.add_active_task("Write tests")
        tasks = manager.get_active_tasks()
        assert "Write tests" in tasks
        print("  [PASS] Active tasks")
        tests_passed += 1
        
        # Test 13: Profile summary contains key sections
        summary = manager.get_summary()
        assert "OWNER PROFILE" in summary
        assert "Key Facts:" in summary  # Key facts section exists
        print("  [PASS] Profile summary")
        tests_passed += 1
        
        # Test 14: Profile persistence
        manager2 = OwnerProfileManager(profile_path=profile_path)
        assert manager2.get_knowledge("favorite_language") == "Python"
        assert "I am a software developer" in manager2.get_key_facts()
        print("  [PASS] Profile persistence")
        tests_passed += 1
        
        # Test 15: Context dict
        ctx_dict = manager.get_context_dict()
        assert "owner_name" in ctx_dict
        assert "custom_knowledge" in ctx_dict
        print("  [PASS] Context dict")
        tests_passed += 1
        
        # Test 16: Interaction tracking
        initial_count = manager.get_interaction_count()
        manager.record_interaction()
        assert manager.get_interaction_count() == initial_count + 1
        print("  [PASS] Interaction tracking")
        tests_passed += 1
        
        # === Test Grounded Context ===
        print("\n[Testing Grounded Context]")
        
        from agent_core.grounded_context import (
            GroundedContext, GroundedContextProvider, ContextSource
        )
        
        # Test 17: Context provider creation
        provider = GroundedContextProvider(
            owner_profile=manager,
            workspace=workspace
        )
        assert provider.workspace == workspace
        print("  [PASS] Context provider creation")
        tests_passed += 1
        
        # Test 18: Context refresh
        ctx = provider.refresh()
        assert ctx.timestamp != ""
        assert ctx.workspace != ""
        print("  [PASS] Context refresh")
        tests_passed += 1
        
        # Test 19: Time context
        assert ctx.timezone  # Timezone set
        assert ctx.timestamp  # Has timestamp
        print("  [PASS] Time context")
        tests_passed += 1
        
        # Test 20: System context
        assert ctx.hostname != ""
        assert ctx.platform != ""
        assert ctx.python_version != ""
        print("  [PASS] System context")
        tests_passed += 1
        
        # Test 21: Workspace context - use path comparison
        assert os.path.normpath(ctx.workspace) == os.path.normpath(os.path.abspath(workspace))
        print("  [PASS] Workspace context")
        tests_passed += 1
        
        # Test 22: Owner context injection
        provider2 = GroundedContextProvider(
            owner_profile=manager,
            workspace=workspace
        )
        ctx2 = provider2.refresh()
        assert ctx2.owner_context.get("name") == "User"
        print("  [PASS] Owner context injection")
        tests_passed += 1
        
        # Test 23: Context summary
        summary = provider.get_context_summary()
        assert "CURRENT CONTEXT" in summary
        assert "Time:" in summary
        print("  [PASS] Context summary")
        tests_passed += 1
        
        # Test 24: Focused context
        focused = provider.get_focused_context(["timestamp", "workspace"])
        assert "timestamp" in focused
        assert "workspace" in focused
        print("  [PASS] Focused context")
        tests_passed += 1
        
        # Test 25: Context sources
        source = provider.get_source("time")
        assert source is not None
        assert source.name == "time"
        print("  [PASS] Context sources")
        tests_passed += 1
        
        # === Test Context Injector ===
        print("\n[Testing Context Injector]")
        
        from agent_core.context_injector import (
            ContextInjector, InjectionConfig
        )
        
        # Test 26: Injector creation
        injector = ContextInjector(
            identity=identity,
            owner_profile=manager,
            grounded_context=provider
        )
        assert injector.identity is identity
        print("  [PASS] Context injector creation")
        tests_passed += 1
        
        # Test 27: System prompt injection
        base_prompt = "You are a helpful assistant."
        enhanced = injector.inject_system_prompt(base_prompt)
        assert "You are a helpful assistant" in enhanced
        assert "CONTEXT" in enhanced
        assert "AGENT IDENTITY" in enhanced
        print("  [PASS] System prompt injection")
        tests_passed += 1
        
        # Test 28: Task prompt
        task_prompt = injector.inject_task_prompt("Write a test")
        assert "Write a test" in task_prompt
        print("  [PASS] Task prompt injection")
        tests_passed += 1
        
        # Test 29: Full context
        full_ctx = injector.get_full_context()
        assert "identity" in full_ctx
        assert "owner" in full_ctx
        assert "grounded" in full_ctx
        print("  [PASS] Full context retrieval")
        tests_passed += 1
        
        # Test 30: Config options
        config = InjectionConfig(
            include_identity=False,
            include_time_context=False
        )
        injector2 = ContextInjector(
            identity=identity,
            owner_profile=manager,
            grounded_context=provider,
            config=config
        )
        enhanced2 = injector2.inject_system_prompt(base_prompt)
        # Should not include identity when disabled
        assert "AGENT IDENTITY" not in enhanced2
        print("  [PASS] Injection config options")
        tests_passed += 1
        
        # Test 31: Context for tools
        tool_ctx = injector.get_context_for_tools()
        assert "workspace" in tool_ctx
        assert "timezone" in tool_ctx
        print("  [PASS] Tool context")
        tests_passed += 1
        
        # Test 32: Memory format
        mem_format = injector.format_for_memory()
        assert "Time:" in mem_format or "Workspace:" in mem_format
        print("  [PASS] Memory format")
        tests_passed += 1
        
        # === Test Integration ===
        print("\n[Testing Integration]")
        
        from agent_core.agent import Agent, AgentConfig, create_agent
        
        # Test 33: Agent with context
        config = AgentConfig(
            name="TestAgent",
            context_enabled=True,
            verbose=False
        )
        # Don't initialize LLM for testing
        agent = Agent(config=config, workspace=workspace)
        
        assert agent.identity is not None
        assert agent.owner_profile is not None
        assert agent.grounded_context is not None
        print("  [PASS] Agent context initialization")
        tests_passed += 1
        
        # Test 34: Identity access
        identity_from_agent = agent.get_identity()
        assert identity_from_agent.get_name() == "TestAgent"
        print("  [PASS] Agent identity access")
        tests_passed += 1
        
        # Test 35: Owner profile access
        profile_from_agent = agent.get_owner_profile()
        profile_from_agent.set_preference("test_value", 123)
        assert profile_from_agent.get_preference("test_value") == 123
        print("  [PASS] Agent owner profile access")
        tests_passed += 1
        
        # Test 36: Context refresh
        ctx_data = agent.refresh_context()
        assert "timestamp" in ctx_data
        assert "workspace" in ctx_data
        print("  [PASS] Agent context refresh")
        tests_passed += 1
        
        # Test 37: Set owner name
        agent.set_owner_name("Test User")
        assert agent.owner_profile.get_name() == "Test User"
        print("  [PASS] Set owner name")
        tests_passed += 1
        
        # Test 38: Add key fact
        agent.add_key_fact("Testing is important")
        assert "Testing is important" in agent.owner_profile.get_key_facts()
        print("  [PASS] Add key fact")
        tests_passed += 1
        
        # Test 39: Set project
        agent.set_current_project("M0.2 Testing")
        assert agent.owner_profile.get_current_project() == "M0.2 Testing"
        print("  [PASS] Set current project")
        tests_passed += 1
        
        # Test 40: Add task
        agent.add_active_task("Complete M0.2 tests")
        assert "Complete M0.2 tests" in agent.owner_profile.get_active_tasks()
        print("  [PASS] Add active task")
        tests_passed += 1
        
        # Test 41: Context summary
        summary = agent.get_context_summary()
        assert "CURRENT CONTEXT" in summary
        print("  [PASS] Context summary")
        tests_passed += 1
        
        # Test 42: Inspect with context
        state = agent.inspect()
        assert "context" in state
        # Compare normalized paths
        assert os.path.normpath(state["context"]["workspace"]) == os.path.normpath(os.path.abspath(workspace))
        print("  [PASS] Agent inspect with context")
        tests_passed += 1
        
        # Test 43: create_agent factory
        agent2 = create_agent(name="FactoryBot", workspace=workspace, verbose=False)
        assert agent2.identity.get_name() == "FactoryBot"
        print("  [PASS] create_agent factory")
        tests_passed += 1
        
        # Test 44: Grounded context access
        ctx_provider = agent.get_grounded_context()
        ctx = ctx_provider.refresh()
        assert ctx.timestamp != ""
        print("  [PASS] Grounded context access")
        tests_passed += 1
        
        # Test 45: Task context creation
        task_ctx = agent.context_injector.create_task_context("Test task")
        assert "task" in task_ctx
        assert "identity" in task_ctx
        assert task_ctx["task"] == "Test task"
        print("  [PASS] Task context creation")
        tests_passed += 1
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        tests_failed += 1
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    # === Summary ===
    print("\n" + "=" * 60)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print("=" * 60)
    
    return tests_failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

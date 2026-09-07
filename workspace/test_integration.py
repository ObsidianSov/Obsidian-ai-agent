"""
Test suite for Phase 4: Full Integration
"""

import sys
import os

# Add agent_core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent_core'))


def test_agent_imports():
    """Test that agent module imports correctly"""
    print("Testing imports...")
    
    try:
        from agent_core.agent import Agent, AgentConfig, create_agent
        print("  [PASS] All imports successful")
        return True
    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        return False


def test_agent_config():
    """Test AgentConfig dataclass"""
    print("Testing AgentConfig...")
    
    from agent_core.agent import AgentConfig
    
    try:
        # Default config
        config = AgentConfig()
        assert config.name == "Obsidian"
        assert config.max_steps == 10
        assert config.llm_model is None  # now defers to OPENROUTER_MODEL / llm.py default
        print("  [PASS] Default config works")
        
        # Custom config
        config = AgentConfig(
            name="Custom",
            max_steps=5,
            llm_model="test/model",
            llm_temperature=0.5
        )
        assert config.name == "Custom"
        assert config.max_steps == 5
        assert config.llm_model == "test/model"
        print("  [PASS] Custom config works")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Config error: {e}")
        return False


def test_agent_initialization():
    """Test agent initialization"""
    print("Testing agent initialization...")
    
    from agent_core.agent import Agent, AgentConfig
    
    try:
        agent = Agent()
        assert agent.config is not None
        assert agent.tools is not None
        assert agent.memory is not None
        assert agent.executor is not None
        print("  [PASS] Agent initialized with all components")
        
        # Check if LLM is available
        if agent.llm_available:
            print(f"  [INFO] LLM available: {agent.config.llm_model}")
        else:
            print("  [INFO] LLM not available (no API key)")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_create_agent_factory():
    """Test factory function"""
    print("Testing create_agent factory...")
    
    from agent_core.agent import create_agent
    
    try:
        agent = create_agent(name="TestBot", verbose=False)
        assert agent.config.name == "TestBot"
        assert agent.config.verbose == False
        print("  [PASS] Factory function works")
        return True
    except Exception as e:
        print(f"  [FAIL] Factory error: {e}")
        return False


def test_get_tools():
    """Test getting tool list"""
    print("Testing get_tools...")
    
    from agent_core.agent import Agent
    
    try:
        agent = Agent()
        tools = agent.get_tools()
        
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert all("name" in t for t in tools)
        print(f"  [PASS] Found {len(tools)} tools")
        
        return True
    except Exception as e:
        print(f"  [FAIL] get_tools error: {e}")
        return False


def test_inspect():
    """Test agent inspection"""
    print("Testing inspect...")
    
    from agent_core.agent import Agent
    
    try:
        agent = Agent()
        state = agent.inspect()
        
        assert "name" in state
        assert "llm_available" in state
        assert "available_tools" in state
        assert "config" in state
        print("  [PASS] Agent inspection works")
        print(f"    LLM: {state['llm_available']}, Tools: {state['available_tools']}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] inspect error: {e}")
        return False


def test_memory_operations():
    """Test memory operations"""
    print("Testing memory operations...")
    
    from agent_core.agent import Agent
    
    try:
        agent = Agent()
        
        # Remember
        agent.remember("Test fact", importance=3)
        print("  [PASS] remember() works")
        
        # Recall
        result = agent.recall("test")
        # Truncate for display
        result_display = result[:50] + "..." if len(result) > 50 else result if result else "empty"
        print(f"  [PASS] recall() works: {result_display}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Memory error: {e}")
        return False


def test_simple_task():
    """Test running a simple task"""
    print("Testing simple task...")
    
    from agent_core.agent import Agent
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        agent = Agent()
        
        # Simple math task (should return final answer directly)
        response = agent.run("What is 3 + 4? Answer with just the number.")
        
        assert response is not None
        assert len(response) > 0
        print(f"  [PASS] Task completed")
        print(f"    Response: {response[:100]}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Task error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_task():
    """Test a task that uses a tool"""
    print("Testing tool task...")
    
    from agent_core.agent import Agent
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        agent = Agent()
        
        # Task that requires a tool
        response = agent.run("List the files in the current directory.")
        
        assert response is not None
        # Response should mention files or be the result
        print(f"  [PASS] Tool task completed")
        # Truncate for display
        response_display = response[:150] if len(response) > 150 else response
        print(f"    Response: {response_display}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Tool task error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trace_mode():
    """Test run_with_trace for debugging"""
    print("Testing trace mode...")
    
    from agent_core.agent import Agent
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        agent = Agent()
        
        response, trace = agent.run_with_trace("What is 1 + 1?")
        
        assert response is not None
        assert isinstance(trace, list)
        response_display = response[:50] + "..." if len(response) > 50 else response
        print(f"  [PASS] Trace mode works")
        print(f"    Steps: {len(trace)}, Response: {response_display}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Trace error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_step_task():
    """Test a multi-step task"""
    print("Testing multi-step task...")
    
    from agent_core.agent import Agent
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        agent = Agent()
        agent.config.max_steps = 5  # Allow more steps
        
        # Multi-step task
        response = agent.run(
            "What are the first 3 steps to make a cup of tea?"
        )
        
        assert response is not None
        # Truncate for display
        response_display = response[:200] + "..." if len(response) > 200 else response
        print(f"  [PASS] Multi-step task completed")
        print(f"    Response: {response_display}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Multi-step error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 4 tests"""
    print("=" * 60)
    print("PHASE 4: Full Integration - Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_agent_imports,
        test_agent_config,
        test_agent_initialization,
        test_create_agent_factory,
        test_get_tools,
        test_inspect,
        test_memory_operations,
        test_simple_task,
        test_tool_task,
        test_trace_mode,
        test_multi_step_task,
    ]
    
    results = []
    for test in tests:
        try:
            passed = test()
            results.append(passed)
        except Exception as e:
            print(f"  [ERROR] Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        print()
    
    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] PHASE 4 COMPLETE - Obsidian AI fully integrated!")
    else:
        print("[FAILURE] Some tests failed - review above")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

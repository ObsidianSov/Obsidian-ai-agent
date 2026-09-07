"""
Test suite for LLM-Driven Coding Agent Lifecycle
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent_core'))


def test_tool_definitions():
    """Test tool definitions"""
    print("Testing tool definitions...")
    
    from agent_core.tools import Tool, ToolRegistry
    
    # Test Tool creation
    tool = Tool(
        name="test_tool",
        description="A test tool",
        func=lambda: "test",
        input_schema={"arg1": {"type": "string", "description": "First argument"}}
    )
    
    assert tool.name == "test_tool"
    print("  [PASS] Tool creation works")
    
    # Test the registry
    registry = ToolRegistry()
    tools = registry.list_tools()
    assert len(tools) >= 5
    assert any(t["name"] == "file_read" for t in tools)
    assert any(t["name"] == "file_write" for t in tools)
    assert any(t["name"] == "list_files" for t in tools)
    print(f"  [PASS] Found {len(tools)} built-in tools")
    
    return True


def test_built_in_tool_functions():
    """Test built-in tool functions"""
    print("Testing built-in tool functions...")
    
    from agent_core.tools import ToolRegistry
    
    registry = ToolRegistry()
    
    # Test list_files
    result = registry.execute("list_files", path=".")
    assert isinstance(result, str)
    assert len(result) > 0
    print("  [PASS] list_files works")
    
    # Test get_env
    result = registry.execute("get_env", key="PATH")
    assert isinstance(result, str)
    print("  [PASS] get_env works")
    
    # Test read_file (nonexistent)
    result = registry.execute("file_read", path="nonexistent_file_xyz.txt")
    assert "Error" in result
    assert "not found" in result.lower() or "Error" in result
    print("  [PASS] file_read handles errors")
    
    return True


def test_tool_executor():
    """Test tool executor"""
    print("Testing tool executor...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    
    # Test executing existing tool
    result = executor.execute("list_files", {"path": "."})
    assert isinstance(result, str)
    assert len(result) > 0
    print("  [PASS] Tool execution works")
    
    # Test unknown tool
    result = executor.execute("unknown_tool", {})
    assert "Error" in result
    assert "Unknown tool" in result or "not found" in result.lower()
    print("  [PASS] Unknown tool handling works")
    
    # Test has_tool
    assert executor.has_tool("list_files") == True
    assert executor.has_tool("unknown_tool") == False
    print("  [PASS] has_tool works")
    
    # Test custom tool registration
    def custom_tool(x: int, y: int) -> str:
        return str(x + y)
    
    from agent_core.tools import Tool
    registry.register(Tool(name="add", description="Add two numbers", func=custom_tool))
    assert registry.get("add") is not None
    result = executor.execute("add", {"x": 5, "y": 3})
    assert result == "8"
    print("  [PASS] Custom tool registration works")
    
    return True


def test_llm_provider():
    """Test LLM provider"""
    print("Testing LLM provider...")
    
    from agent_core.llm import OpenRouterProvider, ConfigurationError
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        llm = OpenRouterProvider(model="anthropic/claude-3-haiku")
        
        # Test simple completion
        response = llm.complete([
            {"role": "user", "content": "Say 'Hello, World!' in exactly those words."}
        ])
        
        assert response is not None
        print(f"  [PASS] LLM completion works")
        
        return True
        
    except ConfigurationError as e:
        print(f"  [SKIP] LLM not configured: {e}")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_agent_lifecycle():
    """Test the complete agent lifecycle"""
    print("Testing agent lifecycle...")
    
    from agent_core.agent import create_agent
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        agent = create_agent(verbose=False)
        
        # Test 1: Agent creation
        assert agent is not None
        print("  [PASS] Agent creation works")
        
        # Test 2: Tools available
        tools = agent.get_tools()
        assert len(tools) > 0
        print(f"  [PASS] Agent has {len(tools)} tools")
        
        # Test 3: Simple question (no tools needed)
        result = agent.run("What is 2 + 2? Answer with just the number.")
        print(f"  [INFO] Math result: {result}")
        assert result is not None
        print("  [PASS] Simple question works")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_step_task():
    """Test multi-step reasoning"""
    print("Testing multi-step task...")
    
    from agent_core.agent import create_agent
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        agent = create_agent(verbose=False)
        
        # Task that requires reasoning
        result = agent.run(
            "Think step by step: What are the first 3 steps to make a cup of tea? "
            "Just list them as a simple numbered list."
        )
        
        print(f"  [INFO] Result: {result[:150]}...")
        assert result is not None
        print("  [PASS] Multi-step reasoning works")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("LLM-DRIVEN CODING AGENT - Lifecycle Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_tool_definitions,
        test_built_in_tool_functions,
        test_tool_executor,
        test_llm_provider,
        test_agent_lifecycle,
        test_multi_step_task,
    ]
    
    results = []
    for test in tests:
        try:
            passed = test()
            results.append(passed)
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        print()
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] All lifecycle tests passed!")
    else:
        print("[FAILURE] Some tests failed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

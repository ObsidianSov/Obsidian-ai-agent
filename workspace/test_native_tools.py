"""
Test suite for Native Tool Calling
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent_core'))


def test_tool_definition():
    """Test ToolDefinition dataclass"""
    print("Testing ToolDefinition...")
    
    from agent_core.llm import ToolDefinition
    
    tool = ToolDefinition(
        name="file_write",
        description="Write to a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "Content"}
            },
            "required": ["path", "content"]
        }
    )
    
    assert tool.name == "file_write"
    assert "path" in tool.parameters["properties"]
    print("  [PASS] ToolDefinition works")
    return True


def test_tool_call():
    """Test ToolCall dataclass"""
    print("Testing ToolCall...")
    
    from agent_core.llm import ToolCall
    
    tc = ToolCall(
        id="call_123",
        name="file_write",
        arguments={"path": "test.txt", "content": "hello"}
    )
    
    assert tc.id == "call_123"
    assert tc.name == "file_write"
    assert tc.arguments["path"] == "test.txt"
    print("  [PASS] ToolCall works")
    return True


def test_llm_response():
    """Test LLMResponse with tool calls"""
    print("Testing LLMResponse...")
    
    from agent_core.llm import LLMResponse, ToolCall
    
    # Response with tool call
    response = LLMResponse(
        content=None,
        tool_calls=[
            ToolCall(id="call_1", name="list_files", arguments={"path": "."})
        ],
        model="test-model",
        finish_reason="tool_calls"
    )
    
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "list_files"
    assert response.finish_reason == "tool_calls"
    print("  [PASS] LLMResponse with tool_calls works")
    
    # Response with content
    response2 = LLMResponse(
        content="The answer is 42",
        tool_calls=[],
        model="test-model",
        finish_reason="stop"
    )
    
    assert response2.content == "The answer is 42"
    assert len(response2.tool_calls) == 0
    print("  [PASS] LLMResponse with content works")
    
    return True


def test_provider_with_tools():
    """Test provider with native tool calling"""
    print("Testing provider with native tools...")
    
    from agent_core.llm import OpenRouterProvider, ToolDefinition
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        
        tools = [
            ToolDefinition(
                name="list_files",
                description="List files in a directory",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path", "default": "."}
                    }
                }
            )
        ]
        
        response = provider.complete_with_tools(
            "List the files in the current directory",
            tools=tools,
            system_prompt="You have access to tools. Use them when needed.",
            reset=True
        )
        
        print(f"  [INFO] Finish reason: {response.finish_reason}")
        
        if response.tool_calls:
            print(f"  [PASS] LLM requested tool: {response.tool_calls[0].name}")
            print(f"  [INFO] Arguments: {response.tool_calls[0].arguments}")
            
            # Add tool result
            result = "file1.txt\nfile2.txt\nfolder/"
            provider.add_tool_result(response.tool_calls[0].id, result)
            
            # Continue
            final = provider.continue_conversation(tools=tools)
            print(f"  [PASS] Final response: {final.content[:100] if final.content else 'No content'}")
        else:
            print(f"  [PASS] LLM responded directly: {response.content[:50]}")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_native_react_engine():
    """Test native ReAct engine"""
    print("Testing NativeReActEngine...")
    
    from agent_core.reasoning import NativeReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = NativeReActEngine(provider, max_steps=5)
        
        # Simple task that doesn't need tools
        engine.reset(
            task="What is 2 + 2? Answer with just the number.",
            tools=[],
            context={}
        )
        
        result = engine.run()
        
        print(f"  [PASS] Result: {result}")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_native_tools():
    """Test Agent with native tool calling"""
    print("Testing Agent with native tools...")
    
    from agent_core.agent import Agent
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        agent = Agent()
        
        # Simple math task
        response = agent.run("What is 5 + 3?")
        print(f"  [PASS] Math task: {response}")
        
        # File listing task (uses tool)
        response = agent.run("List files in the current directory")
        print(f"  [PASS] List files: {response[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_step_tool_call():
    """Test multiple tool calls in sequence"""
    print("Testing multi-step tool calls...")
    
    from agent_core.agent import Agent
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        agent = Agent()
        
        # Task that might require multiple tools
        response, trace = agent.run_with_trace(
            "Read the contents of any text file in the current directory if one exists, otherwise list the files."
        )
        
        print(f"  [INFO] Steps: {len(trace)}")
        for i, step in enumerate(trace):
            if "tool_call" in step:
                tc = step["tool_call"]
                print(f"    Step {i+1}: {tc['name']} -> {tc['result'][:50]}...")
            elif "final" in step:
                print(f"    Final: {step['final'][:50]}...")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("NATIVE TOOL CALLING - Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_tool_definition,
        test_tool_call,
        test_llm_response,
        test_provider_with_tools,
        test_native_react_engine,
        test_agent_native_tools,
        test_multi_step_tool_call,
    ]
    
    results = []
    for test in tests:
        try:
            print()
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
        print("[SUCCESS] Native tool calling working!")
    else:
        print("[FAILURE] Some tests failed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

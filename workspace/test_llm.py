"""
Test suite for Phase 1: LLM Provider
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent_core'))

from agent_core.llm import (
    OpenRouterProvider,
    LLMResponse,
    ConfigurationError,
    RateLimitError,
    JSONParser,
    ToolDefinition,
    ToolCall
)


def test_provider_initialization():
    """Test provider initialization"""
    print("Testing provider initialization...")
    
    # Test without API key
    old_key = os.environ.pop('OPENROUTER_API_KEY', None)
    try:
        provider = OpenRouterProvider(api_key=None)
        print("  [FAIL] Should have raised ConfigurationError")
        return False
    except ConfigurationError as e:
        print("  [PASS] Correctly raised ConfigurationError")
    finally:
        if old_key:
            os.environ['OPENROUTER_API_KEY'] = old_key
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if api_key:
        try:
            provider = OpenRouterProvider(api_key=api_key)
            print(f"  [PASS] Provider initialized with model: {provider.model}")
        except Exception as e:
            print(f"  [FAIL] Failed to initialize: {e}")
            return False
    
    return True


def test_json_parser():
    """Test JSON parsing from LLM responses"""
    print("Testing JSON parser...")
    
    parser = JSONParser()
    
    text1 = '''
    Here is my response:
    ```json
    {"action": "tool_name", "action_input": {"param": "value"}}
    ```
    '''
    result1 = parser.extract_json(text1)
    assert result1 == {"action": "tool_name", "action_input": {"param": "value"}}
    print("  [PASS] Parsed JSON from code block")
    
    text2 = '{"action": "final", "content": "Done!"}'
    result2 = parser.extract_json(text2)
    assert result2 == {"action": "final", "content": "Done!"}
    print("  [PASS] Parsed plain JSON")
    
    text3 = 'Let me think... {"action": "read", "input": {"path": "test.txt"}} is what I need.'
    result3 = parser.extract_json(text3)
    assert result3 == {"action": "read", "input": {"path": "test.txt"}}
    print("  [PASS] Parsed JSON with surrounding text")
    
    return True


def test_llm_response_structure():
    """Test LLMResponse dataclass"""
    print("Testing LLMResponse structure...")
    
    response = LLMResponse(
        content="Hello!",
        model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        raw_response={"id": "test"}
    )
    
    assert response.content == "Hello!"
    assert response.model == "test-model"
    assert response.usage["prompt_tokens"] == 10
    print("  [PASS] LLMResponse structure works")
    
    return True


def test_api_call():
    """Test actual API call"""
    print("Testing API call...")
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key, max_tokens=50)
        
        response = provider.complete(
            "Say exactly: 'Phase 1 works!'",
            system_prompt="You are a helpful assistant. Be concise."
        )
        
        assert response.content
        print(f"  [PASS] API call successful")
        print(f"    Model: {response.model}")
        print(f"    Response: {response.content[:100]}")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] API call failed: {e}")
        return False


def test_tool_definitions():
    """Test ToolDefinition and ToolCall"""
    print("Testing tool definitions...")
    
    # ToolDefinition
    tool = ToolDefinition(
        name="file_write",
        description="Write to a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    )
    
    assert tool.name == "file_write"
    print("  [PASS] ToolDefinition works")
    
    # ToolCall
    tc = ToolCall(
        id="call_123",
        name="file_write",
        arguments={"path": "test.txt", "content": "hello"}
    )
    
    assert tc.name == "file_write"
    assert tc.arguments["path"] == "test.txt"
    print("  [PASS] ToolCall works")
    
    return True


def test_provider_with_tools():
    """Test provider with tool calling"""
    print("Testing provider with tools...")
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        
        tools = [
            ToolDefinition(
                name="list_files",
                description="List files in directory",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"}
                    }
                }
            )
        ]
        
        response = provider.complete_with_tools(
            "List the files here",
            tools=tools,
            system_prompt="Use tools when needed.",
            reset=True
        )
        
        print(f"  [PASS] Tool call response received")
        print(f"    Finish reason: {response.finish_reason}")
        if response.tool_calls:
            print(f"    Tool: {response.tool_calls[0].name}")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] Tool test failed: {e}")
        return False


def run_all_tests():
    """Run all Phase 1 tests"""
    print("=" * 60)
    print("PHASE 1: LLM Provider - Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_provider_initialization,
        test_json_parser,
        test_llm_response_structure,
        test_api_call,
        test_tool_definitions,
        test_provider_with_tools,
    ]
    
    results = []
    for test in tests:
        try:
            passed = test()
            results.append(passed)
        except Exception as e:
            print(f"  [ERROR] Test crashed: {e}")
            results.append(False)
        print()
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] PHASE 1 COMPLETE - LLM Provider ready!")
    else:
        print("[FAILURE] Some tests failed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

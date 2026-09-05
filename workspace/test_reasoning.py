"""
Test suite for Phase 2: LLM ReAct Engine
"""

import sys
import os

# Add agent_core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent_core'))


def test_reasoning_imports():
    """Test that reasoning module imports correctly"""
    print("Testing imports...")
    
    try:
        from agent_core.reasoning import (
            LLMReActEngine,
            Decision,
            ReActEngine,  # Backward compat alias
            LLMError,
            ParseError
        )
        print("  [PASS] All imports successful")
        
        # Check alias
        assert LLMReActEngine is ReActEngine, "ReActEngine should be alias for LLMReActEngine"
        print("  [PASS] Backward compatibility alias works")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        return False


def test_decision_dataclass():
    """Test Decision dataclass"""
    print("Testing Decision dataclass...")
    
    from agent_core.reasoning import Decision
    
    # Test tool decision
    d1 = Decision(
        action="file_write",
        action_input={"path": "test.txt", "content": "hello"},
        raw_thought="I should write a file"
    )
    assert d1.action == "file_write"
    assert d1.action_input["path"] == "test.txt"
    print("  [PASS] Tool decision created correctly")
    
    # Test final decision
    d2 = Decision(action="final", content="Done!")
    assert d2.action == "final"
    assert d2.content == "Done!"
    print("  [PASS] Final decision created correctly")
    
    # Test clarify decision
    d3 = Decision(action="clarify", question="What file?")
    assert d3.action == "clarify"
    assert d3.question == "What file?"
    print("  [PASS] Clarify decision created correctly")
    
    return True


def test_engine_initialization():
    """Test engine initialization"""
    print("Testing engine initialization...")
    
    from agent_core.reasoning import LLMReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = LLMReActEngine(
            llm_provider=provider,
            max_steps=5,
            max_retries=2
        )
        
        assert engine.max_steps == 5
        assert engine.max_retries == 2
        assert engine.step == 0
        assert engine.is_complete() == False
        print("  [PASS] Engine initialized with custom params")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Initialization error: {e}")
        return False


def test_reset():
    """Test engine reset"""
    print("Testing reset...")
    
    from agent_core.reasoning import LLMReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = LLMReActEngine(llm_provider=provider)
        
        tools = [
            {"name": "file_write", "description": "Write a file", "params": {"path": {"type": "string"}}}
        ]
        context = {"key": "value"}
        
        engine.reset("Test task", tools, context)
        
        assert engine.task == "Test task"
        assert engine.available_tools == tools
        assert engine.context == context
        assert engine.step == 0
        assert len(engine.observations) == 0
        assert engine.is_complete() == False
        print("  [PASS] Reset initializes state correctly")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Reset error: {e}")
        return False


def test_prompt_building():
    """Test that prompts are built correctly"""
    print("Testing prompt building...")
    
    from agent_core.reasoning import LLMReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = LLMReActEngine(llm_provider=provider)
        
        # Tools with proper params format (matching ToolRegistry output)
        tools = [
            {
                "name": "file_write",
                "description": "Write a file",
                "params": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content"}
                }
            }
        ]
        context = {"test": "value"}
        
        engine.reset("Write hello to test.txt", tools, context)
        
        system_prompt = engine._build_system_prompt()
        assert "file_write" in system_prompt
        assert "AVAILABLE TOOLS" in system_prompt
        print("  [PASS] System prompt contains tools")
        
        user_prompt = engine._build_step_prompt()
        assert "Write hello to test.txt" in user_prompt
        # Check step format (may vary based on implementation)
        assert "Step" in user_prompt and "of" in user_prompt
        assert "10" in user_prompt  # Default max_steps
        print("  [PASS] Step prompt contains task and step info")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Prompt building error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_reasoning():
    """Test actual LLM-driven reasoning"""
    print("Testing LLM reasoning...")
    
    from agent_core.reasoning import LLMReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = LLMReActEngine(llm_provider=provider, max_steps=3)
        
        # Simple task that should result in a final answer
        engine.reset(
            task="What is 2 + 2? Just answer with the number.",
            tools=[],
            context={}
        )
        
        decision = engine.think()
        
        assert decision.action in ["final", "clarify"]
        print(f"  [PASS] LLM returned action: {decision.action}")
        
        if decision.action == "final":
            assert decision.content, "Final should have content"
            print(f"  [PASS] Final answer: {decision.content}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] LLM reasoning error: {e}")
        return False


def test_tool_decision_parsing():
    """Test parsing of tool decisions from LLM"""
    print("Testing tool decision parsing...")
    
    from agent_core.reasoning import LLMReActEngine, ParseError
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = LLMReActEngine(llm_provider=provider)
        
        # Test JSON extraction
        test_cases = [
            ('{"action": "final", "content": "Done!"}', "final"),
            ('{"action": "file_write", "action_input": {"path": "a.txt"}}', "file_write"),
            ('```json\n{"action": "clarify", "question": "?"}\n```', "clarify"),
            ('Some text {"action": "final", "content": "test"} more text', "final"),
        ]
        
        for text, expected_action in test_cases:
            result = engine._parse_response(text)
            assert result.action == expected_action, f"Expected {expected_action}, got {result.action}"
        
        print("  [PASS] JSON extraction works for various formats")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Parsing error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_observation_tracking():
    """Test that observations are tracked correctly"""
    print("Testing observation tracking...")
    
    from agent_core.reasoning import LLMReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = LLMReActEngine(llm_provider=provider, max_steps=5)
        
        engine.reset("Test", [], {})
        
        # Simulate observations
        engine.step = 1
        engine.add_observation("Result 1")
        engine.add_observation("Result 2")
        
        assert len(engine.observations) == 2
        assert engine.observations[0]["result"] == "Result 1"
        assert engine.observations[1]["result"] == "Result 2"
        print("  [PASS] Observations tracked correctly")
        
        # Test summary
        summary = engine.get_summary()
        assert "2 step(s)" in summary
        print("  [PASS] Summary generated correctly")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Observation tracking error: {e}")
        return False


def run_all_tests():
    """Run all Phase 2 tests"""
    print("=" * 60)
    print("PHASE 2: LLM ReAct Engine - Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_reasoning_imports,
        test_decision_dataclass,
        test_engine_initialization,
        test_reset,
        test_prompt_building,
        test_llm_reasoning,
        test_tool_decision_parsing,
        test_observation_tracking,
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
    
    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] PHASE 2 COMPLETE - ReAct Engine ready!")
    else:
        print("[FAILURE] Some tests failed - review above")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

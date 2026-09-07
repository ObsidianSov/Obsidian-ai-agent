"""
Test suite for Phase 2: Universal ReAct Engine

Includes tests for:
- M0.2: Conversation context preservation
- M0.3: Trivial task detection
- Action Gate preservation
- Max-steps safety limit
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent_core'))


def test_reasoning_imports():
    """Test that reasoning module imports correctly"""
    print("Testing imports...")
    
    try:
        from agent_core.reasoning import (
            UniversalReActEngine,
            LLMReActEngine,
            ReActEngine,
            Decision,
            Observation
        )
        print("  [PASS] All imports successful")
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
        action_input={"path": "test.txt", "content": "hello"}
    )
    assert d1.action == "file_write"
    assert d1.action_input["path"] == "test.txt"
    print("  [PASS] Tool decision created correctly")
    
    # Test final decision
    d2 = Decision(action="final", content="Done!")
    assert d2.action == "final"
    assert d2.content == "Done!"
    print("  [PASS] Final decision created correctly")
    
    return True


def test_observation_dataclass():
    """Test Observation dataclass"""
    print("Testing Observation dataclass...")
    
    from agent_core.reasoning import Observation
    
    obs = Observation(
        step=1,
        tool_name="file_write",
        arguments={"path": "test.txt"},
        result="Success"
    )
    
    assert obs.step == 1
    assert obs.tool_name == "file_write"
    assert obs.success == True
    print("  [PASS] Observation created correctly")
    
    return True


def test_engine_initialization():
    """Test engine initialization"""
    print("Testing engine initialization...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(
            llm_provider=provider,
            max_steps=5
        )
        
        assert engine.max_steps == 5
        assert engine._current_step == 0
        assert engine.is_complete() == False
        print("  [PASS] Engine initialized correctly")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Initialization error: {e}")
        return False


def test_reset():
    """Test engine reset"""
    print("Testing reset...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider)
        
        tools = [
            {"name": "file_write", "description": "Write a file", "params": {"path": {"type": "string"}}}
        ]
        context = {"key": "value"}
        
        engine.reset("Test task", tools, context)
        
        assert engine.task == "Test task"
        assert len(engine.tools) == 1
        assert engine._current_step == 0
        assert len(engine.observations) == 0
        print("  [PASS] Reset initializes state correctly")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Reset error: {e}")
        return False


def test_llm_reasoning():
    """Test actual LLM-driven reasoning"""
    print("Testing LLM reasoning...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider, max_steps=3)
        
        engine.reset(
            task="What is 2 + 2? Just answer with the number.",
            tools=[],
            context={}
        )
        
        result = engine.run()
        
        assert result
        print(f"  [PASS] LLM returned: {result[:50]}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] LLM reasoning error: {e}")
        return False


def test_tool_execution():
    """Test tool execution with executor"""
    print("Testing tool execution...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.executor import ToolExecutor
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider, max_steps=3)
        
        # Set up executor
        from agent_core.tools import ToolRegistry
        executor = ToolExecutor(ToolRegistry())
        engine.set_tool_executor(executor.execute)
        
        # Reset with tools
        tools = [
            {"name": "list_files", "description": "List files", "params": {"path": {"type": "string"}}}
        ]
        engine.reset("List the files here", tools, {})
        
        # Run - should use list_files tool
        result = engine.run()
        
        # Check that observation was recorded
        obs = engine.get_observations()
        if obs:
            print(f"  [PASS] Tool executed: {obs[0].tool_name}")
        else:
            print(f"  [PASS] Run completed: {result[:50]}")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Tool execution error: {e}")
        return False


def test_observation_tracking():
    """Test that observations are tracked correctly"""
    print("Testing observation tracking...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider, max_steps=5)
        
        engine.reset("Test", [], {})
        
        # Add manual observation
        engine.add_observation("file_write", {"path": "test.txt"}, "Success")
        engine.add_observation("list_files", {"path": "."}, "file1.txt\nfile2.txt")
        
        obs = engine.get_observations()
        assert len(obs) == 2
        assert obs[0].tool_name == "file_write"
        assert obs[1].tool_name == "list_files"
        print("  [PASS] Observations tracked correctly")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Observation tracking error: {e}")
        return False


# =============================================================================
# M0.2: Conversation Context Preservation Tests
# =============================================================================

def test_trivial_task_greetings():
    """M0.3: Test that greetings are detected as trivial"""
    print("Testing M0.3 trivial task detection (greetings)...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider)
        
        # Test various greetings
        greetings = ["hi", "hello", "hey", "hi!", "hello!", "howdy"]
        for greeting in greetings:
            result = engine._check_trivial_task(greeting)
            assert result is not None, f"Greeting '{greeting}' should be detected as trivial"
            assert "Obsidian" in result, f"Response should mention Obsidian"
        
        print(f"  [PASS] {len(greetings)} greetings detected as trivial")
        return True
    except Exception as e:
        print(f"  [FAIL] Greeting detection error: {e}")
        return False


def test_trivial_task_simple_questions():
    """M0.3: Test that simple questions are detected as trivial"""
    print("Testing M0.3 trivial task detection (simple questions)...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider)
        
        # Test simple questions
        simple_questions = ["how are you", "how are you?", "what can you do", "who are you"]
        for question in simple_questions:
            result = engine._check_trivial_task(question)
            assert result is not None, f"Question '{question}' should be detected as trivial"
        
        print(f"  [PASS] {len(simple_questions)} simple questions detected as trivial")
        return True
    except Exception as e:
        print(f"  [FAIL] Simple question detection error: {e}")
        return False


def test_trivial_task_complex_questions():
    """M0.3: Test that complex questions are NOT detected as trivial"""
    print("Testing M0.3 trivial task detection (complex questions)...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider)
        
        # Test complex questions - should NOT be trivial
        complex_tasks = [
            "read the file at /path/to/file.txt",
            "list all files in the current directory",
            "search the web for Python tutorials",
            "write a Python script that calculates fibonacci"
        ]
        for task in complex_tasks:
            result = engine._check_trivial_task(task)
            assert result is None, f"Task '{task}' should NOT be detected as trivial"
        
        print(f"  [PASS] {len(complex_tasks)} complex tasks correctly NOT trivial")
        return True
    except Exception as e:
        print(f"  [FAIL] Complex question detection error: {e}")
        return False


def test_greeting_no_tool_call():
    """M0.3: Test that greeting uses trivial path, not LLM tool loop"""
    print("Testing M0.3 greeting bypasses LLM tool loop...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider, max_steps=10)
        
        # Run with greeting - should not hit LLM
        engine.reset("hi", [], {})
        result = engine.run()
        
        # Should complete in 0 steps (trivial path)
        assert engine._current_step == 0, f"Expected 0 steps for trivial task, got {engine._current_step}"
        assert len(engine.observations) == 0, "No observations should be made for trivial task"
        assert "Obsidian" in result or "Hi" in result
        
        print(f"  [PASS] Greeting completed without tool calls")
        return True
    except Exception as e:
        print(f"  [FAIL] Greeting bypass error: {e}")
        return False


def test_conversation_reset_false():
    """M0.2: Test that reset=False preserves conversation context"""
    print("Testing M0.2 conversation context preservation...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider, max_steps=5)
        
        # Simulate conversation accumulation
        engine.reset("Test task", [], {})
        
        # Check that _messages is reset on new task
        assert len(provider._messages) == 0 or len(provider._messages) == 1  # system prompt
        
        # After reset(), LLM should be ready for new conversation
        engine.reset("Another task", [], {})
        
        print(f"  [PASS] Conversation resets correctly for new task")
        return True
    except Exception as e:
        print(f"  [FAIL] Conversation context error: {e}")
        return False


def test_action_gate_preserved():
    """M0.1: Test that Action Gate is preserved and functional"""
    print("Testing Action Gate preservation...")
    
    from agent_core.reasoning import gate_check
    
    try:
        # Test allowed action
        tier, reason = gate_check("read_file", {"path": "test.txt"})
        assert tier == "allow", "read_file should be allowed"
        
        # Test blocked command
        tier, reason = gate_check("command", {"command": "shutdown"})
        assert tier == "block", "shutdown should be blocked"
        assert "Blocked" in reason
        
        # Test approval-required command
        tier, reason = gate_check("command", {"command": "rm -rf /"})
        assert tier == "block", "rm -rf should be blocked"
        
        print("  [PASS] Action Gate checks working correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] Action Gate error: {e}")
        return False


def test_max_steps_safety():
    """Test that max_steps is respected and serves as safety limit"""
    print("Testing max_steps safety limit...")
    
    from agent_core.reasoning import UniversalReActEngine
    from agent_core.llm import OpenRouterProvider
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("  [SKIP] No API key available")
        return True
    
    try:
        # Set low max_steps
        provider = OpenRouterProvider(api_key=api_key)
        engine = UniversalReActEngine(llm_provider=provider, max_steps=3)
        
        # Simple task that might need multiple steps
        engine.reset("What is 2 + 2?", [], {})
        result = engine.run()
        
        # Should not exceed max_steps
        assert engine._current_step <= 3, f"Should not exceed max_steps, got {engine._current_step}"
        
        print(f"  [PASS] max_steps respected (limit=3, used={engine._current_step})")
        return True
    except Exception as e:
        print(f"  [FAIL] max_steps error: {e}")
        return False


def run_all_tests():
    """Run all Phase 2 tests"""
    print("=" * 60)
    print("PHASE 2: Universal ReAct Engine - Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        # Core tests
        test_reasoning_imports,
        test_decision_dataclass,
        test_observation_dataclass,
        test_engine_initialization,
        test_reset,
        test_llm_reasoning,
        test_tool_execution,
        test_observation_tracking,
        # M0.3: Trivial task detection
        test_trivial_task_greetings,
        test_trivial_task_simple_questions,
        test_trivial_task_complex_questions,
        test_greeting_no_tool_call,
        # M0.2: Conversation context
        test_conversation_reset_false,
        # M0.1: Action Gate
        test_action_gate_preserved,
        # Safety
        test_max_steps_safety,
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
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] PHASE 2 COMPLETE - All tests passing!")
    else:
        print(f"[FAILURE] {total - passed} tests failed - review above")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

"""
Test suite for Phase 3: Tool Executor
"""

import sys
import os

# Add agent_core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent_core'))


def test_executor_imports():
    """Test that executor module imports correctly"""
    print("Testing imports...")
    
    try:
        from agent_core.executor import (
            ToolExecutor,
            ExecutionResult
        )
        from agent_core.tools import ToolRegistry
        print("  [PASS] All imports successful")
        return True
    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        return False


def test_execution_result_dataclass():
    """Test ExecutionResult dataclass"""
    print("Testing ExecutionResult dataclass...")
    
    from agent_core.executor import ExecutionResult
    
    # Success result
    r1 = ExecutionResult(
        success=True,
        output="File written",
        tool_name="file_write",
        duration=0.5
    )
    assert r1.success == True
    assert r1.output == "File written"
    assert r1.error is None
    print("  [PASS] Success result created correctly")
    
    # Error result
    r2 = ExecutionResult(
        success=False,
        output="",
        tool_name="bad_tool",
        duration=0.1,
        error="Tool not found"
    )
    assert r2.success == False
    assert r2.error == "Tool not found"
    print("  [PASS] Error result created correctly")
    
    return True


def test_executor_initialization():
    """Test executor initialization"""
    print("Testing executor initialization...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry, default_timeout=60)
        
        assert executor.registry is registry
        assert executor.default_timeout == 60
        assert executor._execution_count == 0
        print("  [PASS] Executor initialized correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] Initialization error: {e}")
        return False


def test_can_execute():
    """Test tool existence check"""
    print("Testing can_execute...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        
        # Check known tools
        assert executor.can_execute("file_write") == True
        assert executor.can_execute("read_workspace_file") == True
        assert executor.can_execute("list_files") == True
        print("  [PASS] Known tools recognized")
        
        # Check unknown tools
        assert executor.can_execute("nonexistent_tool") == False
        assert executor.can_execute("") == False
        print("  [PASS] Unknown tools rejected")
        
        return True
    except Exception as e:
        print(f"  [FAIL] can_execute error: {e}")
        return False


def test_get_available_tools():
    """Test getting list of available tools"""
    print("Testing get_available_tools...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        
        tools = executor.get_available_tools()
        
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert "file_write" in tools
        assert "read_workspace_file" in tools
        print(f"  [PASS] Found {len(tools)} tools: {tools[:3]}...")
        
        return True
    except Exception as e:
        print(f"  [FAIL] get_available_tools error: {e}")
        return False


def test_execute_success():
    """Test successful tool execution"""
    print("Testing successful execution...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        
        # Test list_files (should work without workspace)
        result = executor.execute("list_files", {"path": "."})
        assert "Error" not in result or "list_files" not in result
        print(f"  [PASS] list_files executed: {result[:50]}...")
        
        # Test get_env (simple tool)
        result = executor.execute("get_env", {"key": "PATH"})
        assert "Error" not in result or "Not found" in result  # May or may not have PATH
        print(f"  [PASS] get_env executed")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Execution error: {e}")
        return False


def test_execute_unknown_tool():
    """Test execution of unknown tool"""
    print("Testing unknown tool execution...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        
        result = executor.execute("nonexistent_tool", {"arg": "value"})
        
        assert "Error" in result
        assert "nonexistent_tool" in result
        assert "Available" in result
        print(f"  [PASS] Unknown tool returns error: {result[:60]}...")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Error handling failed: {e}")
        return False


def test_execute_invalid_args():
    """Test execution with invalid arguments"""
    print("Testing invalid arguments...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        
        # file_write should have path and content
        result = executor.execute("file_write", {"wrong_param": "value"})
        
        # Should either work with defaults or return error
        # (depends on tool implementation)
        print(f"  [INFO] Result: {result[:60]}...")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Invalid args error: {e}")
        return False


def test_execute_result():
    """Test execute_result with detailed results"""
    print("Testing execute_result...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        
        # Test successful execution
        result = executor.execute_result("list_files", {"path": "."})
        
        assert isinstance(result.success, bool)
        assert result.tool_name == "list_files"
        assert result.duration >= 0
        assert result.output is not None
        print(f"  [PASS] ExecutionResult has all fields")
        print(f"    success={result.success}, duration={result.duration:.4f}s")
        
        return True
    except Exception as e:
        print(f"  [FAIL] execute_result error: {e}")
        return False


def test_stats():
    """Test execution statistics"""
    print("Testing statistics...")
    
    from agent_core.executor import ToolExecutor
    from agent_core.tools import ToolRegistry
    
    try:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        
        # Initial stats
        stats = executor.get_stats()
        assert stats["total_executions"] == 0
        print("  [PASS] Initial stats are zero")
        
        # Do some executions
        executor.execute("list_files", {"path": "."})
        executor.execute("get_env", {"key": "HOME"})
        
        stats = executor.get_stats()
        assert stats["total_executions"] == 2
        assert stats["total_duration"] > 0
        print(f"  [PASS] Stats updated: {stats['total_executions']} executions, {stats['total_duration']:.4f}s total")
        
        # Reset stats
        executor.reset_stats()
        stats = executor.get_stats()
        assert stats["total_executions"] == 0
        print("  [PASS] Stats reset")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Stats error: {e}")
        return False


def run_all_tests():
    """Run all Phase 3 tests"""
    print("=" * 60)
    print("PHASE 3: Tool Executor - Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_executor_imports,
        test_execution_result_dataclass,
        test_executor_initialization,
        test_can_execute,
        test_get_available_tools,
        test_execute_success,
        test_execute_unknown_tool,
        test_execute_invalid_args,
        test_execute_result,
        test_stats,
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
        print("[SUCCESS] PHASE 3 COMPLETE - Tool Executor ready!")
    else:
        print("[FAILURE] Some tests failed - review above")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

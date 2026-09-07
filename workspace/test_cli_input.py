"""
Regression Tests for CLI Input Handling

Tests for single-line and multiline input buffering.

M0.2 Fix: Multiline input is now buffered and sent as ONE complete message
"""

import os
import sys
from unittest.mock import patch, MagicMock

# Add agent_core to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_single_line_input():
    """Test that single-line input works correctly"""
    from agent_core.cli import read_single_line
    
    with patch('builtins.input', return_value='Hello world'):
        result = read_single_line()
    
    assert result == "Hello world"
    print("[PASS] Single-line input works")


def test_single_line_with_spaces():
    """Test single-line input with leading/trailing spaces"""
    from agent_core.cli import read_single_line
    
    with patch('builtins.input', return_value='  Hello world  '):
        result = read_single_line()
    
    assert result == "  Hello world  "
    print("[PASS] Single-line with spaces works")


def test_single_line_return_immediately():
    """Test that single-line input returns immediately without buffering"""
    from agent_core.cli import read_input
    
    with patch('builtins.input', return_value='Hello world'):
        result = read_input()
    
    assert result == "Hello world"
    print("[PASS] Single-line returns immediately")


def test_multiline_input_two_lines():
    """Test multiline input with two lines"""
    from agent_core.cli import read_input
    
    inputs = ['First line', 'Second line', '---']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    expected = "First line\nSecond line"
    assert result == expected
    print("[PASS] Two-line input works")


def test_multiline_input_three_lines():
    """Test multiline input with three lines"""
    from agent_core.cli import read_input
    
    inputs = ['Line one', 'Line two', 'Line three', '---']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    expected = "Line one\nLine two\nLine three"
    assert result == expected
    print("[PASS] Three-line input works with newlines preserved")


def test_multiline_input_with_blank_lines():
    """Test multiline input with blank lines in the middle"""
    from agent_core.cli import read_input
    
    inputs = ['Line one', '', 'Line three', '---']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    expected = "Line one\n\nLine three"
    assert result == expected
    print("[PASS] Multiline with blank lines preserves them")


def test_pasted_multiline_with_newlines():
    """Test that pasted multiline text (containing newlines) is handled"""
    from agent_core.cli import read_input
    
    pasted_text = "Line 1\nLine 2\nLine 3"
    inputs = [pasted_text, '---']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    expected = "Line 1\nLine 2\nLine 3"
    assert result == expected
    print("[PASS] Pasted multiline text is handled correctly")


def test_multiline_ends_with_delimiter():
    """Test that --- delimiter ends multiline input"""
    from agent_core.cli import read_input
    
    inputs = ['Some text', 'More text', '---']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    expected = "Some text\nMore text"
    assert result == expected
    print("[PASS] --- delimiter ends multiline input")


def test_empty_input_returns_empty():
    """Test that empty input returns empty string"""
    from agent_core.cli import read_input
    
    inputs = ['']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    assert result == ""
    print("[PASS] Empty input returns empty string")


def test_code_block_multiline():
    """Test multiline input with code-like content"""
    from agent_core.cli import read_input
    
    code = 'def hello():\n    print("Hello")\n    return True'
    
    inputs = [code, '---']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    assert "def hello():" in result
    assert 'print("Hello")' in result
    assert result == code
    print("[PASS] Code block multiline input works")


def test_preserves_exact_whitespace():
    """Test that exact whitespace and indentation is preserved"""
    from agent_core.cli import read_input
    
    indented_text = "    indented\n        more indented\n    back"
    
    inputs = [indented_text, '---']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    assert result == indented_text
    print("[PASS] Exact whitespace is preserved")


def test_delimiter_only_lines():
    """Test that --- on its own line as first input starts multiline mode"""
    from agent_core.cli import read_input
    
    inputs = ['---', 'Some content', '---']
    
    with patch('builtins.input', side_effect=inputs):
        result = read_input()
    
    assert result == "Some content"
    print("[PASS] --- as first line starts multiline mode")


def run_cli_tests():
    """Run all CLI input tests"""
    print("=" * 60)
    print("CLI Input Handling - Regression Tests")
    print("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    test_functions = [
        test_single_line_input,
        test_single_line_with_spaces,
        test_single_line_return_immediately,
        test_multiline_input_two_lines,
        test_multiline_input_three_lines,
        test_multiline_input_with_blank_lines,
        test_pasted_multiline_with_newlines,
        test_multiline_ends_with_delimiter,
        test_empty_input_returns_empty,
        test_code_block_multiline,
        test_preserves_exact_whitespace,
        test_delimiter_only_lines,
    ]
    
    for test in test_functions:
        try:
            test()
            tests_passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            tests_failed += 1
    
    print("\n" + "=" * 60)
    print(f"CLI Tests Passed: {tests_passed}")
    print(f"CLI Tests Failed: {tests_failed}")
    print("=" * 60)
    
    return tests_failed == 0


if __name__ == "__main__":
    success = run_cli_tests()
    sys.exit(0 if success else 1)

"""Test script for Obsidian Agent"""
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_core.agent import create_agent

# Create agent
agent = create_agent("Obsidian", workspace=os.getcwd())
print("[OK] Agent created successfully!")
print(f"Name: {agent.config.name}")
print(f"Tools: {len(agent.get_tools())}")

# Test running a task
print("\n--- Testing Agent.run() ---")
result = agent.run("List the files in the current directory")
print(f"Result: {result}")

# Test memory
print("\n--- Testing Memory ---")
agent.remember("Python is the user's preferred language", importance=4)
recall_result = agent.recall("Python")
print(f"Recall 'Python': {recall_result}")

print("\n[OK] All tests passed!")

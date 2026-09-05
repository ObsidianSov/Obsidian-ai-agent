"""
CLI Interface - Run the agent from command line
"""

import os
import sys

def main():
    print("=" * 50)
    print("OBSIDIAN AI AGENT")
    print("=" * 50)
    
    # Get workspace
    workspace = os.environ.get('OBSIDIAN_WORKSPACE', os.getcwd())
    os.chdir(workspace)
    
    from agent_core.agent import create_agent
    
    agent = create_agent(name="Obsidian", workspace=workspace, verbose=True)
    
    print(f"\n[*] Workspace: {workspace}")
    print(f"[*] Tools available: {len(agent.get_tools())}")
    print("\nType 'exit' to quit, 'memory' to see memories, 'tools' to list tools")
    print("-" * 50)
    
    while True:
        try:
            task = input("\n> ")
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break
        
        if not task.strip():
            continue
        
        if task.lower() in ['exit', 'quit', 'bye']:
            print("Goodbye!")
            break
        
        if task.lower() == 'memory':
            print("\n[*] Recent Memories:")
            for m in agent.memory.working.items[-5:]:
                print(f"  [{m['role']}] {m['content'][:80]}...")
            print(f"\n[*] Persistent memories: {len(agent.memory.persistent.memories)}")
            continue
        
        if task.lower() == 'tools':
            print("\n[*] Available Tools:")
            for t in agent.get_tools():
                print(f"  - {t['name']}: {t['description']}")
            continue
        
        if task.lower() == 'inspect':
            state = agent.inspect()
            print(f"\n[*] Agent State:")
            for k, v in state.items():
                print(f"  {k}: {v}")
            continue
        
        # Run the agent
        result = agent.run(task)
        print(f"\n[>] Response: {result}")

if __name__ == "__main__":
    main()

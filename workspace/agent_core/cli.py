"""
CLI Interface - Run the agent from command line
"""

import os


MULTILINE_COMMAND = "paste"
MULTILINE_END = ":::"


def read_single_line():
    """Read a single line of input (no buffering/multi-line)"""
    return input("\n> ")


def read_input():
    """Read user input - single line or multiline if 'paste' command used"""
    return read_task()


def read_multiline_input():
    """Read one complete multiline task until the explicit terminator."""
    print("  [MULTILINE MODE]")
    print(f"  Paste your complete task below.")
    print(f"  Type {MULTILINE_END} on its own line when finished.")
    print()

    lines = []

    while True:
        try:
            line = input("  | ")
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if line.strip() == MULTILINE_END:
            break

        lines.append(line)

    return "\n".join(lines)


def read_task():
    """Read one complete user task from the CLI."""
    try:
        task = input("\n> ")
    except (KeyboardInterrupt, EOFError):
        raise

    # Empty input is ignored by the caller.
    if task.strip().lower() == MULTILINE_COMMAND:
        return read_multiline_input()

    return task


def main():
    print("=" * 50)
    print("OBSIDIAN AI AGENT")
    print("=" * 50)

    # Get workspace
    workspace = os.environ.get("OBSIDIAN_WORKSPACE", os.getcwd())
    os.chdir(workspace)

    from agent_core.agent import create_agent

    agent = create_agent(
        name="Obsidian",
        workspace=workspace,
        verbose=True
    )

    print(f"\n[*] Workspace: {workspace}")
    print(f"[*] Tools available: {len(agent.get_tools())}")
    print("\nType 'exit' to quit, 'memory' to see memories,")
    print("'tools' to list tools, or 'paste' for multiline input.")
    print("-" * 50)

    while True:
        try:
            task = read_task()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break

        if not task.strip():
            continue

        if task.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break

        if task.lower() == "memory":
            print("\n[*] Recent Memories:")
            for m in agent.memory.working.items[-5:]:
                print(f"  [{m['role']}] {m['content'][:80]}...")
            print(f"\n[*] Persistent memories: {len(agent.memory.persistent.memories)}")
            continue

        if task.lower() == "tools":
            print("\n[*] Available Tools:")
            for t in agent.get_tools():
                print(f"  - {t['name']}: {t['description']}")
            continue

        if task.lower() == "inspect":
            state = agent.inspect()
            print("\n[*] Agent State:")
            for k, v in state.items():
                print(f"  {k}: {v}")
            continue

        # Run the agent
        result = agent.run(task)
        print(f"\n[>] Response: {result}")


if __name__ == "__main__":
    main()

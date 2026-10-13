"""
Console input helpers for Obsidian AI  —  Milestone 7.3

THE PROBLEM (seen on the phone): pasting a multi-line message into a
program that calls input() hands the program ONE LINE PER input() CALL.
While the agent is busy, the rest of the paste sits in the terminal's
buffer. The next time the program asks something, that leftover text is
taken as the answer. Two bad things followed:

  1. The brief reached the model in fragments (it started working before
     it had read "inspect first, do not write files yet").
  2. Approval prompts ("Allow this command? yes/no") were answered by
     leftover brief text. Anything except yes/y is a "no", so they were
     denied by accident. A leftover line that said "yes" would have
     APPROVED a command the human never saw.

THE FIX:
  read_message()  - a pasted multi-line message arrives as ONE message,
                    sent only when you press Enter (so the last line of a
                    paste is never lost).
  ask_human()     - throws away anything still waiting in the terminal
                    before it asks, so only a fresh answer typed AFTER the
                    prompt appears can approve something.

Only does anything on a real terminal. When input comes from a pipe or a
file (tests, scripts) it behaves exactly like input().
"""

import select
import sys

try:
    import termios
except ImportError:      # not a Unix-like system
    termios = None


def _is_terminal() -> bool:
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def input_pending(wait: float = 0.0) -> bool:
    """True if characters are already waiting to be read from the terminal."""
    try:
        ready, _, _ = select.select([sys.stdin], [], [], wait)
        return bool(ready)
    except (OSError, ValueError, TypeError):
        return False


def flush_pending_input() -> None:
    """Discard anything typed or pasted that the program has not read yet."""
    if termios is None or not _is_terminal():
        return
    try:
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (OSError, ValueError, termios.error):
        pass


def read_message(prompt: str = "You: ", settle: float = 0.25) -> str:
    """
    Read one message. If several lines arrive together (a paste), join
    them into a single message instead of returning them one by one.
    """
    first = input(prompt)
    if not _is_terminal():
        return first
    lines = [first]
    while input_pending(settle):
        try:
            lines.append(input())
        except EOFError:
            break
    if len(lines) > 1:
        # A paste usually leaves its LAST line unfinished (no line break) until
        # you press Enter. Wait for that Enter so the last line is not lost,
        # and so nothing starts running before the whole message is in.
        print(f"[Pasted {len(lines)} lines. Press Enter to send, or keep typing.]")
        try:
            extra = input()
        except EOFError:
            extra = ""
        if extra.strip():
            lines.append(extra)
    return "\n".join(lines).rstrip()


def ask_human(prompt: str) -> str:
    """Ask a question that must be answered by a fresh, deliberate reply."""
    flush_pending_input()
    return input(prompt)

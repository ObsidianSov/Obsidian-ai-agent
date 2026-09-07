"""
Emergency Kill Switch for Obsidian AI (ai.py)

Deliberately as simple as possible: presence of a file called
KILLSWITCH next to ai.py (outside workspace/) means "stop everything
immediately." No syntax to remember under pressure — creating an
empty file is enough, from a terminal or any file manager.

Lives outside workspace/ so the agent's own write_file/create_directory
tools (scoped to workspace/ only) can never touch it. The only path
to removing it via the agent would be run_command reaching outside
the workspace, which the Action Gate's path-escape check already
forces through an APPROVAL prompt — one safety layer reinforcing
another.
"""

from pathlib import Path


def killswitch_path(base_dir: Path) -> Path:
    return Path(base_dir) / "KILLSWITCH"


def is_killed(base_dir: Path) -> bool:
    """True if the kill switch is currently active."""
    return killswitch_path(base_dir).exists()


def activate(base_dir: Path, reason: str = ""):
    """Create the kill switch file. Idempotent — safe to call repeatedly."""
    path = killswitch_path(base_dir)
    path.write_text(reason or "Kill switch activated.\n", encoding="utf-8")
    return path


def deactivate(base_dir: Path):
    """Remove the kill switch file, if present. Safe to call when already off."""
    path = killswitch_path(base_dir)
    if path.exists():
        path.unlink()
    return path

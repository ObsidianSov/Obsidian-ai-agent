"""
Memory System for Obsidian AI (ai.py)

Ported from agent_core/memory.py — the one module in the original
agent_core build that was verified as genuinely implemented and
tested. Adapted to plug directly into ai.py's tool-calling loop.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import uuid


@dataclass
class Memory:
    """A single persistent memory item."""
    id: str
    content: str
    type: str  # 'fact', 'preference', 'note'
    timestamp: str
    importance: int = 3  # 1-5 scale
    tags: List[str] = field(default_factory=list)
    access_count: int = 0


class PersistentMemory:
    """Long-term memory stored on disk as JSON."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.storage_dir / "memories.json"
        self.memories: List[Memory] = []
        self._load()

    def _load(self):
        if self.memory_file.exists():
            try:
                data = json.loads(self.memory_file.read_text(encoding="utf-8"))
                self.memories = [Memory(**m) for m in data]
            except Exception:
                # Corrupt or unreadable file — start fresh rather than crash
                self.memories = []

    def _save(self):
        self.memory_file.write_text(
            json.dumps([m.__dict__ for m in self.memories], indent=2),
            encoding="utf-8"
        )

    def add(self, content: str, mem_type: str = "fact",
            importance: int = 3, tags: Optional[List[str]] = None) -> str:
        memory = Memory(
            id=str(uuid.uuid4())[:8],
            content=content,
            type=mem_type,
            timestamp=datetime.now().isoformat(),
            importance=importance,
            tags=tags or []
        )
        self.memories.append(memory)
        self._save()
        return memory.id

    def recall(self, query: str, limit: int = 5) -> List[Memory]:
        """Simple keyword-based recall, ranked by importance and access."""
        query_lower = query.lower()
        scored = []
        for m in self.memories:
            if query_lower in m.content.lower():
                m.access_count += 1
                score = m.importance * (1 + 0.1 * m.access_count)
                scored.append((score, m))
        scored.sort(reverse=True, key=lambda x: x[0])
        if scored:
            self._save()  # persist updated access_count
        return [m for _, m in scored[:limit]]

    def get_top(self, limit: int = 10) -> List[Memory]:
        """Highest-importance memories, for session-start context."""
        return sorted(self.memories, key=lambda m: m.importance, reverse=True)[:limit]


class MemorySystem:
    """Simple entry point wrapping persistent memory for ai.py."""

    def __init__(self, workspace: Path):
        self.persistent = PersistentMemory(Path(workspace) / "memory")

    def remember(self, content: str, importance: int = 3,
                 tags: Optional[List[str]] = None) -> str:
        return self.persistent.add(content, importance=importance, tags=tags)

    def recall(self, query: str) -> str:
        results = self.persistent.recall(query)
        if not results:
            return "No relevant memories found."
        return "\n".join(f"- [{m.type}] {m.content}" for m in results)

    def startup_context(self, limit: int = 8) -> str:
        """Text summary of top memories, injected at session start."""
        top = self.persistent.get_top(limit)
        if not top:
            return ""
        return "\n".join(f"- {m.content}" for m in top)

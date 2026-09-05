"""
Memory System - Hierarchical memory with working + persistent layers
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import uuid

@dataclass
class Memory:
    """A single memory item"""
    id: str
    content: str
    type: str  # 'fact', 'conversation', 'knowledge', 'preference'
    timestamp: str
    importance: int = 1  # 1-5 scale
    tags: List[str] = field(default_factory=list)
    access_count: int = 0

class WorkingMemory:
    """Short-term memory for current session"""
    
    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self.items: List[Dict] = []
    
    def add(self, role: str, content: str, metadata: Dict = None):
        self.items.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        })
        # Keep only last N items
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items:]
    
    def get_context(self, max_tokens: int = 4000) -> List[Dict]:
        """Get recent context, truncated to token limit"""
        return self.items[-self.max_items:]
    
    def clear(self):
        self.items = []

class PersistentMemory:
    """Long-term memory stored on disk"""
    
    def __init__(self, storage_path: str = "memory/"):
        self.storage_path = storage_path
        self.memories: List[Memory] = []
        self._ensure_storage()
        self._load()
    
    def _ensure_storage(self):
        os.makedirs(self.storage_path, exist_ok=True)
    
    def _load(self):
        memory_file = os.path.join(self.storage_path, "memories.json")
        if os.path.exists(memory_file):
            try:
                with open(memory_file, 'r') as f:
                    data = json.load(f)
                    self.memories = [Memory(**m) for m in data]
            except Exception:
                self.memories = []
    
    def _save(self):
        memory_file = os.path.join(self.storage_path, "memories.json")
        with open(memory_file, 'w') as f:
            json.dump([m.__dict__ for m in self.memories], f, indent=2)
    
    def add(self, content: str, mem_type: str = "fact", importance: int = 3, tags: List[str] = None):
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
        """Simple keyword-based recall"""
        query_lower = query.lower()
        scored = []
        for m in self.memories:
            if query_lower in m.content.lower():
                m.access_count += 1
                score = m.importance * (1 + 0.1 * m.access_count)
                scored.append((score, m))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [m for _, m in scored[:limit]]
    
    def search(self, tags: List[str] = None, mem_type: str = None) -> List[Memory]:
        results = self.memories
        if tags:
            results = [m for m in results if any(t in m.tags for t in tags)]
        if mem_type:
            results = [m for m in results if m.type == mem_type]
        return sorted(results, key=lambda m: m.importance, reverse=True)
    
    def forget(self, memory_id: str) -> bool:
        self.memories = [m for m in self.memories if m.id != memory_id]
        self._save()
        return True
    
    def get_all(self) -> List[Memory]:
        return sorted(self.memories, key=lambda m: m.timestamp, reverse=True)

class KnowledgeBase:
    """Structured knowledge storage"""
    
    def __init__(self, kb_path: str = "knowledge/"):
        self.kb_path = kb_path
        self._ensure_kb()
    
    def _ensure_kb(self):
        os.makedirs(self.kb_path, exist_ok=True)
    
    def store(self, key: str, data: Any):
        filepath = os.path.join(self.kb_path, f"{key}.json")
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def retrieve(self, key: str) -> Optional[Any]:
        filepath = os.path.join(self.kb_path, f"{key}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return None
    
    def list_keys(self) -> List[str]:
        return [f.replace('.json', '') for f in os.listdir(self.kb_path) if f.endswith('.json')]

class MemorySystem:
    """Complete memory system with all layers"""
    
    def __init__(self, workspace: str = "."):
        self.working = WorkingMemory()
        self.persistent = PersistentMemory(os.path.join(workspace, "memory"))
        self.knowledge = KnowledgeBase(os.path.join(workspace, "knowledge"))
    
    def remember(self, content: str, importance: int = 3):
        """Store important information"""
        return self.persistent.add(content, importance=importance)
    
    def recall(self, query: str) -> str:
        """Recall relevant memories"""
        memories = self.persistent.recall(query)
        if not memories:
            return "No relevant memories found."
        return "\n".join([f"[{m.type}] {m.content}" for m in memories])
    
    def get_system_context(self) -> Dict:
        """Get memory context for system prompt"""
        recent = self.working.get_context()
        important = self.persistent.search(mem_type="preference")
        return {
            "recent_conversation": recent[-5:] if recent else [],
            "user_preferences": [m.content for m in important[:3]],
            "knowledge_base_keys": self.knowledge.list_keys()
        }

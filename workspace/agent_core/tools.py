"""
Tool System - MCP-style extensible tool registry
"""

from typing import Callable, Any, Dict, List
from dataclasses import dataclass, field
import json
import os
import subprocess

@dataclass
class Tool:
    name: str
    description: str
    func: Callable
    input_schema: Dict = field(default_factory=dict)
    
    def __call__(self, **kwargs) -> Any:
        return self.func(**kwargs)

class ToolRegistry:
    """Central registry for all available tools"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register built-in tools"""
        self.register(FileReadTool())
        self.register(FileWriteTool())
        self.register(CommandTool())
        self.register(WebSearchTool())
        self.register(ListFilesTool())
        self.register(CreateDirectoryTool())
        self.register(ReadFileTool())
        self.register(GetEnvTool())
    
    def register(self, tool: Tool):
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found")
        return self._tools[name]
    
    def list_tools(self) -> List[Dict]:
        return [
            {"name": t.name, "description": t.description, "params": t.input_schema}
            for t in self._tools.values()
        ]
    
    def execute(self, name: str, **kwargs) -> Any:
        tool = self.get(name)
        return tool(**kwargs)

# === Built-in Tools ===

class FileReadTool(Tool):
    def __init__(self):
        super().__init__(
            name="file_read",
            description="Read content from a file",
            func=self._read,
            input_schema={"path": {"type": "string", "description": "File path"}}
        )
    
    def _read(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

class FileWriteTool(Tool):
    def __init__(self):
        super().__init__(
            name="file_write",
            description="Write content to a file (creates or overwrites)",
            func=self._write,
            input_schema={
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "Content to write"}
            }
        )
    
    def _write(self, path: str, content: str) -> str:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

class CommandTool(Tool):
    def __init__(self):
        super().__init__(
            name="command",
            description="Execute a terminal command",
            func=self._run,
            input_schema={"command": {"type": "string", "description": "Command to execute"}}
        )
    
    def _run(self, command: str) -> str:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )
            output = f"Exit: {result.returncode}\n"
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            return output
        except Exception as e:
            return f"Error executing command: {str(e)}"

class WebSearchTool(Tool):
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for information",
            func=self._search,
            input_schema={"query": {"type": "string", "description": "Search query"}}
        )
    
    def _search(self, query: str) -> str:
        # Placeholder - would integrate with search API
        return f"Web search for: {query} (not implemented - would use web API)"

class ListFilesTool(Tool):
    def __init__(self):
        super().__init__(
            name="list_files",
            description="List files in a directory",
            func=self._list,
            input_schema={"path": {"type": "string", "description": "Directory path"}}
        )
    
    def _list(self, path: str = ".") -> str:
        try:
            items = os.listdir(path)
            return "\n".join(items) if items else "Empty directory"
        except Exception as e:
            return f"Error: {str(e)}"

class CreateDirectoryTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_directory",
            description="Create a new directory",
            func=self._create,
            input_schema={"path": {"type": "string", "description": "Directory path"}}
        )
    
    def _create(self, path: str) -> str:
        try:
            os.makedirs(path, exist_ok=True)
            return f"Created directory: {path}"
        except Exception as e:
            return f"Error: {str(e)}"

class ReadFileTool(Tool):
    """Workspace-relative file read"""
    def __init__(self):
        super().__init__(
            name="read_workspace_file",
            description="Read a file from the workspace",
            func=self._read,
            input_schema={"path": {"type": "string", "description": "Workspace-relative file path"}}
        )
    
    def _read(self, path: str) -> str:
        workspace = os.environ.get('OBSIDIAN_WORKSPACE', os.getcwd())
        full_path = os.path.join(workspace, path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

class GetEnvTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_env",
            description="Get environment variable",
            func=self._get,
            input_schema={"key": {"type": "string", "description": "Environment variable name"}}
        )
    
    def _get(self, key: str) -> str:
        return os.environ.get(key, "Not found")

# Global registry instance
tools = ToolRegistry()

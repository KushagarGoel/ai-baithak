"""Tool system for agents - provides read, write, web search, and other capabilities."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional
import aiohttp
from ddgs import DDGS


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None


class BaseTool(ABC):
    """Base class for all tools."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def get_schema(self) -> dict:
        """Get the tool schema for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema(),
            },
        }

    @abstractmethod
    def get_parameters_schema(self) -> dict:
        """Get the JSON schema for tool parameters."""
        pass


class ReadFileTool(BaseTool):
    """Tool to read file contents."""

    def __init__(self, base_path: str = "."):
        super().__init__(
            name="read_file",
            description="Read the contents of a file. Returns the file content or an error if file doesn't exist."
        )
        self.base_path = os.path.abspath(base_path)

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to base path or absolute)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read (optional)",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (optional, 1-indexed)",
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str, limit: Optional[int] = None, offset: Optional[int] = None) -> ToolResult:
        try:
            # Resolve path relative to base_path
            if not os.path.isabs(file_path):
                full_path = os.path.join(self.base_path, file_path)
            else:
                full_path = file_path

            full_path = os.path.abspath(full_path)

            # Security: ensure we don't escape base_path
            if not full_path.startswith(self.base_path):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Access denied: path '{file_path}' is outside allowed directory"
                )

            if not os.path.exists(full_path):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"File not found: {file_path}"
                )

            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Handle offset (convert to 0-indexed)
            if offset:
                start = max(0, offset - 1)
            else:
                start = 0

            # Handle limit
            if limit:
                end = start + limit
            else:
                end = len(lines)

            selected_lines = lines[start:end]

            return ToolResult(
                success=True,
                data={
                    "content": ''.join(selected_lines),
                    "total_lines": len(lines),
                    "lines_read": len(selected_lines),
                    "start_line": start + 1,
                    "end_line": min(end, len(lines)),
                    "file_path": file_path,
                }
            )

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class WriteFileTool(BaseTool):
    """Tool to write file contents."""

    def __init__(self, base_path: str = "."):
        super().__init__(
            name="write_file",
            description="Write content to a file. Creates directories if needed. Returns success status."
        )
        self.base_path = os.path.abspath(base_path)

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write (relative to base path or absolute)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
                "append": {
                    "type": "boolean",
                    "description": "If true, append to file instead of overwriting (default: false)",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, file_path: str, content: str, append: bool = False) -> ToolResult:
        try:
            # Resolve path relative to base_path
            if not os.path.isabs(file_path):
                full_path = os.path.join(self.base_path, file_path)
            else:
                full_path = file_path

            full_path = os.path.abspath(full_path)

            # Security: ensure we don't escape base_path
            if not full_path.startswith(self.base_path):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Access denied: path '{file_path}' is outside allowed directory"
                )

            # Create directory if it doesn't exist
            directory = os.path.dirname(full_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            mode = 'a' if append else 'w'
            with open(full_path, mode, encoding='utf-8') as f:
                f.write(content)

            return ToolResult(
                success=True,
                data={
                    "file_path": file_path,
                    "bytes_written": len(content.encode('utf-8')),
                    "mode": "append" if append else "write",
                }
            )

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class ListDirectoryTool(BaseTool):
    """Tool to list directory contents."""

    def __init__(self, base_path: str = "."):
        super().__init__(
            name="list_directory",
            description="List files and directories at the given path. Returns a list of entries with type and name."
        )
        self.base_path = os.path.abspath(base_path)

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Path to directory to list (relative to base path or absolute). Default: current directory",
                },
            },
        }

    async def execute(self, directory_path: str = ".") -> ToolResult:
        try:
            # Resolve path relative to base_path
            if not os.path.isabs(directory_path):
                full_path = os.path.join(self.base_path, directory_path)
            else:
                full_path = directory_path

            full_path = os.path.abspath(full_path)

            # Security: ensure we don't escape base_path
            if not full_path.startswith(self.base_path):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Access denied: path '{directory_path}' is outside allowed directory"
                )

            if not os.path.exists(full_path):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Directory not found: {directory_path}"
                )

            if not os.path.isdir(full_path):
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Path is not a directory: {directory_path}"
                )

            entries = []
            for entry in os.listdir(full_path):
                entry_path = os.path.join(full_path, entry)
                entries.append({
                    "name": entry,
                    "type": "directory" if os.path.isdir(entry_path) else "file",
                    "size": os.path.getsize(entry_path) if os.path.isfile(entry_path) else None,
                })

            return ToolResult(
                success=True,
                data={
                    "directory": directory_path,
                    "entries": entries,
                    "total_count": len(entries),
                }
            )

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class WebSearchTool(BaseTool):
    """Tool to search the web using DuckDuckGo."""

    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web using DuckDuckGo. Returns search results with title, URL, and snippet."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5, max: 10)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            max_results = min(max_results, 10)

            results = []
            with DDGS() as ddgs:
                for result in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("href", ""),
                        "snippet": result.get("body", ""),
                    })

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "result_count": len(results),
                }
            )

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class WebFetchTool(BaseTool):
    """Tool to fetch web page content."""

    def __init__(self, timeout: int = 30):
        super().__init__(
            name="web_fetch",
            description="Fetch the content of a web page. Returns the page content as text."
        )
        self.timeout = timeout

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                },
            },
            "required": ["url"],
        }

    async def execute(self, url: str) -> ToolResult:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=self.timeout) as response:
                    if response.status != 200:
                        return ToolResult(
                            success=False,
                            data=None,
                            error=f"HTTP {response.status}: {response.reason}"
                        )

                    content = await response.text()

                    return ToolResult(
                        success=True,
                        data={
                            "url": url,
                            "status": response.status,
                            "content_length": len(content),
                            "content": content[:10000],  # Limit content size
                        }
                    )

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class ExecutePythonTool(BaseTool):
    """Tool to execute Python code."""

    def __init__(self):
        super().__init__(
            name="execute_python",
            description="Execute Python code and return the result. Use print() to output results."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
            },
            "required": ["code"],
        }

    async def execute(self, code: str) -> ToolResult:
        try:
            # Capture stdout
            import io
            import sys

            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()

            # Execute code in isolated namespace
            namespace = {}
            exec(code, namespace)

            # Get output
            sys.stdout = old_stdout
            output = buffer.getvalue()

            return ToolResult(
                success=True,
                data={
                    "output": output,
                    "executed_code": code[:500] + "..." if len(code) > 500 else code,
                }
            )

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self, base_path: str = "."):
        self.tools: dict[str, BaseTool] = {}
        self.base_path = base_path
        self._register_default_tools()

    def _register_default_tools(self):
        """Register default tools."""
        self.register(ReadFileTool(self.base_path))
        self.register(WriteFileTool(self.base_path))
        self.register(ListDirectoryTool(self.base_path))
        self.register(WebSearchTool())
        self.register(WebFetchTool())
        self.register(ExecutePythonTool())

    def register(self, tool: BaseTool):
        """Register a tool."""
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> list[str]:
        """List all available tool names."""
        return list(self.tools.keys())

    def get_schemas(self) -> list[dict]:
        """Get schemas for all tools."""
        return [tool.get_schema() for tool in self.tools.values()]

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool not found: {tool_name}"
            )
        return await tool.execute(**kwargs)

    def get_tools_description(self) -> str:
        """Get a formatted description of all tools."""
        descriptions = []
        for name, tool in self.tools.items():
            descriptions.append(f"- {name}: {tool.description}")
        return "\n".join(descriptions)

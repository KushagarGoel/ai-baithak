"""MCP client implementation for stdio, SSE, and WebSocket transports."""

import asyncio
import json
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Optional, Callable
from dataclasses import dataclass

import aiohttp
import aiohttp.web


@dataclass
class MCPConnectionState:
    """State of an MCP connection."""
    connected: bool = False
    error: Optional[str] = None
    tools: list[dict] = None

    def __post_init__(self):
        if self.tools is None:
            self.tools = []


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.state = MCPConnectionState()

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the MCP server."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close the connection."""
        pass

    @abstractmethod
    async def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call a method on the MCP server."""
        pass

    @abstractmethod
    async def list_tools(self) -> list[dict]:
        """List available tools from the MCP server."""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server."""
        pass


class StdioTransport(MCPTransport):
    """MCP transport using stdio (subprocess)."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.command = config.get("command", "")
        self.args = config.get("args", [])
        self.env = config.get("env", {})
        self.process: Optional[asyncio.subprocess.Process] = None
        self._message_id = 0
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Start the subprocess and establish communication."""
        try:
            # Merge environment variables
            env = {**dict(os.environ), **self.env}

            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            # Start reader task
            self._reader_task = asyncio.create_task(self._read_messages())

            # Initialize connection
            init_response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent-council", "version": "0.1.0"}
            })

            if init_response:
                self.state.connected = True
                # Load tools
                self.state.tools = await self.list_tools()
                return True
            else:
                self.state.error = "Failed to initialize MCP connection"
                return False

        except Exception as e:
            self.state.error = str(e)
            return False

    async def disconnect(self):
        """Terminate the subprocess."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

        self.state.connected = False

    async def _send_request(self, method: str, params: dict[str, Any]) -> Optional[dict]:
        """Send a JSON-RPC request."""
        if not self.process or self.process.stdin.is_closing():
            return None

        self._message_id += 1
        message_id = str(self._message_id)

        request = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params
        }

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[message_id] = future

        try:
            # Send message
            message = json.dumps(request) + "\n"
            self.process.stdin.write(message.encode())
            await self.process.stdin.drain()

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=30.0)
            return response

        except asyncio.TimeoutError:
            del self._pending_responses[message_id]
            return None
        except Exception as e:
            del self._pending_responses[message_id]
            return None

    async def _read_messages(self):
        """Read messages from stdout."""
        try:
            while self.process and self.process.stdout:
                try:
                    line = await self.process.stdout.readline()
                    if not line:
                        break

                    message = json.loads(line.decode().strip())

                    # Handle responses
                    if "id" in message:
                        message_id = str(message["id"])
                        if message_id in self._pending_responses:
                            future = self._pending_responses.pop(message_id)
                            if not future.done():
                                future.set_result(message.get("result"))

                    # Handle notifications (errors)
                    if "error" in message:
                        error_msg = message["error"].get("message", "Unknown error")
                        self.state.error = error_msg

                except json.JSONDecodeError:
                    continue
                except Exception:
                    break

        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call a method on the MCP server."""
        result = await self._send_request(method, params)
        return result or {}

    async def list_tools(self) -> list[dict]:
        """List available tools."""
        result = await self.call("tools/list", {})
        tools = result.get("tools", [])
        self.state.tools = tools
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool."""
        result = await self.call("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        return result


class SSETransport(MCPTransport):
    """MCP transport using Server-Sent Events (HTTP)."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.url = config.get("url", "")
        self.headers = config.get("headers", {})
        self.session: Optional[aiohttp.ClientSession] = None
        self._message_id = 0

    async def connect(self) -> bool:
        """Establish HTTP connection."""
        try:
            self.session = aiohttp.ClientSession(headers=self.headers)

            # Initialize connection
            init_response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent-council", "version": "0.1.0"}
            })

            if init_response:
                self.state.connected = True
                self.state.tools = await self.list_tools()
                return True
            else:
                self.state.error = "Failed to initialize SSE connection"
                return False

        except Exception as e:
            self.state.error = str(e)
            return False

    async def disconnect(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
        self.state.connected = False

    async def _send_request(self, method: str, params: dict[str, Any]) -> Optional[dict]:
        """Send HTTP POST request."""
        if not self.session:
            return None

        self._message_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": self._message_id,
            "method": method,
            "params": params
        }

        try:
            async with self.session.post(
                f"{self.url}/rpc",
                json=request,
                timeout=aiohttp.ClientTimeout(total=30.0)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("result")
                else:
                    self.state.error = f"HTTP {response.status}"
                    return None

        except Exception as e:
            self.state.error = str(e)
            return None

    async def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call a method."""
        result = await self._send_request(method, params)
        return result or {}

    async def list_tools(self) -> list[dict]:
        """List available tools."""
        result = await self.call("tools/list", {})
        tools = result.get("tools", [])
        self.state.tools = tools
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool."""
        result = await self.call("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        return result


class WebSocketTransport(MCPTransport):
    """MCP transport using WebSocket."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.url = config.get("url", "")
        self.protocols = config.get("protocols", [])
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._message_id = 0
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(
                self.url,
                protocols=self.protocols
            )

            # Start reader task
            self._reader_task = asyncio.create_task(self._read_messages())

            # Initialize
            init_response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent-council", "version": "0.1.0"}
            })

            if init_response:
                self.state.connected = True
                self.state.tools = await self.list_tools()
                return True
            else:
                self.state.error = "Failed to initialize WebSocket connection"
                return False

        except Exception as e:
            self.state.error = str(e)
            return False

    async def disconnect(self):
        """Close WebSocket connection."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            await self.ws.close()

        if self.session:
            await self.session.close()

        self.state.connected = False

    async def _send_request(self, method: str, params: dict[str, Any]) -> Optional[dict]:
        """Send WebSocket message."""
        if not self.ws or self.ws.closed:
            return None

        self._message_id += 1
        message_id = str(self._message_id)

        request = {
            "jsonrpc": "2.0",
            "id": self._message_id,
            "method": method,
            "params": params
        }

        future = asyncio.get_event_loop().create_future()
        self._pending_responses[message_id] = future

        try:
            await self.ws.send_json(request)
            response = await asyncio.wait_for(future, timeout=30.0)
            return response

        except asyncio.TimeoutError:
            del self._pending_responses[message_id]
            return None
        except Exception:
            del self._pending_responses[message_id]
            return None

    async def _read_messages(self):
        """Read messages from WebSocket."""
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        message = json.loads(msg.data)

                        if "id" in message:
                            message_id = str(message["id"])
                            if message_id in self._pending_responses:
                                future = self._pending_responses.pop(message_id)
                                if not future.done():
                                    future.set_result(message.get("result"))

                        if "error" in message:
                            self.state.error = message["error"].get("message", "Unknown error")

                    except json.JSONDecodeError:
                        pass

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.state.error = f"WebSocket error: {self.ws.exception()}"
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.state.error = str(e)

    async def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call a method."""
        result = await self._send_request(method, params)
        return result or {}

    async def list_tools(self) -> list[dict]:
        """List available tools."""
        result = await self.call("tools/list", {})
        tools = result.get("tools", [])
        self.state.tools = tools
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool."""
        result = await self.call("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        return result


class MCPClient:
    """Client for connecting to MCP servers."""

    TRANSPORTS = {
        "stdio": StdioTransport,
        "sse": SSETransport,
        "websocket": WebSocketTransport,
    }

    def __init__(self, name: str, transport_type: str, config: dict[str, Any]):
        self.name = name
        self.transport_type = transport_type
        self.config = config
        self.transport: Optional[MCPTransport] = None

    async def connect(self) -> bool:
        """Connect to the MCP server."""
        transport_class = self.TRANSPORTS.get(self.transport_type)
        if not transport_class:
            raise ValueError(f"Unknown transport type: {self.transport_type}")

        self.transport = transport_class(self.config)
        return await self.transport.connect()

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.transport:
            await self.transport.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.transport is not None and self.transport.state.connected

    @property
    def error(self) -> Optional[str]:
        """Get last error."""
        return self.transport.state.error if self.transport else None

    async def list_tools(self) -> list[dict]:
        """List available tools."""
        if not self.transport:
            return []
        return await self.transport.list_tools()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool."""
        if not self.transport:
            return {"error": "Not connected"}
        return await self.transport.call_tool(tool_name, arguments)


# Import os for stdio transport
import os

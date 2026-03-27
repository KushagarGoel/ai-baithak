"""MCP Registry for managing multiple MCP servers."""

import uuid
from typing import Any, Optional
from dataclasses import dataclass, field

from app.mcp.client import MCPClient
from app.core.database import db


@dataclass
class MCPTool:
    """A tool from an MCP server."""
    name: str
    description: str
    parameters: dict[str, Any]
    mcp_server_id: str
    mcp_server_name: str


@dataclass
class MCPInfo:
    """Information about a registered MCP."""
    id: str
    name: str
    description: Optional[str]
    transport: str
    is_active: bool
    status: str = "unknown"
    tool_count: int = 0
    last_error: Optional[str] = None


@dataclass
class ToolCall:
    """A call to a tool."""
    mcp_server_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None


class MCPRegistry:
    """Central registry for all MCP servers.

    Supports stdio, SSE, and WebSocket transports.
    Integrates with database for persistence.
    """

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._tools: dict[str, MCPTool] = {}

    async def register_mcp(self, name: str, transport: str, config: dict[str, Any],
                          description: str = None, mcp_id: str = None) -> MCPInfo:
        """Register a new MCP server.

        Args:
            name: Unique name for the MCP server
            transport: Transport type (stdio, sse, websocket)
            config: Configuration dict (command/args for stdio, url for sse/ws)
            description: Optional description
            mcp_id: Optional ID (generated if not provided)

        Returns:
            MCPInfo for the registered server
        """
        if mcp_id is None:
            mcp_id = str(uuid.uuid4())

        # Create client but don't connect yet
        client = MCPClient(name, transport, config)
        self._clients[mcp_id] = client

        # Save to database
        db.create_mcp_server(
            mcp_id=mcp_id,
            name=name,
            transport=transport,
            config=config,
            description=description
        )

        return MCPInfo(
            id=mcp_id,
            name=name,
            description=description,
            transport=transport,
            is_active=True
        )

    async def connect_mcp(self, mcp_id: str) -> bool:
        """Connect to an MCP server and load its tools.

        Args:
            mcp_id: The MCP server ID

        Returns:
            True if connection successful
        """
        client = self._clients.get(mcp_id)
        if not client:
            # Try to load from database
            mcp_data = db.get_mcp_server(mcp_id)
            if not mcp_data:
                return False

            client = MCPClient(
                mcp_data['name'],
                mcp_data['transport'],
                mcp_data['config']
            )
            self._clients[mcp_id] = client

        success = await client.connect()

        if success:
            # Load tools from this MCP
            tools = await client.list_tools()
            for tool in tools:
                tool_name = tool.get('name')
                if tool_name:
                    self._tools[f"{mcp_id}:{tool_name}"] = MCPTool(
                        name=tool_name,
                        description=tool.get('description', ''),
                        parameters=tool.get('parameters', {}),
                        mcp_server_id=mcp_id,
                        mcp_server_name=client.name
                    )

        return success

    async def disconnect_mcp(self, mcp_id: str):
        """Disconnect from an MCP server."""
        client = self._clients.get(mcp_id)
        if client:
            await client.disconnect()

        # Remove tools from this MCP
        tools_to_remove = [
            key for key, tool in self._tools.items()
            if tool.mcp_server_id == mcp_id
        ]
        for key in tools_to_remove:
            del self._tools[key]

    async def unregister_mcp(self, mcp_id: str) -> bool:
        """Unregister and remove an MCP server."""
        await self.disconnect_mcp(mcp_id)

        if mcp_id in self._clients:
            del self._clients[mcp_id]

        # Remove from database
        return db.delete_mcp_server(mcp_id)

    def list_mcps(self, active_only: bool = True) -> list[MCPInfo]:
        """List all registered MCP servers."""
        mcps = db.list_mcp_servers(active_only=active_only)

        result = []
        for mcp in mcps:
            mcp_id = mcp['id']
            client = self._clients.get(mcp_id)

            info = MCPInfo(
                id=mcp_id,
                name=mcp['name'],
                description=mcp.get('description'),
                transport=mcp['transport'],
                is_active=mcp.get('is_active', True),
                status="active" if client and client.is_connected else "offline",
                tool_count=len([
                    t for t in self._tools.values()
                    if t.mcp_server_id == mcp_id
                ]),
                last_error=client.error if client else None
            )
            result.append(info)

        return result

    def get_mcp(self, mcp_id: str) -> Optional[MCPInfo]:
        """Get information about a specific MCP."""
        mcp = db.get_mcp_server(mcp_id)
        if not mcp:
            return None

        client = self._clients.get(mcp_id)
        return MCPInfo(
            id=mcp_id,
            name=mcp['name'],
            description=mcp.get('description'),
            transport=mcp['transport'],
            is_active=mcp.get('is_active', True),
            status="active" if client and client.is_connected else "offline",
            tool_count=len([
                t for t in self._tools.values()
                if t.mcp_server_id == mcp_id
            ]),
            last_error=client.error if client else None
        )

    def get_mcp_tools(self, mcp_id: str) -> list[MCPTool]:
        """Get all tools from a specific MCP server."""
        return [
            tool for tool in self._tools.values()
            if tool.mcp_server_id == mcp_id
        ]

    def get_all_tools(self) -> list[MCPTool]:
        """Get all tools from all MCP servers."""
        return list(self._tools.values())

    def get_all_tools_for_agent(self, agent_id: str) -> list[MCPTool]:
        """Get all tools an agent has access to."""
        # Get MCPs the agent has access to
        agent_mcps = db.get_agent_mcps(agent_id)
        allowed_mcp_ids = {m['id'] for m in agent_mcps}

        # Get allowed tools for each MCP
        allowed_tools = {}
        for mcp in agent_mcps:
            allowed_tools[mcp['id']] = mcp.get('allowed_tools')  # None = all allowed

        # Filter tools
        result = []
        for tool in self._tools.values():
            if tool.mcp_server_id not in allowed_mcp_ids:
                continue

            # Check if tool is allowed
            tool_allowlist = allowed_tools.get(tool.mcp_server_id)
            if tool_allowlist is None or tool.name in tool_allowlist:
                result.append(tool)

        return result

    async def execute_tool(self, mcp_id: str, tool_name: str,
                          params: dict[str, Any]) -> ToolResult:
        """Execute a tool on a specific MCP server."""
        client = self._clients.get(mcp_id)
        if not client:
            return ToolResult(
                success=False,
                data=None,
                error=f"MCP server {mcp_id} not connected"
            )

        if not client.is_connected:
            # Try to reconnect
            success = await self.connect_mcp(mcp_id)
            if not success:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"MCP server {mcp_id} is not connected"
                )

        try:
            result = await client.call_tool(tool_name, params)

            # Check for errors in result
            if "error" in result:
                return ToolResult(
                    success=False,
                    data=None,
                    error=result["error"]
                )

            return ToolResult(
                success=True,
                data=result.get("content", result)
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e)
            )

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call."""
        return await self.execute_tool(
            tool_call.mcp_server_id,
            tool_call.tool_name,
            tool_call.arguments
        )

    async def test_connection(self, mcp_id: str) -> tuple[bool, Optional[str]]:
        """Test connection to an MCP server.

        Returns:
            (success, error_message)
        """
        client = self._clients.get(mcp_id)
        if not client:
            mcp_data = db.get_mcp_server(mcp_id)
            if not mcp_data:
                return False, "MCP server not found"

            client = MCPClient(
                mcp_data['name'],
                mcp_data['transport'],
                mcp_data['config']
            )
            self._clients[mcp_id] = client

        success = await client.connect()

        if success:
            # Disconnect after test to avoid keeping connections open
            await client.disconnect()
            return True, None
        else:
            return False, client.error or "Connection failed"

    async def load_from_database(self):
        """Load all active MCP servers from database and connect."""
        import logging
        logger = logging.getLogger(__name__)

        mcps = db.list_mcp_servers(active_only=True)
        logger.info(f"[MCP REGISTRY] Loading {len(mcps)} MCP servers from database")

        for mcp in mcps:
            try:
                # Validate transport type
                if mcp['transport'] not in ['stdio', 'sse', 'websocket']:
                    logger.warning(f"[MCP REGISTRY] Skipping {mcp['name']}: unknown transport '{mcp['transport']}'")
                    continue

                client = MCPClient(
                    mcp['name'],
                    mcp['transport'],
                    mcp['config']
                )
                self._clients[mcp['id']] = client

                # Try to connect (but don't fail startup if connection fails)
                try:
                    await self.connect_mcp(mcp['id'])
                    logger.info(f"[MCP REGISTRY] Connected to {mcp['name']}")
                except Exception as e:
                    logger.warning(f"[MCP REGISTRY] Failed to connect to {mcp['name']}: {e}")

            except Exception as e:
                logger.error(f"[MCP REGISTRY] Error loading MCP {mcp.get('name', 'unknown')}: {e}")

    async def close_all(self):
        """Close all MCP connections."""
        for mcp_id in list(self._clients.keys()):
            await self.disconnect_mcp(mcp_id)

        self._clients.clear()
        self._tools.clear()


# Global registry instance
mcp_registry = MCPRegistry()

"""Admin API routes for MCP Framework."""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query

from app.core.agent_config import agent_config_manager
from app.core.database import db
from app.mcp.registry import mcp_registry
from app.mcp.templates import list_templates, create_from_template
from app.models.schemas import (
    Agent, AgentCreate, AgentUpdate,
    MCPServer, MCPServerCreate, MCPServerUpdate, MCPServerWithStatus,
    MCPAccessGrant, MCPAccessUpdate,
    AgentGroup, AgentGroupCreate, AgentGroupWithMembers,
    PermissionMatrix, PermissionMatrixCell,
    MCPTool,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Agent Management
# ============================================================================

@router.post("/agents", response_model=Agent)
async def create_agent(data: AgentCreate):
    """Create a new agent."""
    try:
        return agent_config_manager.create_agent(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@router.get("/agents", response_model=list[Agent])
async def list_agents(active_only: bool = Query(True)):
    """List all agents."""
    try:
        return agent_config_manager.list_agents(active_only=active_only)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")


@router.get("/agents/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    """Get a specific agent."""
    agent = agent_config_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, data: AgentUpdate):
    """Update an agent."""
    agent = agent_config_manager.update_agent(agent_id, data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent."""
    success = agent_config_manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted"}


# ============================================================================
# MCP Server Management
# ============================================================================

@router.post("/mcps", response_model=MCPServer)
async def create_mcp(data: MCPServerCreate):
    """Register a new MCP server."""
    try:
        import uuid
        mcp_id = str(uuid.uuid4())

        result = db.create_mcp_server(
            mcp_id=mcp_id,
            name=data.name,
            transport=data.transport,
            config=data.config,
            description=data.description
        )
        return MCPServer(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create MCP: {str(e)}")


@router.get("/mcps", response_model=list[MCPServerWithStatus])
async def list_mcps(active_only: bool = Query(True)):
    """List all MCP servers with their status."""
    try:
        mcps = mcp_registry.list_mcps(active_only=active_only)
        return [
            MCPServerWithStatus(
                id=m.id,
                name=m.name,
                description=m.description,
                transport=m.transport,
                is_active=m.is_active,
                config=db.get_mcp_server(m.id).get('config', {}),
                created_at=db.get_mcp_server(m.id).get('created_at'),
                status=m.status,
                tool_count=m.tool_count,
                last_error=m.last_error
            )
            for m in mcps
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list MCPs: {str(e)}")


@router.get("/mcps/{mcp_id}", response_model=MCPServerWithStatus)
async def get_mcp(mcp_id: str):
    """Get a specific MCP server."""
    mcp = mcp_registry.get_mcp(mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP server not found")

    full_data = db.get_mcp_server(mcp_id) or {}
    return MCPServerWithStatus(
        id=mcp.id,
        name=mcp.name,
        description=mcp.description,
        transport=mcp.transport,
        is_active=mcp.is_active,
        config=full_data.get('config', {}),
        created_at=full_data.get('created_at'),
        status=mcp.status,
        tool_count=mcp.tool_count,
        last_error=mcp.last_error
    )


@router.put("/mcps/{mcp_id}", response_model=MCPServer)
async def update_mcp(mcp_id: str, data: MCPServerUpdate):
    """Update an MCP server."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = db.update_mcp_server(mcp_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="MCP server not found")

    return MCPServer(**result)


@router.delete("/mcps/{mcp_id}")
async def delete_mcp(mcp_id: str):
    """Unregister an MCP server."""
    success = await mcp_registry.unregister_mcp(mcp_id)
    if not success:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {"message": "MCP server unregistered"}


@router.post("/mcps/{mcp_id}/test")
async def test_mcp_connection(mcp_id: str):
    """Test connection to an MCP server."""
    success, error = await mcp_registry.test_connection(mcp_id)
    if success:
        return {"status": "success", "message": "Connection successful"}
    else:
        return {"status": "error", "message": error or "Connection failed"}


@router.get("/mcps/{mcp_id}/tools", response_model=list[MCPTool])
async def get_mcp_tools(mcp_id: str):
    """Get tools available from an MCP server."""
    tools = mcp_registry.get_mcp_tools(mcp_id)
    return [
        MCPTool(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
            mcp_server_id=t.mcp_server_id,
            mcp_server_name=t.mcp_server_name
        )
        for t in tools
    ]


# ============================================================================
# MCP Templates
# ============================================================================

@router.get("/mcp-templates")
async def list_mcp_templates():
    """List available MCP templates."""
    return {"templates": list_templates()}


@router.post("/mcp-templates/{template_name}")
async def create_from_mcp_template(template_name: str, name: str, variables: dict[str, Any]):
    """Create an MCP server from a template."""
    try:
        config = create_from_template(template_name, name, **variables)
        return await create_mcp(MCPServerCreate(**config))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create from template: {str(e)}")


# ============================================================================
# Permission Management
# ============================================================================

@router.post("/agents/{agent_id}/mcps")
async def grant_mcp_access(agent_id: str, data: MCPAccessGrant):
    """Grant an agent access to an MCP server."""
    success = agent_config_manager.grant_mcp_access(
        agent_id, data.mcp_id, data.allowed_tools
    )
    if not success:
        raise HTTPException(status_code=404, detail="Agent or MCP server not found")
    return {"message": "MCP access granted"}


@router.get("/agents/{agent_id}/mcps", response_model=list[MCPServer])
async def get_agent_mcps(agent_id: str):
    """Get all MCP servers an agent has access to."""
    mcps = agent_config_manager.get_agent_mcps(agent_id)
    return mcps


@router.delete("/agents/{agent_id}/mcps/{mcp_id}")
async def revoke_mcp_access(agent_id: str, mcp_id: str):
    """Revoke an agent's access to an MCP server."""
    success = agent_config_manager.revoke_mcp_access(agent_id, mcp_id)
    if not success:
        raise HTTPException(status_code=404, detail="Permission not found")
    return {"message": "MCP access revoked"}


@router.put("/agents/{agent_id}/mcps/{mcp_id}")
async def update_mcp_permissions(agent_id: str, mcp_id: str, data: MCPAccessUpdate):
    """Update the allowed tools for an agent-MCP pair."""
    success = agent_config_manager.update_mcp_permissions(
        agent_id, mcp_id, data.allowed_tools
    )
    if not success:
        raise HTTPException(status_code=404, detail="Permission not found")
    return {"message": "Permissions updated"}


@router.get("/permissions/matrix", response_model=PermissionMatrix)
async def get_permission_matrix():
    """Get the full permission matrix."""
    matrix = agent_config_manager.get_permission_matrix()

    # Build cells with tool info
    cells = []
    for perm in matrix["permissions"]:
        mcp_tools = mcp_registry.get_mcp_tools(perm["mcp_id"])
        cells.append(PermissionMatrixCell(
            agent_id=perm["agent_id"],
            mcp_id=perm["mcp_id"],
            has_access=perm["has_access"],
            allowed_tools=perm["allowed_tools"],
            all_tools=[t.name for t in mcp_tools]
        ))

    return PermissionMatrix(
        agents=matrix["agents"],
        mcps=matrix["mcps"],
        permissions=cells
    )


# ============================================================================
# Agent Groups
# ============================================================================

@router.post("/groups", response_model=AgentGroup)
async def create_agent_group(data: AgentGroupCreate):
    """Create a new agent group."""
    result = agent_config_manager.create_agent_group(data.name, data.description)
    return AgentGroup(**result)


@router.get("/groups", response_model=list[AgentGroup])
async def list_agent_groups():
    """List all agent groups."""
    groups = agent_config_manager.list_agent_groups()
    return [AgentGroup(**g) for g in groups]


@router.get("/groups/{group_id}", response_model=AgentGroupWithMembers)
async def get_agent_group(group_id: str):
    """Get an agent group with its members."""
    group = agent_config_manager.get_agent_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    agents = agent_config_manager.get_group_agents(group_id)
    return AgentGroupWithMembers(
        id=group["id"],
        name=group["name"],
        description=group.get("description"),
        created_at=group.get("created_at"),
        agents=agents
    )


@router.delete("/groups/{group_id}")
async def delete_agent_group(group_id: str):
    """Delete an agent group."""
    success = agent_config_manager.delete_agent_group(group_id)
    if not success:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"message": "Group deleted"}


@router.post("/groups/{group_id}/agents/{agent_id}")
async def add_agent_to_group(group_id: str, agent_id: str):
    """Add an agent to a group."""
    success = agent_config_manager.add_agent_to_group(group_id, agent_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add agent to group")
    return {"message": "Agent added to group"}


@router.delete("/groups/{group_id}/agents/{agent_id}")
async def remove_agent_from_group(group_id: str, agent_id: str):
    """Remove an agent from a group."""
    success = agent_config_manager.remove_agent_from_group(group_id, agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not in group")
    return {"message": "Agent removed from group"}

"""Agent Configuration Manager for database-driven agent management."""

import uuid
from typing import Optional

from app.core.database import db
from app.models.schemas import Agent, AgentCreate, AgentUpdate, MCPServer


class AgentConfigManager:
    """Manages agent configurations stored in the database.

    Provides CRUD operations for agents and their MCP permissions.
    """

    def __init__(self):
        pass

    # Agent CRUD
    def create_agent(self, data: AgentCreate) -> Agent:
        """Create a new agent."""
        agent_id = str(uuid.uuid4())

        result = db.create_agent(
            agent_id=agent_id,
            name=data.name,
            description=data.description,
            system_prompt=data.system_prompt,
            model=data.model,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            speak_probability=data.speak_probability,
            avatar_url=data.avatar_url
        )

        return Agent(**result)

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        result = db.get_agent(agent_id)
        if result:
            return Agent(**result)
        return None

    def update_agent(self, agent_id: str, data: AgentUpdate) -> Optional[Agent]:
        """Update an agent."""
        # Filter out None values
        updates = {k: v for k, v in data.model_dump().items() if v is not None}

        if not updates:
            return self.get_agent(agent_id)

        result = db.update_agent(agent_id, **updates)
        if result:
            return Agent(**result)
        return None

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        return db.delete_agent(agent_id)

    def list_agents(self, active_only: bool = True) -> list[Agent]:
        """List all agents."""
        results = db.list_agents(active_only=active_only)
        return [Agent(**r) for r in results]

    def get_agent_with_mcps(self, agent_id: str) -> Optional[dict]:
        """Get an agent with its MCP permissions."""
        agent = self.get_agent(agent_id)
        if not agent:
            return None

        mcps = db.get_agent_mcps(agent_id)
        return {
            "agent": agent,
            "mcps": [MCPServer(**m) for m in mcps]
        }

    # MCP Permission Management
    def grant_mcp_access(self, agent_id: str, mcp_id: str,
                        allowed_tools: list[str] = None) -> bool:
        """Grant an agent access to an MCP server."""
        # Verify agent and MCP exist
        agent = db.get_agent(agent_id)
        mcp = db.get_mcp_server(mcp_id)

        if not agent or not mcp:
            return False

        db.grant_mcp_access(agent_id, mcp_id, allowed_tools)
        return True

    def revoke_mcp_access(self, agent_id: str, mcp_id: str) -> bool:
        """Revoke an agent's access to an MCP server."""
        return db.revoke_mcp_access(agent_id, mcp_id)

    def get_agent_mcps(self, agent_id: str) -> list[MCPServer]:
        """Get all MCP servers an agent has access to."""
        mcps = db.get_agent_mcps(agent_id)
        return [MCPServer(**m) for m in mcps]

    def update_mcp_permissions(self, agent_id: str, mcp_id: str,
                               allowed_tools: list[str] = None) -> bool:
        """Update the allowed tools for an agent-MCP pair."""
        result = db.update_mcp_permissions(agent_id, mcp_id, allowed_tools)
        return result is not None

    # Permission Matrix
    def get_permission_matrix(self) -> dict:
        """Get the full permission matrix for all agents and MCPs."""
        agents = self.list_agents()
        mcps = db.list_mcp_servers()

        # Build permission grid
        permissions = []
        for agent in agents:
            agent_mcps = {m['id']: m for m in db.get_agent_mcps(agent.id)}

            for mcp in mcps:
                has_access = mcp['id'] in agent_mcps
                allowed_tools = agent_mcps.get(mcp['id'], {}).get('allowed_tools')

                permissions.append({
                    "agent_id": agent.id,
                    "mcp_id": mcp['id'],
                    "has_access": has_access,
                    "allowed_tools": allowed_tools
                })

        return {
            "agents": agents,
            "mcps": [MCPServer(**m) for m in mcps],
            "permissions": permissions
        }

    # Agent Group Management
    def create_agent_group(self, name: str, description: str = None) -> dict:
        """Create a new agent group."""
        group_id = str(uuid.uuid4())
        return db.create_agent_group(group_id, name, description)

    def get_agent_group(self, group_id: str) -> Optional[dict]:
        """Get an agent group by ID."""
        return db.get_agent_group(group_id)

    def delete_agent_group(self, group_id: str) -> bool:
        """Delete an agent group."""
        return db.delete_agent_group(group_id)

    def list_agent_groups(self) -> list[dict]:
        """List all agent groups."""
        return db.list_agent_groups()

    def add_agent_to_group(self, group_id: str, agent_id: str) -> bool:
        """Add an agent to a group."""
        return db.add_agent_to_group(group_id, agent_id)

    def remove_agent_from_group(self, group_id: str, agent_id: str) -> bool:
        """Remove an agent from a group."""
        return db.remove_agent_from_group(group_id, agent_id)

    def get_group_agents(self, group_id: str) -> list[Agent]:
        """Get all agents in a group."""
        agents = db.get_group_agents(group_id)
        return [Agent(**a) for a in agents]


# Global instance
agent_config_manager = AgentConfigManager()

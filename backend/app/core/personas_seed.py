"""Seed default personas into the database."""

from app.core.database import db
from app.core.personas import PERSONAS


# Default MCP access for each persona
# Maps persona key to list of (mcp_name, allowed_tools) tuples
# allowed_tools=None means all tools allowed
DEFAULT_MCP_ACCESS = {
    "the_lazy_one": [],  # No MCP access - wants to avoid work
    "the_egomaniac": [
        ("filesystem", ["read_file", "list_directory"]),
    ],
    "the_devils_advocate": [
        ("filesystem", ["read_file", "list_directory"]),
    ],
    "the_creative": [],  # No MCP access - relies on imagination
    "the_pragmatist": [
        ("filesystem", ["read_file", "list_directory"]),  # Read-only
    ],
    "the_developer": [
        ("filesystem", None),  # Full access - can read, write, list
    ],
    "the_empath": [],  # No MCP access - focuses on human aspects
    "the_researcher": [
        ("filesystem", ["read_file", "list_directory"]),  # Read-only
    ],
    "the_orchestrator": [],  # Special - gets all MCPs dynamically
}


def seed_personas():
    """Seed default personas into the database. Adds missing personas if already seeded."""
    print("[SEED] Checking for personas to seed...")

    # Create MCP servers first (if not exist)
    _ensure_mcp_servers()

    # Get existing agent IDs (column is 'id', not 'agent_id')
    existing_agents = db.list_agents(active_only=True)
    existing_agent_ids = {a.get('id') or a.get('agent_id') for a in existing_agents}
    print(f"[SEED] Found {len(existing_agent_ids)} existing agents")

    added_count = 0
    for persona_key, persona in PERSONAS.items():
        agent_id = f"persona_{persona_key}"

        # Skip if already exists
        if agent_id in existing_agent_ids:
            continue

        # Create agent
        db.create_agent(
            agent_id=agent_id,
            name=persona.name,
            description=f"Default {persona.name} persona",
            system_prompt=persona.system_prompt,
            model="openai/gpt-4o-mini",
            temperature=persona.temperature,
            max_tokens=persona.max_tokens or 2000,
            speak_probability=persona.speak_probability,
            avatar_url=None
        )

        print(f"[SEED] Created agent: {persona.name}")
        added_count += 1

        # Grant MCP access
        mcp_access = DEFAULT_MCP_ACCESS.get(persona_key, [])
        for mcp_name, allowed_tools in mcp_access:
            mcp = db.get_mcp_server_by_name(mcp_name)
            if mcp:
                db.grant_mcp_access(agent_id, mcp['id'], allowed_tools)
                print(f"[SEED]   Granted {mcp_name} access to {persona.name}")

    if added_count > 0:
        print(f"[SEED] Added {added_count} new persona(s)")
    else:
        print("[SEED] All personas already exist")


def _ensure_mcp_servers():
    """Ensure default MCP servers exist.

    Note: Built-in tools (web_search, web_fetch, execute_python) are handled
    by the existing MCPToolServer and should NOT be registered as MCP servers.
    Only external MCP servers (stdio, sse, websocket) are registered here.
    """
    import uuid
    from app.mcp.templates import MCP_TEMPLATES

    default_mcps = {
        "filesystem": {
            "template": "filesystem",
            "vars": {"WORKSPACE_PATH": "."}
        },
        # Note: web_search, web_fetch, execute_python are built-in tools
        # handled by MCPToolServer, not registered as MCP servers
    }

    for name, data in default_mcps.items():
        existing = db.get_mcp_server_by_name(name)
        if existing:
            continue

        if data["template"]:
            template = MCP_TEMPLATES.get(data["template"])
            if template:
                config = template.render_config(**data["vars"])
                db.create_mcp_server(
                    mcp_id=str(uuid.uuid4()),
                    name=name,
                    transport=template.transport,
                    config=config,
                    description=template.description
                )
                print(f"[SEED] Created MCP server: {name}")


def get_persona_agent_id(persona_key: str) -> str:
    """Get the agent ID for a persona key."""
    return f"persona_{persona_key}"


def seed_if_needed():
    """Seed personas if database is empty."""
    seed_personas()

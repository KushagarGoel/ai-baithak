"""MCP server templates for common use cases."""

from typing import Any


class MCPTemplate:
    """A template for creating an MCP server."""

    def __init__(self, name: str, description: str, transport: str, config: dict[str, Any]):
        self.name = name
        self.description = description
        self.transport = transport
        self.config = config

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "transport": self.transport,
            "config": self.config
        }

    def render_config(self, **kwargs) -> dict[str, Any]:
        """Render config with variable substitution."""
        import copy
        import json

        # Serialize and substitute
        config_str = json.dumps(self.config)
        for key, value in kwargs.items():
            placeholder = f"{{{{{key}}}}}"
            config_str = config_str.replace(placeholder, str(value))

        return json.loads(config_str)


# Built-in MCP templates
MCP_TEMPLATES: dict[str, MCPTemplate] = {
    "filesystem": MCPTemplate(
        name="filesystem",
        description="Read and write local files",
        transport="stdio",
        config={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{{WORKSPACE_PATH}}"],
            "env": {}
        }
    ),

    "github": MCPTemplate(
        name="github",
        description="Search repos, create PRs, manage issues",
        transport="stdio",
        config={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": "{{GITHUB_TOKEN}}"
            }
        }
    ),

    "sqlite": MCPTemplate(
        name="sqlite",
        description="Query SQLite databases",
        transport="stdio",
        config={
            "command": "uvx",
            "args": ["mcp-server-sqlite", "--db-path", "{{DB_PATH}}"],
            "env": {}
        }
    ),

    "postgres": MCPTemplate(
        name="postgres",
        description="Query PostgreSQL databases",
        transport="stdio",
        config={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres", "{{DATABASE_URL}}"],
            "env": {}
        }
    ),

    "brave-search": MCPTemplate(
        name="brave-search",
        description="Web search via Brave API (SSE)",
        transport="sse",
        config={
            "url": "https://api.search.brave.com/mcp",
            "headers": {
                "Authorization": "Bearer {{API_KEY}}"
            }
        }
    ),

    "fetch": MCPTemplate(
        name="fetch",
        description="Fetch web pages and extract content",
        transport="stdio",
        config={
            "command": "uvx",
            "args": ["mcp-server-fetch"],
            "env": {}
        }
    ),

    "puppeteer": MCPTemplate(
        name="puppeteer",
        description="Browser automation with Puppeteer",
        transport="stdio",
        config={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
            "env": {}
        }
    ),

    "playwright": MCPTemplate(
        name="playwright",
        description="Browser automation with Playwright (screenshots, clicks, scraping)",
        transport="stdio",
        config={
            "command": "npx",
            "args": ["-y", "@anthropic-ai/playwright-mcp"],
            "env": {}
        }
    ),

    "memory": MCPTemplate(
        name="memory",
        description="Knowledge graph memory for persistent storage",
        transport="stdio",
        config={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "env": {}
        }
    ),
}


def get_template(name: str) -> MCPTemplate:
    """Get a template by name."""
    if name not in MCP_TEMPLATES:
        raise ValueError(f"Unknown MCP template: {name}. Available: {list(MCP_TEMPLATES.keys())}")
    return MCP_TEMPLATES[name]


def list_templates() -> list[dict[str, Any]]:
    """List all available templates."""
    return [t.to_dict() for t in MCP_TEMPLATES.values()]


def create_from_template(template_name: str, name: str, **kwargs) -> dict[str, Any]:
    """Create an MCP server config from a template."""
    template = get_template(template_name)

    return {
        "name": name,
        "description": template.description,
        "transport": template.transport,
        "config": template.render_config(**kwargs)
    }

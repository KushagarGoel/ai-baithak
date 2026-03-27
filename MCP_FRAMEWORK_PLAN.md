# MCP Agent Framework - Architecture Plan

## Overview
Build a flexible **UI-configurable** framework where:
1. **MCP Servers** can be registered via UI/API (filesystem, web search, database, etc.)
2. **Agent Personas** are stored in SQLite and fully manageable via UI
3. **Agents** can be granted access to specific MCPs through a visual permission matrix
4. **Users** configure everything through an intuitive Admin UI

### Key Principle: UI-First Configuration
Everything should be configurable without touching code or config files.

---

## Core Components

### 1. MCP Registry (`/backend/app/mcp/registry.py`)
Manages multiple MCP server connections.

```python
class MCPRegistry:
    """
    Central registry for all MCP servers.
    Supports stdio, SSE, and WebSocket transports.
    """
    - register_mcp(name, transport, config)
    - unregister_mcp(name)
    - list_mcps() -> List[MCPInfo]
    - get_mcp_tools(mcp_name) -> List[Tool]
    - execute_tool(mcp_name, tool_name, params)
    - get_all_tools_for_agent(agent_id) -> List[Tool]
```

**MCP Server Types:**
- `stdio` - Local subprocess (e.g., npx, python)
- `sse` - Server-Sent Events over HTTP
- `websocket` - WebSocket connection

**Example MCP Configurations:**
```json
{
  "filesystem": {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/workspace"]
  },
  "github": {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "..."}
  },
  "sqlite": {
    "transport": "stdio",
    "command": "uvx",
    "args": ["mcp-server-sqlite", "--db-path", "/path/to/db.sqlite"]
  },
  "brave-search": {
    "transport": "sse",
    "url": "https://api.search.brave.com/mcp",
    "headers": {"Authorization": "Bearer ..."}
  }
}
```

---

### 2. Agent Configuration System (`/backend/app/core/agent_config.py`)
SQLite-based storage for agent definitions.

**Database Schema:**

```sql
-- agents table
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    model TEXT DEFAULT 'openai/gpt-4o-mini',
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 2000,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- mcp_servers table
CREATE TABLE mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    transport TEXT NOT NULL, -- 'stdio', 'sse', 'websocket'
    config JSON NOT NULL,    -- Full configuration object
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- agent_mcp_permissions table (many-to-many)
CREATE TABLE agent_mcp_permissions (
    agent_id TEXT NOT NULL,
    mcp_id TEXT NOT NULL,
    allowed_tools JSON,      -- NULL = all tools allowed, else ["tool1", "tool2"]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, mcp_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (mcp_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
);

-- agent_groups table (for organizing agents)
CREATE TABLE agent_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- agent_group_members table
CREATE TABLE agent_group_members (
    group_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    PRIMARY KEY (group_id, agent_id),
    FOREIGN KEY (group_id) REFERENCES agent_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);
```

**AgentConfigManager Class:**
```python
class AgentConfigManager:
    # Agent CRUD
    - create_agent(name, system_prompt, **config) -> Agent
    - get_agent(agent_id) -> Agent
    - update_agent(agent_id, **fields)
    - delete_agent(agent_id)
    - list_agents() -> List[Agent]

    # MCP CRUD
    - create_mcp(name, transport, config) -> MCP
    - get_mcp(mcp_id) -> MCP
    - update_mcp(mcp_id, **fields)
    - delete_mcp(mcp_id)
    - list_mcps() -> List[MCP]

    # Permission management
    - grant_mcp_access(agent_id, mcp_id, allowed_tools=None)
    - revoke_mcp_access(agent_id, mcp_id)
    - get_agent_mcps(agent_id) -> List[MCPWithPermissions]
    - get_mcp_agents(mcp_id) -> List[Agent]
```

---

### 3. Enhanced Agent Class (`/backend/app/core/agent.py`)
Integrates with MCP registry for dynamic tool access.

```python
class CouncilAgent:
    def __init__(self, agent_config: Agent, mcp_registry: MCPRegistry):
        self.config = agent_config
        self.mcp_registry = mcp_registry
        self.available_tools = self._load_tools()

    def _load_tools(self) -> List[Tool]:
        """Load all tools from MCPs this agent has access to."""
        return self.mcp_registry.get_all_tools_for_agent(self.config.id)

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool via the MCP registry."""
        return await self.mcp_registry.execute_tool_call(tool_call)
```

---

### 4. Default Agent Personas (`/backend/app/core/personas.py`)
Keep existing personas but store them in the database.

**Migration on startup:**
- Check if agents table is empty
- If empty, insert default personas with appropriate MCP access:

| Persona | Default MCP Access |
|---------|-------------------|
| The Lazy One | None (or web search only) |
| The Know-It-All | web_search, web_fetch |
| Devil's Advocate | web_search |
| The Creative | None |
| The Pragmatist | filesystem (read-only), web_search |
| The Empath | None |
| The Researcher | web_search, web_fetch, filesystem (read-only) |
| The Orchestrator | All MCPs |

---

### 5. Admin API Endpoints (`/backend/app/api/admin.py`)

```python
# Agent Management
POST   /api/admin/agents              # Create new agent
GET    /api/admin/agents              # List all agents
GET    /api/admin/agents/{id}         # Get agent details
PUT    /api/admin/agents/{id}         # Update agent
DELETE /api/admin/agents/{id}         # Delete agent

# MCP Management
POST   /api/admin/mcps                # Register new MCP
GET    /api/admin/mcps                # List all MCPs
GET    /api/admin/mcps/{id}           # Get MCP details
PUT    /api/admin/mcps/{id}           # Update MCP
DELETE /api/admin/mcps/{id}           # Unregister MCP
POST   /api/admin/mcps/{id}/test      # Test MCP connection

# Permission Management
POST   /api/admin/agents/{id}/mcps    # Grant MCP access
GET    /api/admin/agents/{id}/mcps    # Get agent's MCPs
DELETE /api/admin/agents/{id}/mcps/{mcp_id}  # Revoke access
PUT    /api/admin/agents/{id}/mcps/{mcp_id}  # Update permissions

# Agent Groups
POST   /api/admin/groups              # Create group
GET    /api/admin/groups              # List groups
POST   /api/admin/groups/{id}/agents  # Add agent to group
```

---

### 6. Frontend Admin UI - Fully Configurable

#### Navigation Structure
```
Admin Panel (accessible from main sidebar)
├── MCP Servers
│   ├── List View (all registered MCPs)
│   ├── Add MCP (form to register new server)
│   └── Edit MCP (modify config, test connection)
├── Agents
│   ├── List View (all agent personas)
│   ├── Create Agent (full agent builder)
│   └── Edit Agent (modify prompts, model, MCP access)
└── Permissions
    └── Matrix View (visual grid: Agents x MCPs)
```

#### UI Components Detail

**MCP Management UI:**
```
┌─────────────────────────────────────────┐
│ MCP Servers                              │
│ [+ Add MCP Server]                      │
├─────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐        │
│ │ filesystem  │ │ github      │  ...   │
│ │ ● Active    │ │ ● Active    │        │
│ │ Tools: 4    │ │ Tools: 8    │        │
│ │ [Edit] [×]  │ │ [Edit] [×]  │        │
│ └─────────────┘ └─────────────┘        │
└─────────────────────────────────────────┘
```

**Add MCP Form:**
- Quick Templates (dropdown):
  - Filesystem (npx @modelcontextprotocol/server-filesystem)
  - GitHub (npx @modelcontextprotocol/server-github)
  - SQLite (uvx mcp-server-sqlite)
  - Brave Search (SSE)
  - Custom (manual entry)
- Name (e.g., "filesystem", "github")
- Description
- Transport Type: stdio / SSE / WebSocket
- Dynamic form fields based on transport:
  - stdio: Command, Arguments (array), Environment Variables
  - SSE: URL, Headers
  - WebSocket: URL, Protocols
- [Test Connection] button
- Tool Preview (shows discovered tools after test)

**MCP Templates (built-in):**
Users can select from pre-configured templates, then customize:
```typescript
const MCP_TEMPLATES = [
  {
    name: "Filesystem",
    description: "Read and write local files",
    transport: "stdio",
    config: {
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-filesystem", "{{WORKSPACE_PATH}}"]
    }
  },
  {
    name: "GitHub",
    description: "Search repos, create PRs, manage issues",
    transport: "stdio",
    config: {
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-github"],
      env: { "GITHUB_PERSONAL_ACCESS_TOKEN": "" }
    }
  },
  {
    name: "SQLite",
    description: "Query SQLite databases",
    transport: "stdio",
    config: {
      command: "uvx",
      args: ["mcp-server-sqlite", "--db-path", "{{DB_PATH}}"]
    }
  },
  {
    name: "Brave Search",
    description: "Web search via Brave API",
    transport: "sse",
    config: {
      url: "https://api.search.brave.com/mcp",
      headers: { "Authorization": "Bearer {{API_KEY}}" }
    }
  }
];```

**Agent Builder UI:**
```
┌─────────────────────────────────────────┐
│ Create Agent                             │
├─────────────────────────────────────────┤
│ Name: [________________]                │
│ Description: [________________]         │
│                                         │
│ Model: [gpt-4o-mini ▼]                  │
│ Temperature: [0.7] (slider 0-1)         │
│ Max Tokens: [2000]                      │
│                                         │
│ System Prompt:                          │
│ ┌─────────────────────────────────┐    │
│ │                                 │    │
│ │  Rich text editor or textarea   │    │
│ │                                 │    │
│ └─────────────────────────────────┘    │
│                                         │
│ MCP Access:                             │
│ [ ] filesystem  (4 tools)               │
│   [x] read_file                         │
│   [x] list_directory                    │
│   [ ] write_file                        │
│ [x] github      (8 tools)               │
│   [x] All tools                         │
│                                         │
│ [Save Agent]                            │
└─────────────────────────────────────────┘
```

**Permission Matrix UI:**
```
┌────────────────────────────────────────────────────┐
│ Permissions Matrix                                  │
├──────────────┬──────────┬──────────┬──────────┬────┤
│ Agent        │ filesystem│ github   │ sqlite   │ ...│
├──────────────┼──────────┼──────────┼──────────┼────┤
│ Dev          │ [x] 4/4  │ [x] 8/8  │ [ ]      │    │
│ Researcher   │ [x] 2/4  │ [ ]      │ [x] 5/5  │    │
│ Creative     │ [ ]      │ [ ]      │ [ ]      │    │
│ ...          │          │          │          │    │
└──────────────┴──────────┴──────────┴──────────┴────┘
│ Legend: [x] = enabled, 4/4 = tools granted          │
│ Click cell to toggle or configure specific tools    │
└────────────────────────────────────────────────────┘
```

**Inline MCP Tool Config (Modal):**
When clicking a matrix cell or MCP checkbox:
```
┌─────────────────────────────┐
│ Configure filesystem access │
├─────────────────────────────┤
│ Dev agent can use:          │
│ [x] read_file               │
│ [x] list_directory          │
│ [x] write_file              │
│ [ ] delete_file             │
│                             │
│ [Save] [Cancel]             │
└─────────────────────────────┘
```

#### Real-time Features
- Connection status indicators for MCPs (● Active / ● Offline)
- Test connection button with success/failure feedback
- Tool discovery preview after MCP registration
- Live validation of forms

---

## Implementation Plan

### Phase 1: Foundation (Sequential)
**Goal**: Database and core models ready

| Task | File | Effort |
|------|------|--------|
| 1.1 Create database migrations | `/backend/app/migrations/001_agent_mcp_tables.py` | 2h |
| 1.2 Update database.py with new tables | `/backend/app/core/database.py` | 1h |
| 1.3 Create Pydantic schemas | `/backend/app/models/schemas.py` | 2h |

**Deliverable**: Database schema ready, migrations working

---

### Phase 2: Backend Core (Parallel Tracks)

#### Track A: Agent Configuration System
| Task | File | Effort |
|------|------|--------|
| 2A.1 Build AgentConfigManager | `/backend/app/core/agent_config.py` | 4h |
| 2A.2 Seed default personas | `/backend/app/core/personas_seed.py` | 2h |

#### Track B: MCP Registry
| Task | File | Effort |
|------|------|--------|
| 2B.1 Build MCP client (stdio) | `/backend/app/mcp/client.py` | 4h |
| 2B.2 Build MCPRegistry | `/backend/app/mcp/registry.py` | 4h |
| 2B.3 Add MCP templates | `/backend/app/mcp/templates.py` | 2h |

**Parallel**: Track A and Track B can be done simultaneously
**Deliverable**: AgentConfigManager and MCPRegistry working independently

---

### Phase 3: Integration (Sequential)
**Goal**: Connect all backend pieces

| Task | File | Effort | Depends On |
|------|------|--------|------------|
| 3.1 Update CouncilAgent to use DB config | `/backend/app/core/agent.py` | 3h | 2A, 2B |
| 3.2 Update Orchestrator | `/backend/app/core/orchestrator.py` | 2h | 3.1 |
| 3.3 Integrate tools with registry | `/backend/app/mcp/tools.py` | 2h | 2B |
| 3.4 Create test MCP server | `/backend/app/mcp/test_server.py` | 1h | 2B |

**Deliverable**: Backend fully functional with DB-driven agents and MCPs

---

### Phase 4: Admin API (Can start after Phase 2)

| Task | File | Effort | Depends On |
|------|------|--------|------------|
| 4.1 Create Admin API router | `/backend/app/api/admin.py` | 4h | 2A, 2B |
| 4.2 Add agent CRUD endpoints | (in admin.py) | 3h | 4.1 |
| 4.3 Add MCP CRUD endpoints | (in admin.py) | 3h | 4.1 |
| 4.4 Add permission endpoints | (in admin.py) | 2h | 4.1 |
| 4.5 Add test connection endpoint | (in admin.py) | 2h | 4.1 |
| 4.6 Wire up to main.py | `/backend/app/main.py` | 1h | 4.1-4.5 |

**Parallel**: Can start after Phase 2 completes (independent of Phase 3)
**Deliverable**: Full Admin API ready for frontend

---

### Phase 5: Frontend (Parallel Tracks after Phase 4)

#### Track C: Admin Layout & API Client
| Task | File | Effort |
|------|------|--------|
| 5C.1 Create admin layout | `/frontend/app/admin/layout.tsx` | 2h |
| 5C.2 Create API client hooks | `/frontend/hooks/useAdminApi.ts` | 3h |
| 5C.3 Add admin to main nav | `/frontend/components/Sidebar.tsx` | 1h |

#### Track D: MCP Management UI (can start after 5C.1)
| Task | File | Effort | Depends On |
|------|------|--------|------------|
| 5D.1 MCP list page | `/frontend/app/admin/mcps/page.tsx` | 3h | 5C |
| 5D.2 MCP card component | `/frontend/components/admin/MCPCard.tsx` | 2h | 5D.1 |
| 5D.3 Add MCP form with templates | `/frontend/app/admin/mcps/new/page.tsx` | 4h | 5D.1 |
| 5D.4 Dynamic transport fields | `/frontend/components/admin/TransportConfig.tsx` | 3h | 5D.3 |
| 5D.5 Test connection button | (in new/page.tsx) | 2h | 5D.3 |

#### Track E: Agent Management UI (can start after 5C.1)
| Task | File | Effort | Depends On |
|------|------|--------|------------|
| 5E.1 Agent list page | `/frontend/app/admin/agents/page.tsx` | 3h | 5C |
| 5E.2 Agent card component | `/frontend/components/admin/AgentCard.tsx` | 2h | 5E.1 |
| 5E.3 Create agent form | `/frontend/app/admin/agents/new/page.tsx` | 4h | 5E.1 |
| 5E.4 Model/temp selector | `/frontend/components/admin/ModelSelector.tsx` | 2h | 5E.3 |
| 5E.5 MCP access selector | `/frontend/components/admin/MCPAccessSelector.tsx` | 3h | 5E.3 |

#### Track F: Permission Matrix (after 5D, 5E)
| Task | File | Effort | Depends On |
|------|------|--------|------------|
| 5F.1 Permission matrix page | `/frontend/app/admin/permissions/page.tsx` | 4h | 5D, 5E |
| 5F.2 Matrix grid component | `/frontend/components/admin/PermissionMatrix.tsx` | 4h | 5F.1 |
| 5F.3 Tool config modal | `/frontend/components/admin/ToolConfigModal.tsx` | 3h | 5F.2 |

**Parallel**: Tracks C, D, E, F have dependencies shown above
**Deliverable**: Complete Admin UI

---

## Parallel Execution Summary

```
Week 1                    Week 2                    Week 3
────────────────────────────────────────────────────────────────
Phase 1 (2 days)
├── DB Migrations ──────────────────────────────────────────────

Phase 2 (4 days) - PARALLEL TRACKS
├── Track A: AgentConfig ─┐
│   └── AgentConfigManager│
├── Track B: MCP Registry │
│   ├── MCP Client        │
│   └── MCPRegistry       │
└─────────────────────────┴─────────────────────────────────────

Phase 3 (2 days)
├── Integration ────────────────────────────────────────────────
│   ├── Update CouncilAgent
│   ├── Update Orchestrator
│   └── Tool Integration

Phase 4 (3 days) - Can start when Track A & B done
├── Admin API ──────────────────────────────────────────────────
│   ├── Agent endpoints
│   ├── MCP endpoints
│   └── Permission endpoints

Phase 5 (4 days) - Can start when Phase 4 done
├── Track C: Layout/API ──┐
├── Track D: MCP UI ──────┼── Track F: Permissions ─────────────
└── Track E: Agent UI ────┘
```

## Minimum Viable Integration Points

**Between Phase 2A and 2B**: None (fully parallel)
**Between Phase 2 and 3**: Both tracks must complete
**Between Phase 3 and 4**: None (API uses same classes)
**Between Phase 4 and 5**: API must be ready

## Quick Wins (Do These First)

1. **Database migrations** - Unblocks everything
2. **MCP Templates** - Define the common MCP configs users will need
3. **AgentConfigManager CRUD** - Basic agent storage
4. **Agent list UI** - Simple table showing agents from DB
5. **MCP list UI** - Show registered MCPs with status

## Testing Strategy

| Phase | Test Approach |
|-------|--------------|
| 1 | Migration tests, schema validation |
| 2 | Unit tests for AgentConfigManager, MCPRegistry |
| 3 | Integration tests with real MCP server |
| 4 | API endpoint tests (pytest + httpx) |
| 5 | E2E tests with Playwright or manual QA |

---

## Example Usage

### Register a Filesystem MCP:
```bash
POST /api/admin/mcps
{
  "name": "filesystem",
  "description": "Local filesystem access",
  "transport": "stdio",
  "config": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
  }
}
```

### Create a Dev Agent:
```bash
POST /api/admin/agents
{
  "name": "Code Reviewer",
  "description": "Expert code reviewer with filesystem access",
  "system_prompt": "You are an expert code reviewer...",
  "model": "anthropic/claude-3-sonnet",
  "temperature": 0.3
}
```

### Grant Filesystem Access:
```bash
POST /api/admin/agents/{agent_id}/mcps
{
  "mcp_id": "filesystem",
  "allowed_tools": ["read_file", "list_directory"]  # Restrict to read-only
}
```

### Use in Discussion:
The Code Reviewer agent will now have filesystem tools available during discussions.

---

## File Structure

```
/backend/app/
├── core/
│   ├── agent_config.py      # NEW: Agent configuration manager
│   ├── database.py          UPDATE: Add new tables
│   └── migrations/          # NEW: Database migrations
├── mcp/
│   ├── registry.py          # NEW: MCP registry
│   ├── client.py            # NEW: MCP client (stdio/sse/ws)
│   ├── tools.py             # UPDATE: Integrate with registry
│   └── servers/             # NEW: Built-in MCP server configs
├── api/
│   ├── admin.py             # NEW: Admin API routes
│   └── websocket.py         # UPDATE: Use new agent system
└── models/
    └── schemas.py           # UPDATE: Pydantic models

/frontend/app/
├── admin/
│   ├── agents/
│   │   ├── page.tsx
│   │   └── new/page.tsx
│   ├── mcps/
│   │   ├── page.tsx
│   │   └── new/page.tsx
│   └── permissions/
│       └── page.tsx
└── components/admin/
    ├── AgentCard.tsx
    ├── MCPCard.tsx
    └── PermissionMatrix.tsx
```

---

## Benefits

1. **Modular**: Easy to add new MCP servers without code changes
2. **Secure**: Fine-grained tool-level permissions per agent
3. **Configurable**: Agents fully configurable via API/UI
4. **Extensible**: Easy to add new transport types
5. **Persistent**: All configuration in SQLite
6. **Multi-tenant**: Agent groups allow different council configurations

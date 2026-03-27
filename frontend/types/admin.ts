// Admin types for MCP Framework

export interface Agent {
  id: string;
  name: string;
  description?: string;
  system_prompt: string;
  model: string;
  temperature: number;
  max_tokens: number;
  speak_probability: number;
  avatar_url?: string;
  created_at?: string;
  updated_at?: string;
  is_active: boolean;
}

export interface AgentCreate {
  name: string;
  description?: string;
  system_prompt: string;
  model: string;
  temperature: number;
  max_tokens: number;
  speak_probability: number;
  avatar_url?: string;
}

export interface AgentUpdate {
  name?: string;
  description?: string;
  system_prompt?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  speak_probability?: number;
  avatar_url?: string;
  is_active?: boolean;
}

export interface MCPServer {
  id: string;
  name: string;
  description?: string;
  transport: 'stdio' | 'sse' | 'websocket';
  config: Record<string, any>;
  is_active: boolean;
  created_at?: string;
}

export interface MCPServerWithStatus extends MCPServer {
  status: 'active' | 'offline' | 'error' | 'unknown';
  tool_count: number;
  last_error?: string;
}

export interface MCPServerCreate {
  name: string;
  description?: string;
  transport: 'stdio' | 'sse' | 'websocket';
  config: Record<string, any>;
}

export interface MCPServerUpdate {
  name?: string;
  description?: string;
  transport?: 'stdio' | 'sse' | 'websocket';
  config?: Record<string, any>;
  is_active?: boolean;
}

export interface MCPTool {
  name: string;
  description: string;
  parameters: Record<string, any>;
  mcp_server_id: string;
  mcp_server_name: string;
}

export interface MCPAccessGrant {
  mcp_id: string;
  allowed_tools?: string[];
}

export interface MCPAccessUpdate {
  allowed_tools?: string[];
}

export interface PermissionMatrixCell {
  agent_id: string;
  mcp_id: string;
  has_access: boolean;
  allowed_tools?: string[];
  all_tools: string[];
}

export interface PermissionMatrix {
  agents: Agent[];
  mcps: MCPServer[];
  permissions: PermissionMatrixCell[];
}

export interface MCPTemplate {
  name: string;
  description: string;
  transport: string;
  config: Record<string, any>;
}

export interface AgentGroup {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
}

export interface AgentGroupCreate {
  name: string;
  description?: string;
}

export interface AgentGroupWithMembers extends AgentGroup {
  agents: Agent[];
}

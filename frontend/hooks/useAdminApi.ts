'use client';

import { useState, useCallback } from 'react';
import {
  Agent,
  AgentCreate,
  AgentUpdate,
  MCPServer,
  MCPServerCreate,
  MCPServerUpdate,
  MCPServerWithStatus,
  MCPTool,
  MCPAccessGrant,
  MCPAccessUpdate,
  PermissionMatrix,
  MCPTemplate,
  AgentGroup,
  AgentGroupCreate,
  AgentGroupWithMembers,
} from '@/types/admin';

const API_BASE = '/api';

export function useAdminApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchApi = useCallback(async <T>(url: string, options?: RequestInit): Promise<T | null> => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}${url}`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });

      if (response.status === 401) {
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        throw new Error('Unauthorized');
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Agents
  const listAgents = useCallback(async (): Promise<Agent[]> => {
    const result = await fetchApi<Agent[]>('/admin/agents');
    return result || [];
  }, [fetchApi]);

  const getAgent = useCallback(async (id: string): Promise<Agent | null> => {
    return await fetchApi<Agent>(`/admin/agents/${id}`);
  }, [fetchApi]);

  const createAgent = useCallback(async (data: AgentCreate): Promise<Agent | null> => {
    return await fetchApi<Agent>('/admin/agents', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }, [fetchApi]);

  const updateAgent = useCallback(async (id: string, data: AgentUpdate): Promise<Agent | null> => {
    return await fetchApi<Agent>(`/admin/agents/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }, [fetchApi]);

  const deleteAgent = useCallback(async (id: string): Promise<boolean> => {
    const result = await fetchApi<{ message: string }>(`/admin/agents/${id}`, {
      method: 'DELETE',
    });
    return result !== null;
  }, [fetchApi]);

  // MCP Servers
  const listMCPServers = useCallback(async (): Promise<MCPServerWithStatus[]> => {
    const result = await fetchApi<MCPServerWithStatus[]>('/admin/mcps');
    return result || [];
  }, [fetchApi]);

  const getMCPServer = useCallback(async (id: string): Promise<MCPServerWithStatus | null> => {
    return await fetchApi<MCPServerWithStatus>(`/admin/mcps/${id}`);
  }, [fetchApi]);

  const createMCPServer = useCallback(async (data: MCPServerCreate): Promise<MCPServer | null> => {
    return await fetchApi<MCPServer>('/admin/mcps', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }, [fetchApi]);

  const updateMCPServer = useCallback(async (id: string, data: MCPServerUpdate): Promise<MCPServer | null> => {
    return await fetchApi<MCPServer>(`/admin/mcps/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }, [fetchApi]);

  const deleteMCPServer = useCallback(async (id: string): Promise<boolean> => {
    const result = await fetchApi<{ message: string }>(`/admin/mcps/${id}`, {
      method: 'DELETE',
    });
    return result !== null;
  }, [fetchApi]);

  const testMCPConnection = useCallback(async (id: string): Promise<{ status: string; message: string }> => {
    const result = await fetchApi<{ status: string; message: string }>(`/admin/mcps/${id}/test`, {
      method: 'POST',
    });
    return result || { status: 'error', message: 'Test failed' };
  }, [fetchApi]);

  const getMCPTools = useCallback(async (id: string): Promise<MCPTool[]> => {
    const result = await fetchApi<MCPTool[]>(`/admin/mcps/${id}/tools`);
    return result || [];
  }, [fetchApi]);

  // MCP Templates
  const listMCPTemplates = useCallback(async (): Promise<MCPTemplate[]> => {
    const result = await fetchApi<{ templates: MCPTemplate[] }>('/admin/mcp-templates');
    return result?.templates || [];
  }, [fetchApi]);

  const createFromTemplate = useCallback(async (templateName: string, name: string, variables: Record<string, any>): Promise<MCPServer | null> => {
    return await fetchApi<MCPServer>(`/admin/mcp-templates/${templateName}`, {
      method: 'POST',
      body: JSON.stringify({ name, variables }),
    });
  }, [fetchApi]);

  // Permissions
  const grantMCPAccess = useCallback(async (agentId: string, data: MCPAccessGrant): Promise<boolean> => {
    const result = await fetchApi<{ message: string }>(`/admin/agents/${agentId}/mcps`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return result !== null;
  }, [fetchApi]);

  const revokeMCPAccess = useCallback(async (agentId: string, mcpId: string): Promise<boolean> => {
    const result = await fetchApi<{ message: string }>(`/admin/agents/${agentId}/mcps/${mcpId}`, {
      method: 'DELETE',
    });
    return result !== null;
  }, [fetchApi]);

  const getAgentMCPs = useCallback(async (agentId: string): Promise<MCPServer[]> => {
    const result = await fetchApi<MCPServer[]>(`/admin/agents/${agentId}/mcps`);
    return result || [];
  }, [fetchApi]);

  const updateMCPPermissions = useCallback(async (agentId: string, mcpId: string, data: MCPAccessUpdate): Promise<boolean> => {
    const result = await fetchApi<{ message: string }>(`/admin/agents/${agentId}/mcps/${mcpId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    return result !== null;
  }, [fetchApi]);

  const getPermissionMatrix = useCallback(async (): Promise<PermissionMatrix | null> => {
    return await fetchApi<PermissionMatrix>('/admin/permissions/matrix');
  }, [fetchApi]);

  // Agent Groups
  const listAgentGroups = useCallback(async (): Promise<AgentGroup[]> => {
    const result = await fetchApi<AgentGroup[]>('/admin/groups');
    return result || [];
  }, [fetchApi]);

  const getAgentGroup = useCallback(async (id: string): Promise<AgentGroupWithMembers | null> => {
    return await fetchApi<AgentGroupWithMembers>(`/admin/groups/${id}`);
  }, [fetchApi]);

  const createAgentGroup = useCallback(async (data: AgentGroupCreate): Promise<AgentGroup | null> => {
    return await fetchApi<AgentGroup>('/admin/groups', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }, [fetchApi]);

  const deleteAgentGroup = useCallback(async (id: string): Promise<boolean> => {
    const result = await fetchApi<{ message: string }>(`/admin/groups/${id}`, {
      method: 'DELETE',
    });
    return result !== null;
  }, [fetchApi]);

  const addAgentToGroup = useCallback(async (groupId: string, agentId: string): Promise<boolean> => {
    const result = await fetchApi<{ message: string }>(`/admin/groups/${groupId}/agents/${agentId}`, {
      method: 'POST',
    });
    return result !== null;
  }, [fetchApi]);

  const removeAgentFromGroup = useCallback(async (groupId: string, agentId: string): Promise<boolean> => {
    const result = await fetchApi<{ message: string }>(`/admin/groups/${groupId}/agents/${agentId}`, {
      method: 'DELETE',
    });
    return result !== null;
  }, [fetchApi]);

  return {
    loading,
    error,
    // Agents
    listAgents,
    getAgent,
    createAgent,
    updateAgent,
    deleteAgent,
    // MCP Servers
    listMCPServers,
    getMCPServer,
    createMCPServer,
    updateMCPServer,
    deleteMCPServer,
    testMCPConnection,
    getMCPTools,
    // Templates
    listMCPTemplates,
    createFromTemplate,
    // Permissions
    grantMCPAccess,
    revokeMCPAccess,
    getAgentMCPs,
    updateMCPPermissions,
    getPermissionMatrix,
    // Groups
    listAgentGroups,
    getAgentGroup,
    createAgentGroup,
    deleteAgentGroup,
    addAgentToGroup,
    removeAgentFromGroup,
  };
}

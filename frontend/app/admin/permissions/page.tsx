'use client';

import { useState, useEffect } from 'react';
import { useAdminApi } from '@/hooks/useAdminApi';
import { PermissionMatrix, MCPServer, Agent } from '@/types/admin';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

export default function PermissionsPage() {
  const { getPermissionMatrix, grantMCPAccess, revokeMCPAccess, updateMCPPermissions, listAgents, listMCPServers } = useAdminApi();
  const [matrix, setMatrix] = useState<PermissionMatrix | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [mcps, setMcps] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCell, setSelectedCell] = useState<{
    agentId: string;
    mcpId: string;
    tools: string[];
    allowedTools: string[];
  } | null>(null);

  const loadData = async () => {
    setLoading(true);
    const [matrixData, agentsData, mcpsData] = await Promise.all([
      getPermissionMatrix(),
      listAgents(),
      listMCPServers(),
    ]);
    setMatrix(matrixData);
    setAgents(agentsData);
    setMcps(mcpsData);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggleAccess = async (agentId: string, mcpId: string, hasAccess: boolean) => {
    if (hasAccess) {
      await revokeMCPAccess(agentId, mcpId);
    } else {
      await grantMCPAccess(agentId, { mcp_id: mcpId });
    }
    loadData();
  };

  const handleEditTools = (agentId: string, mcpId: string, tools: string[], allowedTools?: string[]) => {
    setSelectedCell({
      agentId,
      mcpId,
      tools,
      allowedTools: allowedTools || [],
    });
  };

  const handleSaveTools = async (allowedTools: string[]) => {
    if (!selectedCell) return;

    await updateMCPPermissions(selectedCell.agentId, selectedCell.mcpId, {
      allowed_tools: allowedTools.length > 0 ? allowedTools : undefined,
    });
    setSelectedCell(null);
    loadData();
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="text-center py-12">
          <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-body-md text-on-surface-variant">Loading permissions...</p>
        </div>
      </div>
    );
  }

  if (agents.length === 0 || mcps.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-8">
        <h1 className="text-headline-lg text-on-surface mb-8">Permissions</h1>
        <div className="text-center py-12 bg-surface-container rounded-2xl">
          <span className="text-4xl mb-4 block">🔐</span>
          <h3 className="text-headline-sm text-on-surface mb-2">No Data Available</h3>
          <p className="text-body-md text-on-surface-variant mb-4">
            {agents.length === 0
              ? 'Create some agents first to manage permissions'
              : 'Add MCP servers first to configure permissions'}
          </p>
          <Button onClick={() => window.location.href = agents.length === 0 ? '/admin/agents' : '/admin/mcps'}>
            Go to {agents.length === 0 ? 'Agents' : 'MCP Servers'}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-headline-lg text-on-surface">Permissions</h1>
            <p className="text-body-md text-on-surface-variant mt-1">
              Manage which agents can access which MCP servers
            </p>
          </div>
        </div>

        {/* Permission Matrix */}
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-container">
                  <th className="text-left px-6 py-4 text-label-md font-semibold text-on-surface sticky left-0 bg-surface-container z-10">
                    Agent / MCP
                  </th>
                  {mcps.map((mcp) => (
                    <th
                      key={mcp.id}
                      className="text-center px-4 py-4 text-label-sm font-medium text-on-surface min-w-[120px]"
                    >
                      <div className="flex flex-col items-center">
                        <span className="font-semibold">{mcp.name}</span>
                        <span className="text-label-xs text-on-surface-variant capitalize">
                          {mcp.transport}
                        </span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {agents.map((agent) => (
                  <tr key={agent.id} className="hover:bg-surface-container/50">
                    <td className="px-6 py-4 sticky left-0 bg-background z-10">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-primary-container flex items-center justify-center text-on-primary font-semibold text-sm">
                          {agent.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <p className="text-label-md font-medium text-on-surface">
                            {agent.name}
                          </p>
                          <p className="text-label-xs text-on-surface-variant">
                            {agent.model}
                          </p>
                        </div>
                      </div>
                    </td>
                    {mcps.map((mcp) => {
                      const permission = matrix?.permissions.find(
                        (p) => p.agent_id === agent.id && p.mcp_id === mcp.id
                      );
                      const hasAccess = permission?.has_access || false;
                      const allTools = permission?.all_tools || [];
                      const allowedTools = permission?.allowed_tools;

                      return (
                        <td key={mcp.id} className="px-4 py-4 text-center">
                          <div className="flex flex-col items-center gap-2">
                            <button
                              onClick={() => handleToggleAccess(agent.id, mcp.id, hasAccess)}
                              className={`w-12 h-6 rounded-full transition-colors relative ${
                                hasAccess ? 'bg-primary' : 'bg-outline-variant'
                              }`}
                            >
                              <span
                                className={`absolute top-1 w-4 h-4 rounded-full bg-on-primary transition-transform ${
                                  hasAccess ? 'left-7' : 'left-1'
                                }`}
                              />
                            </button>
                            {hasAccess && allTools.length > 0 && (
                              <button
                                onClick={() => handleEditTools(agent.id, mcp.id, allTools, allowedTools)}
                                className="text-label-xs text-primary hover:underline"
                              >
                                {allowedTools
                                  ? `${allowedTools.length}/${allTools.length} tools`
                                  : 'All tools'}
                              </button>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Legend */}
        <div className="mt-6 flex items-center gap-6 text-label-sm text-on-surface-variant">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-primary" />
            <span>Access granted</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-outline-variant" />
            <span>No access</span>
          </div>
          <p className="ml-auto">
            Click on any cell to toggle access. Click "X tools" to configure specific tools.
          </p>
        </div>
      </div>

      {/* Tool Selection Modal */}
      {selectedCell && (
        <ToolSelectionModal
          tools={selectedCell.tools}
          allowedTools={selectedCell.allowedTools}
          onSave={handleSaveTools}
          onClose={() => setSelectedCell(null)}
        />
      )}
    </>
  );
}

interface ToolSelectionModalProps {
  tools: string[];
  allowedTools: string[];
  onSave: (allowedTools: string[]) => void;
  onClose: () => void;
}

function ToolSelectionModal({ tools, allowedTools, onSave, onClose }: ToolSelectionModalProps) {
  const [selected, setSelected] = useState<string[]>(allowedTools);

  const toggleTool = (tool: string) => {
    setSelected((prev) =>
      prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool]
    );
  };

  const handleSelectAll = () => {
    setSelected(selected.length === tools.length ? [] : [...tools]);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-surface-container-high rounded-2xl w-full max-w-md mx-4 p-6">
        <h3 className="text-headline-sm text-on-surface mb-4">Select Allowed Tools</h3>
        <p className="text-body-md text-on-surface-variant mb-4">
          Leave empty to allow all tools
        </p>

        <div className="mb-4">
          <button
            onClick={handleSelectAll}
            className="text-label-md text-primary hover:underline"
          >
            {selected.length === tools.length ? 'Deselect all' : 'Select all'}
          </button>
        </div>

        <div className="space-y-2 max-h-64 overflow-y-auto mb-6">
          {tools.map((tool) => (
            <label
              key={tool}
              className="flex items-center gap-3 p-3 bg-surface-container rounded-lg cursor-pointer hover:bg-surface-container-high"
            >
              <input
                type="checkbox"
                checked={selected.includes(tool)}
                onChange={() => toggleTool(tool)}
                className="w-5 h-5 rounded border-outline-variant text-primary focus:ring-primary"
              />
              <span className="text-label-md text-on-surface">{tool}</span>
            </label>
          ))}
        </div>

        <div className="flex gap-3">
          <Button onClick={onClose} variant="secondary" className="flex-1">
            Cancel
          </Button>
          <Button onClick={() => onSave(selected)} variant="primary" className="flex-1">
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}

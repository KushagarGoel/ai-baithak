'use client';

import { useState, useEffect } from 'react';
import { useAdminApi } from '@/hooks/useAdminApi';
import { MCPServerWithStatus } from '@/types/admin';
import { MCPCard } from '@/components/admin/MCPCard';
import { MCPFormModal } from '@/components/admin/MCPFormModal';
import { Button } from '@/components/ui/Button';

export default function MCPServersPage() {
  const { listMCPServers, deleteMCPServer, testMCPConnection, loading } = useAdminApi();
  const [servers, setServers] = useState<MCPServerWithStatus[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingServer, setEditingServer] = useState<MCPServerWithStatus | null>(null);

  const loadServers = async () => {
    const data = await listMCPServers();
    setServers(data);
  };

  useEffect(() => {
    loadServers();
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this MCP server?')) return;
    const success = await deleteMCPServer(id);
    if (success) {
      loadServers();
    }
  };

  const handleTest = async (id: string) => {
    const result = await testMCPConnection(id);
    alert(result.message);
    loadServers();
  };

  const handleEdit = (server: MCPServerWithStatus) => {
    setEditingServer(server);
    setShowForm(true);
  };

  const handleAdd = () => {
    setEditingServer(null);
    setShowForm(true);
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingServer(null);
    loadServers();
  };

  return (
    <>
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-headline-lg text-on-surface">MCP Servers</h1>
            <p className="text-body-md text-on-surface-variant mt-1">
              Manage your Model Context Protocol servers
            </p>
          </div>
          <Button onClick={handleAdd} variant="primary">
            <span className="mr-2">+</span>
            Add MCP Server
          </Button>
        </div>

        {/* Servers Grid */}
        {loading && servers.length === 0 ? (
          <div className="text-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-body-md text-on-surface-variant">Loading servers...</p>
          </div>
        ) : servers.length === 0 ? (
          <div className="text-center py-12 bg-surface-container rounded-2xl">
            <span className="text-4xl mb-4 block">🔌</span>
            <h3 className="text-headline-sm text-on-surface mb-2">No MCP Servers</h3>
            <p className="text-body-md text-on-surface-variant mb-4">
              Add your first MCP server to enable tools for your agents
            </p>
            <Button onClick={handleAdd} variant="primary">
              Add MCP Server
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {servers.map((server) => (
              <MCPCard
                key={server.id}
                server={server}
                onEdit={() => handleEdit(server)}
                onDelete={() => handleDelete(server.id)}
                onTest={() => handleTest(server.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Form Modal */}
      {showForm && (
        <MCPFormModal
          server={editingServer}
          onClose={handleFormClose}
        />
      )}
    </>
  );
}

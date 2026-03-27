'use client';

import { useState, useEffect } from 'react';
import { useAdminApi } from '@/hooks/useAdminApi';
import { Agent } from '@/types/admin';
import { AgentCard } from '@/components/admin/AgentCard';
import { AgentFormModal } from '@/components/admin/AgentFormModal';
import { Button } from '@/components/ui/Button';

export default function AgentsPage() {
  const { listAgents, deleteAgent, loading } = useAdminApi();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

  const loadAgents = async () => {
    const data = await listAgents();
    setAgents(data);
  };

  useEffect(() => {
    loadAgents();
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this agent?')) return;
    const success = await deleteAgent(id);
    if (success) {
      loadAgents();
    }
  };

  const handleEdit = (agent: Agent) => {
    setEditingAgent(agent);
    setShowForm(true);
  };

  const handleAdd = () => {
    setEditingAgent(null);
    setShowForm(true);
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingAgent(null);
    loadAgents();
  };

  return (
    <>
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-headline-lg text-on-surface">Agents</h1>
            <p className="text-body-md text-on-surface-variant mt-1">
              Manage your council members and their capabilities
            </p>
          </div>
          <Button onClick={handleAdd} variant="primary">
            <span className="mr-2">+</span>
            Add Agent
          </Button>
        </div>

        {/* Agents Grid */}
        {loading && agents.length === 0 ? (
          <div className="text-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-body-md text-on-surface-variant">Loading agents...</p>
          </div>
        ) : agents.length === 0 ? (
          <div className="text-center py-12 bg-surface-container rounded-2xl">
            <span className="text-4xl mb-4 block">🤖</span>
            <h3 className="text-headline-sm text-on-surface mb-2">No Agents</h3>
            <p className="text-body-md text-on-surface-variant mb-4">
              Create your first agent to participate in council discussions
            </p>
            <Button onClick={handleAdd} variant="primary">
              Add Agent
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onEdit={() => handleEdit(agent)}
                onDelete={() => handleDelete(agent.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Form Modal */}
      {showForm && (
        <AgentFormModal
          agent={editingAgent}
          onClose={handleFormClose}
        />
      )}
    </>
  );
}

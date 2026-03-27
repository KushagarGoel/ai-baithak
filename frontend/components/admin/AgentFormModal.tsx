'use client';

import { useState, useEffect } from 'react';
import { useAdminApi } from '@/hooks/useAdminApi';
import { Agent, MCPServer } from '@/types/admin';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

interface AgentFormModalProps {
  agent: Agent | null;
  onClose: () => void;
}

export function AgentFormModal({ agent, onClose }: AgentFormModalProps) {
  const { createAgent, updateAgent, listMCPServers, getAgentMCPs, grantMCPAccess, revokeMCPAccess } = useAdminApi();
  const [mcps, setMcps] = useState<MCPServer[]>([]);
  const [agentMCPs, setAgentMCPs] = useState<string[]>([]);

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    system_prompt: '',
    model: 'openai/gpt-4o-mini',
    temperature: 0.7,
    max_tokens: 2000,
    speak_probability: 1.0,
    avatar_url: '',
  });

  useEffect(() => {
    if (agent) {
      setFormData({
        name: agent.name,
        description: agent.description || '',
        system_prompt: agent.system_prompt,
        model: agent.model,
        temperature: agent.temperature,
        max_tokens: agent.max_tokens,
        speak_probability: agent.speak_probability,
        avatar_url: agent.avatar_url || '',
      });
      loadAgentMCPs(agent.id);
    }
    loadMCPs();
  }, [agent]);

  const loadMCPs = async () => {
    const data = await listMCPServers();
    setMcps(data);
  };

  const loadAgentMCPs = async (agentId: string) => {
    const data = await getAgentMCPs(agentId);
    setAgentMCPs(data.map(m => m.id));
  };

  const handleMCPChange = async (mcpId: string, checked: boolean) => {
    if (!agent) return;

    if (checked) {
      await grantMCPAccess(agent.id, { mcp_id: mcpId });
    } else {
      await revokeMCPAccess(agent.id, mcpId);
    }
    loadAgentMCPs(agent.id);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const data = {
      ...formData,
      description: formData.description || undefined,
      avatar_url: formData.avatar_url || undefined,
    };

    if (agent) {
      await updateAgent(agent.id, data);
    } else {
      await createAgent(data);
    }
    onClose();
  };

  return (
    <Modal
      title={agent ? 'Edit Agent' : 'Add Agent'}
      onClose={onClose}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          {/* Name */}
          <Input
            label="Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., The Researcher"
            required
          />

          {/* Model */}
          <Input
            label="Model"
            value={formData.model}
            onChange={(e) => setFormData({ ...formData, model: e.target.value })}
            placeholder="e.g., openai/gpt-4o-mini"
            required
          />
        </div>

        {/* Description */}
        <Input
          label="Description"
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          placeholder="Brief description of this agent's role"
        />

        {/* System Prompt */}
        <div>
          <label className="block text-label-md text-on-surface mb-2">
            System Prompt <span className="text-error">*</span>
          </label>
          <textarea
            value={formData.system_prompt}
            onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
            placeholder="You are a helpful assistant..."
            rows={6}
            className="w-full px-4 py-3 bg-surface-container rounded-xl border border-outline-variant/20 text-on-surface focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            required
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          {/* Temperature */}
          <div>
            <label className="block text-label-md text-on-surface mb-2">
              Temperature: {formData.temperature}
            </label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={formData.temperature}
              onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>

          {/* Max Tokens */}
          <Input
            label="Max Tokens"
            type="number"
            value={formData.max_tokens}
            onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) })}
            min="100"
            max="8000"
            required
          />

          {/* Speak Probability */}
          <div>
            <label className="block text-label-md text-on-surface mb-2">
              Speak %: {Math.round(formData.speak_probability * 100)}%
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={formData.speak_probability}
              onChange={(e) => setFormData({ ...formData, speak_probability: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>
        </div>

        {/* Avatar URL */}
        <Input
          label="Avatar URL (optional)"
          value={formData.avatar_url}
          onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })}
          placeholder="https://example.com/avatar.png"
        />

        {/* MCP Access (only for editing) */}
        {agent && mcps.length > 0 && (
          <div className="border-t border-outline-variant/20 pt-6">
            <h4 className="text-headline-sm text-on-surface mb-4">MCP Access</h4>
            <div className="space-y-2">
              {mcps.map((mcp) => (
                <label
                  key={mcp.id}
                  className="flex items-center gap-3 p-3 bg-surface-container rounded-lg cursor-pointer hover:bg-surface-container-high"
                >
                  <input
                    type="checkbox"
                    checked={agentMCPs.includes(mcp.id)}
                    onChange={(e) => handleMCPChange(mcp.id, e.target.checked)}
                    className="w-5 h-5 rounded border-outline-variant text-primary focus:ring-primary"
                  />
                  <div className="flex-1">
                    <p className="text-label-md text-on-surface font-medium">{mcp.name}</p>
                    <p className="text-label-sm text-on-surface-variant">{mcp.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t border-outline-variant/20">
          <Button type="button" variant="secondary" onClick={onClose} className="flex-1">
            Cancel
          </Button>
          <Button type="submit" variant="primary" className="flex-1">
            {agent ? 'Update' : 'Create'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

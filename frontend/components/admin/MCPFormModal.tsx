'use client';

import { useState, useEffect } from 'react';
import { useAdminApi } from '@/hooks/useAdminApi';
import { MCPServerWithStatus, MCPTemplate } from '@/types/admin';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';

interface MCPFormModalProps {
  server: MCPServerWithStatus | null;
  onClose: () => void;
}

export function MCPFormModal({ server, onClose }: MCPFormModalProps) {
  const { createMCPServer, updateMCPServer, listMCPTemplates } = useAdminApi();
  const [templates, setTemplates] = useState<MCPTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    transport: 'stdio' as 'stdio' | 'sse' | 'websocket',
    config: '{}',
  });

  useEffect(() => {
    if (server) {
      setFormData({
        name: server.name,
        description: server.description || '',
        transport: server.transport,
        config: JSON.stringify(server.config, null, 2),
      });
    }
  }, [server]);

  useEffect(() => {
    listMCPTemplates().then(setTemplates);
  }, []);

  const handleTemplateSelect = (templateName: string) => {
    setSelectedTemplate(templateName);
    const template = templates.find(t => t.name === templateName);
    if (template) {
      setFormData(prev => ({
        ...prev,
        transport: template.transport as 'stdio' | 'sse' | 'websocket',
        config: JSON.stringify(template.config, null, 2),
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const config = JSON.parse(formData.config);
      const data = {
        name: formData.name,
        description: formData.description || undefined,
        transport: formData.transport,
        config,
      };

      if (server) {
        await updateMCPServer(server.id, data);
      } else {
        await createMCPServer(data);
      }
      onClose();
    } catch (err) {
      alert('Invalid JSON in config field');
    }
  };

  return (
    <Modal
      title={server ? 'Edit MCP Server' : 'Add MCP Server'}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Template Selection (only for new servers) */}
        {!server && (
          <div>
            <label className="block text-label-md text-on-surface mb-2">
              Template (Optional)
            </label>
            <select
              value={selectedTemplate}
              onChange={(e) => handleTemplateSelect(e.target.value)}
              className="w-full px-4 py-3 bg-surface-container rounded-xl border border-outline-variant/20 text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">Custom Configuration</option>
              {templates.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name} - {t.description}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Name */}
        <Input
          label="Name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="e.g., filesystem, github"
          required
        />

        {/* Description */}
        <Input
          label="Description"
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          placeholder="Brief description of this MCP server"
        />

        {/* Transport */}
        <div>
          <label className="block text-label-md text-on-surface mb-2">
            Transport
          </label>
          <div className="flex gap-2">
            {(['stdio', 'sse', 'websocket'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setFormData({ ...formData, transport: t })}
                className={`px-4 py-2 rounded-lg text-label-md font-medium transition-all ${
                  formData.transport === t
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                }`}
              >
                {t.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Config */}
        <div>
          <label className="block text-label-md text-on-surface mb-2">
            Configuration (JSON)
          </label>
          <textarea
            value={formData.config}
            onChange={(e) => setFormData({ ...formData, config: e.target.value })}
            placeholder={`{\n  "command": "npx",\n  "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]\n}`}
            rows={8}
            className="w-full px-4 py-3 bg-surface-container rounded-xl border border-outline-variant/20 text-on-surface font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            required
          />
          <p className="text-label-sm text-on-surface-variant mt-2">
            {formData.transport === 'stdio' && 'Requires: command, args, env (optional)'}
            {formData.transport === 'sse' && 'Requires: url, headers (optional)'}
            {formData.transport === 'websocket' && 'Requires: url, protocols (optional)'}
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4">
          <Button type="button" variant="secondary" onClick={onClose} className="flex-1">
            Cancel
          </Button>
          <Button type="submit" variant="primary" className="flex-1">
            {server ? 'Update' : 'Create'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

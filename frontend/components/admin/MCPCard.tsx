'use client';

import { MCPServerWithStatus } from '@/types/admin';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

interface MCPCardProps {
  server: MCPServerWithStatus;
  onEdit: () => void;
  onDelete: () => void;
  onTest: () => void;
}

export function MCPCard({ server, onEdit, onDelete, onTest }: MCPCardProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-success';
      case 'offline':
        return 'bg-outline-variant';
      case 'error':
        return 'bg-error';
      default:
        return 'bg-outline-variant';
    }
  };

  const getTransportIcon = (transport: string) => {
    switch (transport) {
      case 'stdio':
        return '💻';
      case 'sse':
        return '🌐';
      case 'websocket':
        return '🔌';
      default:
        return '📦';
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-surface-container-high flex items-center justify-center text-2xl">
            {getTransportIcon(server.transport)}
          </div>
          <div>
            <h3 className="text-headline-sm text-on-surface font-semibold">
              {server.name}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <span className={`w-2 h-2 rounded-full ${getStatusColor(server.status)}`} />
              <span className="text-label-sm text-on-surface-variant capitalize">
                {server.status}
              </span>
              <span className="text-label-sm text-outline">•</span>
              <span className="text-label-sm text-on-surface-variant uppercase">
                {server.transport}
              </span>
            </div>
          </div>
        </div>
      </div>

      {server.description && (
        <p className="text-body-md text-on-surface-variant mb-4 line-clamp-2">
          {server.description}
        </p>
      )}

      <div className="flex items-center gap-4 mb-4 text-label-sm text-on-surface-variant">
        <div className="flex items-center gap-1">
          <span>🛠️</span>
          <span>{server.tool_count} tools</span>
        </div>
      </div>

      {server.last_error && (
        <div className="mb-4 p-3 bg-error/10 rounded-lg">
          <p className="text-label-sm text-error">
            {server.last_error}
          </p>
        </div>
      )}

      <div className="flex gap-2">
        <Button onClick={onTest} variant="secondary" className="flex-1" size="sm">
          Test
        </Button>
        <Button onClick={onEdit} variant="secondary" className="flex-1" size="sm">
          Edit
        </Button>
        <Button onClick={onDelete} variant="danger" size="sm">
          🗑️
        </Button>
      </div>
    </Card>
  );
}

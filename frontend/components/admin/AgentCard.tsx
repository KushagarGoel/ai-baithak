'use client';

import { Agent } from '@/types/admin';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

interface AgentCardProps {
  agent: Agent;
  onEdit: () => void;
  onDelete: () => void;
}

export function AgentCard({ agent, onEdit, onDelete }: AgentCardProps) {
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <Card variant="elevated" className="p-6 group hover:shadow-ambient transition-shadow duration-300">
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-4">
          {agent.avatar_url ? (
            <img
              src={agent.avatar_url}
              alt={agent.name}
              className="w-14 h-14 rounded-2xl object-cover ring-2 ring-outline-variant/20"
            />
          ) : (
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-surface-container-high to-surface-container-highest ring-2 ring-outline-variant/30 flex items-center justify-center">
              <span className="text-xl font-bold bg-gradient-to-br from-primary to-tertiary bg-clip-text text-transparent">
                {getInitials(agent.name)}
              </span>
            </div>
          )}
          <div>
            <h3 className="text-headline-sm text-on-surface font-semibold tracking-tight">
              {agent.name}
            </h3>
            <div className="flex items-center gap-2 mt-1.5">
              <span className="text-label-sm text-on-surface-variant/80 font-mono">
                {agent.model.split('/').pop()}
              </span>
              {!agent.is_active && (
                <span className="px-2 py-0.5 bg-outline-variant/10 rounded-full text-label-xs text-on-surface-variant/60 border border-outline-variant/20">
                  Inactive
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {agent.description && (
        <p className="text-body-md text-on-surface-variant/80 mb-5 line-clamp-2 leading-relaxed">
          {agent.description}
        </p>
      )}

      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-surface-container-low/50 rounded-xl p-3 border border-outline-variant/10">
          <p className="text-label-xs text-on-surface-variant/60 uppercase tracking-wider mb-1">Temp</p>
          <p className="text-title-md font-semibold text-on-surface">{agent.temperature}</p>
        </div>
        <div className="bg-surface-container-low/50 rounded-xl p-3 border border-outline-variant/10">
          <p className="text-label-xs text-on-surface-variant/60 uppercase tracking-wider mb-1">Tokens</p>
          <p className="text-title-md font-semibold text-on-surface">{agent.max_tokens}</p>
        </div>
        <div className="bg-surface-container-low/50 rounded-xl p-3 border border-outline-variant/10">
          <p className="text-label-xs text-on-surface-variant/60 uppercase tracking-wider mb-1">Speak</p>
          <p className="text-title-md font-semibold text-on-surface">
            {Math.round(agent.speak_probability * 100)}%
          </p>
        </div>
      </div>

      <div className="flex gap-3">
        <Button onClick={onEdit} variant="secondary" className="flex-1" size="sm">
          <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          Edit
        </Button>
        <Button onClick={onDelete} variant="danger" size="sm" className="px-3">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </Button>
      </div>
    </Card>
  );
}

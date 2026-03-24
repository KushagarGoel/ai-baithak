'use client';

import { DiscussionTurn, PERSONA_COLORS } from '@/types';
import { formatTimestamp } from '@/lib/utils';
import { Card } from '@/components/ui/Card';

interface MessageCardProps {
  turn: DiscussionTurn;
}

export function MessageCard({ turn }: MessageCardProps) {
  const isOrchestrator = turn.agent_name === 'Orchestrator';
  const isUser = turn.agent_name === 'You';

  const colors = PERSONA_COLORS[turn.persona.toLowerCase().replace(/\s+/g, '_')] ||
    (isOrchestrator ? PERSONA_COLORS.the_orchestrator : PERSONA_COLORS.the_pragmatist);

  return (
    <Card
      variant="default"
      padding="md"
      className="animate-fade-in"
      style={{
        background: colors.bg,
        borderLeft: `4px solid ${colors.border}`,
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center text-label-sm font-medium"
            style={{
              background: colors.border,
              color: '#0b0e14',
            }}
          >
            {turn.agent_name.charAt(0)}
          </div>
          <div>
            <span className="text-label-md font-medium text-on-surface">
              {turn.agent_name}
            </span>
            {!isUser && (
              <span
                className="ml-2 px-2 py-0.5 rounded-full text-label-sm"
                style={{
                  background: `${colors.border}30`,
                  color: colors.border,
                }}
              >
                {turn.persona}
              </span>
            )}
          </div>
        </div>
        <span className="text-label-sm text-on-surface-variant">
          {formatTimestamp(turn.timestamp)}
        </span>
      </div>

      {/* Content */}
      <div className="text-body-md text-on-surface whitespace-pre-wrap leading-relaxed">
        {turn.content}
      </div>

      {/* Tool calls */}
      {turn.tool_calls && turn.tool_calls.length > 0 && (
        <div className="mt-4 p-3 bg-surface-container-lowest rounded-lg">
          <p className="text-label-sm text-on-surface-variant mb-2">Tool Calls:</p>
          {turn.tool_calls.map((call, idx) => (
            <div key={idx} className="font-mono text-label-sm text-primary">
              {call.name}({JSON.stringify(call.arguments)})
            </div>
          ))}
        </div>
      )}

      {/* Tool results */}
      {turn.tool_results && turn.tool_results.length > 0 && (
        <div className="mt-2 p-3 bg-surface-container-lowest rounded-lg">
          <p className="text-label-sm text-on-surface-variant mb-2">Results:</p>
          {turn.tool_results.map((result, idx) => (
            <div key={idx} className="font-mono text-label-sm">
              <span className={result.success ? 'text-secondary' : 'text-error'}>
                {result.success ? '✓' : '✗'} {result.tool}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Segment indicator */}
      {turn.segment > 0 && (
        <div className="mt-3 pt-3 border-t border-outline-variant/10">
          <span className="text-label-xs text-on-surface-variant/60">
            Segment {turn.segment + 1}
          </span>
        </div>
      )}
    </Card>
  );
}

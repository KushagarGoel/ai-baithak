'use client';

import { useCouncilStore } from '@/stores/councilStore';
import { formatTokens } from '@/lib/utils';
import { ProgressRing } from '@/components/ui/ProgressRing';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

export function Sidebar() {
  const { config, orchestratorState } = useCouncilStore();

  const progress = orchestratorState.max_turns > 0
    ? orchestratorState.current_turn / orchestratorState.max_turns
    : 0;

  return (
    <aside className="w-80 bg-surface-container-low border-r border-outline-variant/10 flex flex-col">
      {/* Progress Section */}
      <div className="p-6 border-b border-outline-variant/10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-headline-sm text-on-surface">Progress</h2>
          <ProgressRing
            progress={progress}
            size={50}
            strokeWidth={3}
            color="primary"
          />
        </div>

        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-body-md text-on-surface-variant">Current Turn</span>
            <span className="text-label-lg font-medium text-on-surface">
              {orchestratorState.current_turn}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-body-md text-on-surface-variant">Max Turns</span>
            <span className="text-label-lg font-medium text-on-surface">
              {orchestratorState.max_turns}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-body-md text-on-surface-variant">Segment</span>
            <span className="text-label-lg font-medium text-on-surface">
              {orchestratorState.current_segment + 1} / {orchestratorState.total_segments}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-body-md text-on-surface-variant">Tokens</span>
            <span className="text-label-lg font-medium text-primary">
              {formatTokens(orchestratorState.total_tokens)}
            </span>
          </div>
        </div>
      </div>

      {/* Agents Section */}
      <div className="p-6 flex-1 overflow-y-auto">
        <h2 className="text-headline-sm text-on-surface mb-4">Council Members</h2>
        <div className="space-y-3">
          {config.agents.map((agent, index) => (
            <Card key={index} variant="default" padding="sm" className="group">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-label-md font-medium"
                  style={{
                    background: `linear-gradient(135deg, var(--primary-dim), var(--primary-container))`,
                    color: 'var(--on-primary)',
                  }}
                >
                  {agent.name.charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-label-md font-medium text-on-surface truncate">
                    {agent.name}
                  </p>
                  <p className="text-label-sm text-on-surface-variant truncate">
                    {agent.model}
                  </p>
                </div>
                {orchestratorState.current_agent === agent.name && (
                  <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
                )}
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Topic Section */}
      {config.topic && (
        <div className="p-6 border-t border-outline-variant/10">
          <h2 className="text-headline-sm text-on-surface mb-2">Topic</h2>
          <p className="text-body-md text-on-surface-variant line-clamp-3">
            {config.topic}
          </p>
        </div>
      )}
    </aside>
  );
}

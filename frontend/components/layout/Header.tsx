'use client';

import { useCouncilStore } from '@/stores/councilStore';
import { ViewMode } from '@/types';
import { cn } from '@/lib/utils';

const NAV_ITEMS: { label: string; mode: ViewMode; icon: string }[] = [
  { label: 'MCP Config', mode: 'config', icon: '⚙️' },
  { label: 'Sessions', mode: 'sessions', icon: '💬' },
  { label: 'Archives', mode: 'archives', icon: '📚' },
];

// Report is accessible from Sessions/Archives tabs, not main nav

export function Header() {
  const { viewMode, setViewMode, orchestratorState } = useCouncilStore();

  return (
    <header className="border-b border-outline-variant/10 bg-surface-container-low/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-container flex items-center justify-center shadow-glow-primary">
              <span className="text-xl">🏛️</span>
            </div>
            <div>
              <h1 className="text-headline-sm font-semibold text-on-surface">
                Agent Council
              </h1>
              <p className="text-label-sm text-on-surface-variant">
                AI Deliberation Platform
              </p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex items-center gap-1 bg-surface-container rounded-lg p-1">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.mode}
                onClick={() => setViewMode(item.mode)}
                className={cn(
                  'px-4 py-2 rounded-md text-label-md font-medium transition-all duration-200',
                  viewMode === item.mode
                    ? 'bg-surface-container-high text-primary shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                )}
              >
                <span className="mr-2">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>

          {/* Status */}
          <div className="flex items-center gap-4">
            {orchestratorState.is_running && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-secondary/10 rounded-full">
                <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
                <span className="text-label-sm text-secondary">
                  {orchestratorState.status === 'thinking' ? 'Thinking...' : 'Speaking'}
                </span>
              </div>
            )}
            <div className="text-right">
              <p className="text-label-sm text-on-surface-variant">
                {orchestratorState.current_turn}/{orchestratorState.max_turns} turns
              </p>
              <p className="text-label-xs text-on-surface-variant/60">
                Segment {orchestratorState.current_segment + 1}/{orchestratorState.total_segments}
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

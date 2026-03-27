'use client';

import { useState } from 'react';
import { useCouncilStore } from '@/stores/councilStore';
import { ViewMode } from '@/types';
import { cn } from '@/lib/utils';

const NAV_ITEMS: { label: string; mode: ViewMode; icon: string }[] = [
  { label: 'Configure', mode: 'config', icon: '⚙️' },
  { label: 'Sessions', mode: 'sessions', icon: '💬' },
  { label: 'Archives', mode: 'archives', icon: '📚' },
];

const ADMIN_ITEMS = [
  { label: 'MCP Servers', path: '/admin/mcps', icon: '🔌' },
  { label: 'Agents', path: '/admin/agents', icon: '🤖' },
  { label: 'Permissions', path: '/admin/permissions', icon: '🔐' },
];

// Report is accessible from Sessions/Archives tabs, not main nav

export function Header() {
  const { viewMode, setViewMode, orchestratorState } = useCouncilStore();
  const [adminOpen, setAdminOpen] = useState(false);

  return (
    <header className="border-b border-outline-variant/10 bg-surface-container/90 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-dim to-primary flex items-center justify-center shadow-glow-primary">
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

            {/* Admin Dropdown */}
            <div className="relative">
              <button
                onClick={() => setAdminOpen(!adminOpen)}
                onBlur={() => setTimeout(() => setAdminOpen(false), 200)}
                className={cn(
                  'px-4 py-2 rounded-md text-label-md font-medium transition-all duration-200 flex items-center',
                  adminOpen
                    ? 'bg-surface-container-high text-primary shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                )}
              >
                <span className="mr-2">🛠️</span>
                Admin
                <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {adminOpen && (
                <div className="absolute top-full right-0 mt-2 w-48 bg-surface-container-high rounded-lg shadow-lg border border-outline-variant/10 py-1">
                  {ADMIN_ITEMS.map((item) => (
                    <a
                      key={item.path}
                      href={item.path}
                      className="flex items-center px-4 py-2 text-label-md text-on-surface hover:bg-surface-container transition-colors"
                    >
                      <span className="mr-3">{item.icon}</span>
                      {item.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
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

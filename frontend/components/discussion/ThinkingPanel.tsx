'use client';

import { useState } from 'react';
import { DiscussionTurn, ToolCall, ToolResult } from '@/types';
import { cn } from '@/lib/utils';
import { ChevronDownIcon, ChevronRightIcon, LightBulbIcon, WrenchIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';

interface ThinkingPanelProps {
  turn: DiscussionTurn;
  className?: string;
}

export function ThinkingPanel({ turn, className }: ThinkingPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const hasThinking = !!turn.thinking;
  const hasTools = turn.tool_calls && turn.tool_calls.length > 0;

  if (!hasThinking && !hasTools) {
    return null;
  }

  return (
    <div className={cn('mt-3 border border-outline-variant/30 rounded-lg overflow-hidden', className)}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          'w-full flex items-center justify-between px-3 py-2 text-left',
          'bg-surface-container-high/50 hover:bg-surface-container-high transition-colors'
        )}
      >
        <div className="flex items-center gap-2">
          <LightBulbIcon className="w-4 h-4 text-primary" />
          <span className="text-label-sm text-on-surface-variant">
            {hasThinking ? 'Thinking' : 'Tools'}
            {hasTools && (
              <span className="ml-1 text-tertiary">
                ({turn.tool_calls.length} tool{turn.tool_calls.length !== 1 ? 's' : ''})
              </span>
            )}
          </span>
        </div>
        {isExpanded ? (
          <ChevronDownIcon className="w-4 h-4 text-on-surface-variant" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-on-surface-variant" />
        )}
      </button>

      {isExpanded && (
        <div className="px-3 py-2 bg-surface-container-lowest/50">
          {/* Thinking content */}
          {hasThinking && (
            <div className="mb-3">
              <h4 className="text-label-xs font-medium text-primary mb-1.5 uppercase tracking-wide">
                Reasoning Process
              </h4>
              <div className="text-body-sm text-on-surface-variant whitespace-pre-wrap leading-relaxed">
                {turn.thinking}
              </div>
            </div>
          )}

          {/* Tool calls */}
          {hasTools && (
            <div>
              <h4 className="text-label-xs font-medium text-tertiary mb-1.5 uppercase tracking-wide">
                Tool Calls
              </h4>
              <div className="space-y-2">
                {turn.tool_calls.map((tool, idx) => (
                  <ToolCallCard
                    key={idx}
                    tool={tool}
                    result={turn.tool_results?.[idx]}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ToolCallCardProps {
  tool: ToolCall;
  result?: ToolResult;
}

function ToolCallCard({ tool, result }: ToolCallCardProps) {
  const [showArgs, setShowArgs] = useState(false);
  const [showResult, setShowResult] = useState(false);

  return (
    <div className="border border-outline-variant/20 rounded-lg overflow-hidden bg-surface-container-low">
      {/* Tool header */}
      <div className="flex items-center justify-between px-3 py-2 bg-surface-container-high/50">
        <div className="flex items-center gap-2">
          <WrenchIcon className="w-4 h-4 text-tertiary" />
          <span className="text-label-sm font-medium text-on-surface">
            {tool.name}
          </span>
        </div>
        {result && (
          <div className="flex items-center gap-1">
            {result.success ? (
              <CheckCircleIcon className="w-4 h-4 text-success" />
            ) : (
              <XCircleIcon className="w-4 h-4 text-error" />
            )}
          </div>
        )}
      </div>

      {/* Arguments */}
      <div className="border-t border-outline-variant/10">
        <button
          onClick={() => setShowArgs(!showArgs)}
          className="w-full flex items-center justify-between px-3 py-1.5 text-left hover:bg-surface-container-high/30 transition-colors"
        >
          <span className="text-label-xs text-on-surface-variant">Arguments</span>
          {showArgs ? (
            <ChevronDownIcon className="w-3 h-3 text-on-surface-variant" />
          ) : (
            <ChevronRightIcon className="w-3 h-3 text-on-surface-variant" />
          )}
        </button>
        {showArgs && (
          <div className="px-3 pb-2">
            <pre className="text-label-xs text-on-surface-variant bg-surface-container-high/50 p-2 rounded overflow-x-auto">
              {JSON.stringify(tool.arguments, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Result */}
      {result && (
        <div className="border-t border-outline-variant/10">
          <button
            onClick={() => setShowResult(!showResult)}
            className="w-full flex items-center justify-between px-3 py-1.5 text-left hover:bg-surface-container-high/30 transition-colors"
          >
            <span className="text-label-xs text-on-surface-variant">
              Result {result.success ? '(Success)' : '(Error)'}
            </span>
            {showResult ? (
              <ChevronDownIcon className="w-3 h-3 text-on-surface-variant" />
            ) : (
              <ChevronRightIcon className="w-3 h-3 text-on-surface-variant" />
            )}
          </button>
          {showResult && (
            <div className="px-3 pb-2">
              {result.success ? (
                <pre className="text-label-xs text-on-surface-variant bg-success-container/30 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto">
                  {JSON.stringify(result.data, null, 2)}
                </pre>
              ) : (
                <div className="text-label-xs text-error bg-error-container/30 p-2 rounded">
                  {result.error}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

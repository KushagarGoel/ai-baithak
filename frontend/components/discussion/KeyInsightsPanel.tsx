'use client';

import { useState } from 'react';
import { KeyInsight } from '@/types';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { cn } from '@/lib/utils';
import { SparklesIcon, ChevronRightIcon, LightBulbIcon, XMarkIcon } from '@heroicons/react/24/outline';

interface KeyInsightsPanelProps {
  sessionId: string;
  insights: KeyInsight[];
  isOpen: boolean;
  onToggle: () => void;
  className?: string;
}

export function KeyInsightsPanel({ sessionId, insights, isOpen, onToggle, className }: KeyInsightsPanelProps) {
  const [selectedSegment, setSelectedSegment] = useState<number | 'all'>('all');

  // Get unique segments from insights
  const segments = Array.from(new Set(insights.map(i => i.segment))).sort((a, b) => a - b);

  // Filter insights by selected segment
  const filteredInsights = selectedSegment === 'all'
    ? insights
    : insights.filter(i => i.segment === selectedSegment);

  // Group insights by segment for display
  const groupedInsights = filteredInsights.reduce((acc, insight) => {
    if (!acc[insight.segment]) {
      acc[insight.segment] = [];
    }
    acc[insight.segment].push(insight);
    return acc;
  }, {} as Record<number, KeyInsight[]>);

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className={cn(
          'fixed right-4 top-24 z-40 flex items-center gap-2 px-4 py-3',
          'bg-primary-container text-on-primary-container rounded-xl shadow-ambient',
          'hover:bg-primary-container/90 transition-all duration-200',
          'border border-primary/20',
          className
        )}
      >
        <LightBulbIcon className="w-5 h-5" />
        <span className="text-label-md font-medium">Key Insights</span>
        {insights.length > 0 && (
          <span className="ml-1 px-2 py-0.5 bg-primary text-on-primary rounded-full text-label-xs">
            {insights.length}
          </span>
        )}
      </button>
    );
  }

  return (
    <div
      className={cn(
        'fixed right-4 top-24 bottom-24 z-40 w-96',
        'flex flex-col',
        className
      )}
    >
      <Card variant="elevated" className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <CardHeader className="flex flex-row items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-container flex items-center justify-center">
              <SparklesIcon className="w-5 h-5 text-primary" />
            </div>
            <div>
              <CardTitle>Key Insights</CardTitle>
              <p className="text-label-sm text-on-surface-variant mt-0.5">
                {insights.length} insights from discussion
              </p>
            </div>
          </div>
          <button
            onClick={onToggle}
            className="p-2 rounded-lg hover:bg-surface-container-high transition-colors"
          >
            <XMarkIcon className="w-5 h-5 text-on-surface-variant" />
          </button>
        </CardHeader>

        {/* Segment Filter */}
        {segments.length > 1 && (
          <div className="px-4 pb-3 shrink-0">
            <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-thin">
              <button
                onClick={() => setSelectedSegment('all')}
                className={cn(
                  'px-3 py-1.5 rounded-full text-label-sm whitespace-nowrap transition-colors',
                  selectedSegment === 'all'
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest'
                )}
              >
                All Segments
              </button>
              {segments.map(segment => (
                <button
                  key={segment}
                  onClick={() => setSelectedSegment(segment)}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-label-sm whitespace-nowrap transition-colors',
                    selectedSegment === segment
                      ? 'bg-primary text-on-primary'
                      : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest'
                  )}
                >
                  Segment {segment + 1}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Insights List */}
        <CardContent className="flex-1 overflow-y-auto scrollbar-thin">
          {filteredInsights.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-4">
              <LightBulbIcon className="w-12 h-12 text-on-surface-variant/30 mb-3" />
              <p className="text-body-md text-on-surface-variant">
                No insights yet.
              </p>
              <p className="text-label-sm text-on-surface-variant/70 mt-1">
                Insights will appear as the orchestrator analyzes the discussion.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {selectedSegment === 'all' ? (
                // Group by segment when showing all
                Object.entries(groupedInsights)
                  .sort(([a], [b]) => Number(a) - Number(b))
                  .map(([segment, segmentInsights]) => (
                    <div key={segment}>
                      <h4 className="text-label-sm font-medium text-primary mb-2 sticky top-0 bg-surface-container-high py-1 px-2 rounded-lg">
                        Segment {Number(segment) + 1}
                      </h4>
                      <div className="space-y-2">
                        {segmentInsights.map((insight) => (
                          <InsightCard key={insight.insight_number} insight={insight} />
                        ))}
                      </div>
                    </div>
                  ))
              ) : (
                // Show flat list when filtered
                filteredInsights.map((insight) => (
                  <InsightCard key={insight.insight_number} insight={insight} />
                ))
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

interface InsightCardProps {
  insight: KeyInsight;
}

function InsightCard({ insight }: InsightCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      className={cn(
        'group p-3 rounded-xl transition-all duration-200',
        'bg-surface-container-lowest border border-outline-variant/20',
        'hover:bg-surface-container-low hover:border-primary/30',
        isExpanded && 'bg-surface-container-low border-primary/30'
      )}
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-start gap-3 text-left"
      >
        <div className="w-6 h-6 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-label-xs font-bold text-primary">
            {insight.insight_number}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <p
            className="text-body-sm text-on-surface leading-relaxed"
            style={{
              display: '-webkit-box',
              WebkitLineClamp: isExpanded ? undefined : 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {insight.content}
          </p>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-label-xs text-on-surface-variant/70">
              Turn {Math.floor(insight.turn_number || 0)}
            </span>
            {insight.source === 'orchestrator' && (
              <span className="px-1.5 py-0.5 rounded bg-tertiary-container text-tertiary text-label-xs">
                Orchestrator
              </span>
            )}
          </div>
        </div>
        <ChevronRightIcon
          className={cn(
            'w-4 h-4 text-on-surface-variant transition-transform duration-200 shrink-0 mt-1',
            isExpanded && 'rotate-90'
          )}
        />
      </button>
    </div>
  );
}


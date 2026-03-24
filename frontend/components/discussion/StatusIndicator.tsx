'use client';

import { useEffect, useState } from 'react';

interface StatusIndicatorProps {
  status: string;
  currentAgent?: string;
  progressEvent?: {
    event: string;
    data: any;
  } | null;
}

export function StatusIndicator({ status, currentAgent, progressEvent }: StatusIndicatorProps) {
  const [dots, setDots] = useState('');
  const [currentTool, setCurrentTool] = useState<string | null>(null);

  // Animate dots
  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);
    return () => clearInterval(interval);
  }, []);

  // Track current tool from progress events
  useEffect(() => {
    if (progressEvent?.event === 'agent_tool_calls') {
      const calls = progressEvent.data?.calls || [];
      if (calls.length > 0) {
        setCurrentTool(calls[0].name);
      }
    } else if (progressEvent?.event === 'agent_tool_results') {
      setCurrentTool(null);
    }
  }, [progressEvent]);

  if (status === 'idle' || status === 'completed' || status === 'error') {
    return null;
  }

  const getStatusText = () => {
    switch (status) {
      case 'thinking':
        if (currentTool) {
          return `${currentAgent} is using tool: ${currentTool}${dots}`;
        }
        return `${currentAgent} is thinking${dots}`;
      case 'speaking':
        return `${currentAgent} is responding${dots}`;
      case 'orchestrating':
        return 'Orchestrator is analyzing discussion';
      default:
        return 'Processing';
    }
  };

  const getStatusIcon = () => {
    if (currentTool) {
      return (
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 bg-tertiary rounded-full animate-pulse" />
          <span className="w-2 h-2 bg-tertiary rounded-full animate-pulse delay-75" />
          <span className="w-2 h-2 bg-tertiary rounded-full animate-pulse delay-150" />
        </div>
      );
    }
    return (
      <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    );
  };

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-surface-container-high rounded-full">
      {getStatusIcon()}
      <span className="text-label-md text-on-surface-variant">
        {getStatusText()}
      </span>
    </div>
  );
}

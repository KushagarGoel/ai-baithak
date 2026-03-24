'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { useCouncilStore } from '@/stores/councilStore';
import { MessageCard } from './MessageCard';
import { Card } from '@/components/ui/Card';
import { Tabs, TabList, Tab, TabPanel } from '@/components/ui/Tabs';
import { StatusIndicator } from './StatusIndicator';
import { KeyInsightsPanel } from './KeyInsightsPanel';
import { DiscussionTurn } from '@/types';

interface ProgressEvent {
  event: string;
  data: any;
}

export function DiscussionPanel() {
  const {
    turns,
    segments,
    config,
    insights,
    addTurn,
    updateSegment,
    updateOrchestratorState,
    setSummary,
    addInsights,
    setInsights,
    orchestratorState,
  } = useCouncilStore();

  // Local state for connection status (not in global store to avoid re-render issues)
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');

  // Progress tracking for real-time status
  const [progressEvent, setProgressEvent] = useState<ProgressEvent | null>(null);
  const [currentStatus, setCurrentStatus] = useState<string>(orchestratorState.status);

  // Key insights panel state
  const [isInsightsOpen, setIsInsightsOpen] = useState(false);
  const [newInsightsCount, setNewInsightsCount] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const hasConnectedRef = useRef(false);

  // Group turns by segment
  const turnsBySegment = turns.reduce((acc, turn) => {
    const seg = turn.segment || 0;
    if (!acc[seg]) acc[seg] = [];
    acc[seg].push(turn);
    return acc;
  }, {} as Record<number, DiscussionTurn[]>);

  const sortedSegments = Object.keys(turnsBySegment)
    .map(Number)
    .sort((a, b) => a - b);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  // Fetch existing insights when loading a previous session
  useEffect(() => {
    const fetchInsights = async () => {
      if (!config.session_id) return;
      try {
        const response = await fetch(`http://localhost:11111/sessions/${config.session_id}/insights`);
        if (response.ok) {
          const data = await response.json();
          if (data.insights && data.insights.length > 0) {
            setInsights(data.insights);
          }
        }
      } catch (e) {
        console.error('[Insights] Failed to fetch insights:', e);
      }
    };

    // Only fetch if we have no insights yet (loading existing session)
    if (insights.length === 0 && config.session_id) {
      fetchInsights();
    }
  }, [config.session_id]);

  // Ref for insights panel open state (to avoid dependency issues in WebSocket callback)
  const isInsightsOpenRef = useRef(isInsightsOpen);
  useEffect(() => {
    isInsightsOpenRef.current = isInsightsOpen;
  }, [isInsightsOpen]);

  // WebSocket connection - only run once on mount
  useEffect(() => {
    // Prevent double connection in development
    if (hasConnectedRef.current) return;
    hasConnectedRef.current = true;

    const wsUrl = `ws://localhost:11111/ws/discussion/${config.session_id}`;
    console.log('[WebSocket] Connecting to:', wsUrl);

    let ws: WebSocket | null = null;
    let retryCount = 0;
    const maxRetries = 5;
    let isActive = true;

    const connect = () => {
      if (!isActive) return;

      console.log(`[WebSocket] Connection attempt ${retryCount + 1}/${maxRetries}`);
      setConnectionStatus('connecting');

      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isActive) return;
        console.log('[WebSocket] Connected successfully');
        retryCount = 0;
        setConnectionStatus('connected');

        // Send config to start discussion
        ws?.send(JSON.stringify({
          type: 'start',
          config,
        }));
      };

      ws.onmessage = (event) => {
        if (!isActive) return;
        try {
          const data = JSON.parse(event.data);
          console.log('[WebSocket] Received:', data.type);

          switch (data.type) {
            case 'turn':
              addTurn(data.turn);
              updateOrchestratorState(data.state);
              break;

            case 'segment':
              updateSegment(data.segment);
              updateOrchestratorState(data.state);
              break;

            case 'orchestrator':
              addTurn({
                turn_number: data.state.current_turn + 0.5,
                agent_name: 'Orchestrator',
                persona: 'Manager',
                content: data.message,
                timestamp: Date.now() / 1000,
                tool_calls: [],
                tool_results: [],
                segment: data.state.current_segment,
              });
              break;

            case 'insights':
              // Add new insights from WebSocket
              if (data.insights && data.insights.length > 0) {
                addInsights(data.insights);
                // If panel is closed, increment new insights count
                if (!isInsightsOpenRef.current) {
                  setNewInsightsCount(prev => prev + data.insights.length);
                }
              }
              break;

            case 'state':
              updateOrchestratorState(data.state);
              setCurrentStatus(data.state.status);
              break;

            case 'progress':
              setProgressEvent({ event: data.event, data: data.data });
              if (data.event === 'agent_llm_call') {
                setCurrentStatus('thinking');
              } else if (data.event === 'agent_tool_calls') {
                setCurrentStatus('thinking');
              }
              break;

            case 'complete':
              setSummary(data.summary);
              updateOrchestratorState({ ...data.state, is_running: false, status: 'completed' });
              setConnectionStatus('disconnected');
              ws?.close();
              break;

            case 'error':
              console.error('Discussion error:', data.error);
              updateOrchestratorState({ status: 'error' });
              setConnectionStatus('error');
              break;

            case 'pong':
              // Keepalive response
              break;
          }
        } catch (e) {
          console.error('[WebSocket] Error parsing message:', e);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setConnectionStatus('error');
      };

      ws.onclose = (event) => {
        console.log('[WebSocket] Closed:', event.code, event.reason);
        if (!isActive) return;

        // Check if we should retry (not a normal closure)
        if (event.code !== 1000 && retryCount < maxRetries) {
          retryCount++;
          console.log(`[WebSocket] Retrying connection (${retryCount}/${maxRetries})...`);
          setTimeout(connect, 1000 * Math.min(retryCount, 3));
        } else {
          setConnectionStatus('disconnected');
        }
      };
    };

    connect();

    // Keepalive ping
    const pingInterval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    // Cleanup on unmount
    return () => {
      isActive = false;
      clearInterval(pingInterval);
      ws?.close(1000, 'Component unmounting');
    };
  }, []); // Empty dependency array - only connect once

  const handleSendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'user_message',
        content,
      }));
    }
  }, []);

  // Show connecting state when no turns yet
  if (turns.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-4 animate-pulse">
            <span className="text-3xl">💭</span>
          </div>
          <p className="text-body-lg text-on-surface-variant">
            {connectionStatus === 'connecting' && 'Connecting to server...'}
            {connectionStatus === 'connected' && 'Starting discussion...'}
            {connectionStatus === 'error' && 'Connection failed. Please try again.'}
            {connectionStatus === 'disconnected' && 'Disconnected from server.'}
          </p>
          {(connectionStatus === 'error' || connectionStatus === 'disconnected') && (
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 bg-primary text-on-primary rounded-lg font-medium hover:bg-primary-dim transition-colors"
            >
              Retry Connection
            </button>
          )}
          <p className="text-label-sm text-on-surface-variant/50 mt-4">
            Session: {config.session_id}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Topic header */}
      <div className="p-6 border-b border-outline-variant/10 bg-surface-container-low/30">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h2 className="text-headline-md text-on-surface mb-1 truncate" title={config.topic}>
              {config.topic}
            </h2>
            <p className="text-body-md text-on-surface-variant">
              Turn {orchestratorState.current_turn} of {orchestratorState.max_turns} •
              Segment {orchestratorState.current_segment + 1} •
              <span className="ml-1 text-primary">
                Tokens: {orchestratorState.segment_tokens} (segment) / {orchestratorState.total_tokens} (total)
              </span>
            </p>
          </div>
          <StatusIndicator
            status={currentStatus}
            currentAgent={orchestratorState.current_agent}
            progressEvent={progressEvent}
          />
        </div>
      </div>

      {/* Discussion tabs */}
      <div className="flex-1 overflow-hidden">
        <Tabs defaultTab={`segment-${sortedSegments[0]}`} className="h-full flex flex-col">
          <div className="px-6 pt-4 border-b border-outline-variant/10">
            <TabList>
              {sortedSegments.map((segNum) => (
                <Tab key={segNum} value={`segment-${segNum}`}>
                  Segment {segNum + 1}
                </Tab>
              ))}
            </TabList>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            {sortedSegments.map((segNum) => (
              <TabPanel key={segNum} value={`segment-${segNum}`}>
                <div className="space-y-4 max-w-4xl mx-auto">
                  {/* Segment transition message */}
                  {segNum > 0 && segments.find(s => s.segment_number === segNum)?.orchestrator_message && (
                    <Card variant="glass" padding="md">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-xl">🔄</span>
                        <span className="text-label-md font-medium text-tertiary">
                          Segment {segNum + 1} - Continued Discussion
                        </span>
                      </div>
                      <p className="text-body-md text-on-surface-variant">
                        {segments.find(s => s.segment_number === segNum)?.orchestrator_message}
                      </p>
                    </Card>
                  )}

                  {/* Topic for first segment */}
                  {segNum === 0 && (
                    <Card variant="glass" padding="md">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-xl">📋</span>
                        <span className="text-label-md font-medium text-primary">
                          Topic
                        </span>
                      </div>
                      <p className="text-body-md text-on-surface">{config.topic}</p>
                    </Card>
                  )}

                  {/* Turns */}
                  {turnsBySegment[segNum]?.map((turn, idx) => (
                    <MessageCard key={`${segNum}-${idx}`} turn={turn} />
                  ))}

                  <div ref={messagesEndRef} />
                </div>
              </TabPanel>
            ))}
          </div>
        </Tabs>
      </div>

      {/* Input area */}
      {orchestratorState.is_running && (
        <div className="p-4 border-t border-outline-variant/10 bg-surface-container-low/30">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const input = e.currentTarget.elements.namedItem('message') as HTMLInputElement;
              if (input.value.trim()) {
                handleSendMessage(input.value.trim());
                input.value = '';
              }
            }}
            className="flex gap-3 max-w-4xl mx-auto"
          >
            <input
              type="text"
              name="message"
              placeholder="Share your thoughts or ask a question..."
              className="flex-1 bg-surface-container-highest text-on-surface rounded-lg px-4 py-3 border border-transparent focus:border-b-primary focus:bg-surface-bright transition-all duration-200 placeholder:text-on-surface-variant/50"
            />
            <button
              type="submit"
              className="px-6 py-3 bg-primary text-on-primary rounded-lg font-medium hover:bg-primary-dim transition-colors"
            >
              Send
            </button>
          </form>
        </div>
      )}

      {/* Key Insights Panel */}
      <KeyInsightsPanel
        sessionId={config.session_id || ''}
        insights={insights}
        isOpen={isInsightsOpen}
        onToggle={() => {
          setIsInsightsOpen(!isInsightsOpen);
          // Reset new insights count when opening
          if (!isInsightsOpen) {
            setNewInsightsCount(0);
          }
        }}
      />
    </div>
  );
}

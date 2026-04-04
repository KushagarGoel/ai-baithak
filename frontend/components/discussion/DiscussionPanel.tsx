'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { useCouncilStore } from '@/stores/councilStore';
import { MessageCard } from './MessageCard';
import { Card } from '@/components/ui/Card';
import { Tabs, TabList, Tab, TabPanel } from '@/components/ui/Tabs';
import { StatusIndicator } from './StatusIndicator';
import { KeyInsightsPanel } from './KeyInsightsPanel';
import { DiscussionTurn, DiscussionSegment } from '@/types';
import { API_BASE_URL } from '@/lib/utils';

interface ProgressEvent {
  event: string;
  data: any;
}

type DiscussionStatus = 'idle' | 'connecting' | 'running' | 'completed' | 'error';

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
    setWsConnection,
    setWsStatus,
    setCurrentSessionId,
    resetDiscussion,
  } = useCouncilStore();

  // Local state
  const [discussionStatus, setDiscussionStatus] = useState<DiscussionStatus>('idle');
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState(false);

  // Progress tracking
  const [progressEvent, setProgressEvent] = useState<ProgressEvent | null>(null);
  const [currentStatus, setCurrentStatus] = useState<string>(orchestratorState.status);

  // Key insights panel state
  const [isInsightsOpen, setIsInsightsOpen] = useState(false);
  const [newInsightsCount, setNewInsightsCount] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const isActiveRef = useRef(true);
  const retryCountRef = useRef(0);
  const maxRetries = 3;
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastPongRef = useRef<number>(Date.now());

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

  // Check if this is an existing session and load data via API
  useEffect(() => {
    const loadExistingSession = async () => {
      if (!config.session_id) return;

      setIsLoadingSession(true);
      try {
        // Try to load session data via API
        const response = await fetch(`${API_BASE_URL}/api/sessions/${config.session_id}`, { credentials: 'include' });
        if (response.ok) {
          const sessionData = await response.json();

          // If session has turns, load them
          if (sessionData.turns && sessionData.turns.length > 0) {
            // Load turns
            sessionData.turns.forEach((turn: DiscussionTurn) => {
              addTurn(turn);
            });

            // Load segments
            if (sessionData.segments) {
              sessionData.segments.forEach((seg: DiscussionSegment) => {
                updateSegment(seg);
              });
            }

            // Update orchestrator state
            updateOrchestratorState({
              current_turn: sessionData.current_turn || 0,
              current_segment: sessionData.current_segment || 0,
              is_running: false,
              status: sessionData.status === 'completed' ? 'completed' : 'idle',
            });

            // Load summary if completed
            if (sessionData.status === 'completed' && sessionData.summary) {
              setSummary(sessionData.summary);
              setDiscussionStatus('completed');
            } else {
              setDiscussionStatus('idle');
            }
          }

          // Load insights
          const insightsResponse = await fetch(`${API_BASE_URL}/api/sessions/${config.session_id}/insights`, { credentials: 'include' });
          if (insightsResponse.ok) {
            const insightsData = await insightsResponse.json();
            if (insightsData.insights && insightsData.insights.length > 0) {
              setInsights(insightsData.insights);
            }
          }
        }
      } catch (e) {
        console.error('[Session] Failed to load session:', e);
      } finally {
        setIsLoadingSession(false);
      }
    };

    // Only load if no turns yet (first time loading this session)
    if (turns.length === 0 && config.session_id) {
      loadExistingSession();
    }
  }, [config.session_id]);

  // Ref for insights panel open state
  const isInsightsOpenRef = useRef(isInsightsOpen);
  useEffect(() => {
    isInsightsOpenRef.current = isInsightsOpen;
  }, [isInsightsOpen]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isActiveRef.current = false;
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
        wsRef.current = null;
      }
    };
  }, []);

  // Start heartbeat to keep connection alive
  const startHeartbeat = useCallback(() => {
    // Send ping every 20 seconds to prevent idle timeout
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        // Check if we haven't received a pong in 60 seconds
        if (Date.now() - lastPongRef.current > 60000) {
          console.log('[WebSocket] No pong received for 60s, closing connection');
          wsRef.current.close(1011, 'Heartbeat timeout');
          return;
        }
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 20000);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  // Start discussion - connect WebSocket only when user clicks start
  const startDiscussion = useCallback(() => {
    if (!config.session_id) {
      // Generate new session ID if not set
      const newSessionId = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      setCurrentSessionId(newSessionId);
    }

    setDiscussionStatus('connecting');
    setConnectionError(null);
    retryCountRef.current = 0;

    const sessionId = config.session_id || new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}/ws/discussion/${sessionId}`;

    console.log('[WebSocket] Connecting to:', wsUrl);

    const connect = () => {
      if (!isActiveRef.current) return;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      setWsConnection(ws);
      setWsStatus('connecting');

      ws.onopen = () => {
        if (!isActiveRef.current) return;
        console.log('[WebSocket] Connected successfully');
        retryCountRef.current = 0;
        lastPongRef.current = Date.now();
        setWsStatus('connected');
        setDiscussionStatus('running');

        // Start heartbeat to prevent idle timeout
        startHeartbeat();

        // Update orchestrator state
        updateOrchestratorState({ is_running: true, status: 'thinking' });

        // Send config to start discussion
        ws.send(JSON.stringify({
          type: 'start',
          config: { ...config, session_id: sessionId },
        }));
      };

      ws.onmessage = (event) => {
        if (!isActiveRef.current) return;
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
              updateOrchestratorState(data.state);
              break;

            case 'insights':
              console.log('[WebSocket] Received insights:', data.insights?.length);
              if (data.insights && data.insights.length > 0) {
                addInsights(data.insights);
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
              if (data.event === 'agent_llm_call' || data.event === 'agent_tool_calls') {
                setCurrentStatus('thinking');
              }
              break;

            case 'complete':
              setSummary(data.summary);
              updateOrchestratorState({ ...data.state, is_running: false, status: 'completed' });
              setDiscussionStatus('completed');
              setWsStatus('disconnected');
              ws.close();
              break;

            case 'error':
              console.error('Discussion error:', data.error);
              updateOrchestratorState({ status: 'error' });
              setDiscussionStatus('error');
              setConnectionError(data.error);
              break;

            case 'pong':
              // Keepalive response
              lastPongRef.current = Date.now();
              break;
          }
        } catch (e) {
          console.error('[WebSocket] Error parsing message:', e);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setWsStatus('error');
      };

      ws.onclose = (event) => {
        console.log('[WebSocket] Closed:', event.code, event.reason);
        stopHeartbeat();
        setWsStatus('disconnected');
        setWsConnection(null);

        if (!isActiveRef.current) return;

        // Retry on abnormal closure
        if (event.code !== 1000 && event.code !== 1001 && retryCountRef.current < maxRetries) {
          if (discussionStatus === 'running') {
            retryCountRef.current++;
            console.log(`[WebSocket] Retrying connection (${retryCountRef.current}/${maxRetries})...`);
            setTimeout(connect, 1000 * Math.min(retryCountRef.current, 3));
          }
        } else if (discussionStatus === 'running') {
          setDiscussionStatus('error');
          setConnectionError('Connection lost. Please try again.');
        }
      };
    };

    connect();
  }, [config, config.session_id, setCurrentSessionId, setWsConnection, setWsStatus, updateOrchestratorState, addTurn, updateSegment, setSummary, addInsights, setInsights, discussionStatus]);

  // Stop discussion
  const stopDiscussion = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }));
      console.log('[Stop] Stop message sent');
    }
  }, []);

  // Send user message
  const handleSendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'user_message',
        content,
      }));
    }
  }, []);

  // Reset and start new discussion
  const handleNewDiscussion = useCallback(() => {
    resetDiscussion();
    setDiscussionStatus('idle');
    setConnectionError(null);
    setInsights([]);
    setCurrentSessionId(null);
  }, [resetDiscussion, setInsights, setCurrentSessionId]);

  // Show loading state
  if (isLoadingSession) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-4 animate-pulse">
            <span className="text-3xl">📂</span>
          </div>
          <p className="text-body-lg text-on-surface-variant">Loading session...</p>
        </div>
      </div>
    );
  }

  // Show start screen when idle
  if (discussionStatus === 'idle' && turns.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-6">
            <span className="text-4xl">🏛️</span>
          </div>
          <h2 className="text-headline-md text-on-surface mb-2">Ready to Start</h2>
          <p className="text-body-md text-on-surface-variant mb-6">
            Topic: <span className="text-on-surface font-medium">{config.topic}</span>
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={startDiscussion}
              className="px-6 py-3 bg-primary text-on-primary rounded-lg font-medium hover:bg-primary-dim transition-colors"
            >
              Start Discussion
            </button>
          </div>
          <div className="mt-6 text-label-sm text-on-surface-variant/60">
            <p>Session: {config.session_id || 'New Session'}</p>
            <p className="mt-1">{config.agents.length} agents • {config.max_turns} max turns</p>
          </div>
        </div>
      </div>
    );
  }

  // Show connecting state
  if (discussionStatus === 'connecting') {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-4 animate-pulse">
            <span className="text-3xl">🔗</span>
          </div>
          <p className="text-body-lg text-on-surface-variant">Connecting to server...</p>
          <p className="text-label-sm text-on-surface-variant/50 mt-2">
            Session: {config.session_id}
          </p>
        </div>
      </div>
    );
  }

  // Show error state
  if (discussionStatus === 'error') {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-full bg-error/10 flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">⚠️</span>
          </div>
          <h2 className="text-headline-md text-error mb-2">Connection Error</h2>
          <p className="text-body-md text-on-surface-variant mb-6">
            {connectionError || 'Failed to connect to the discussion server.'}
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={startDiscussion}
              className="px-6 py-3 bg-primary text-on-primary rounded-lg font-medium hover:bg-primary-dim transition-colors"
            >
              Retry Connection
            </button>
            <button
              onClick={handleNewDiscussion}
              className="px-6 py-3 bg-surface-container-high text-on-surface rounded-lg font-medium hover:bg-surface-container transition-colors"
            >
              New Discussion
            </button>
          </div>
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
          <div className="flex items-center gap-3">
            {discussionStatus === 'running' && (
              <button
                onClick={stopDiscussion}
                className="px-4 py-2 bg-error text-on-error rounded-lg font-medium hover:bg-error-dim transition-colors"
              >
                Stop
              </button>
            )}
            {discussionStatus === 'completed' && (
              <button
                onClick={handleNewDiscussion}
                className="px-4 py-2 bg-secondary text-on-secondary rounded-lg font-medium hover:bg-secondary-dim transition-colors"
              >
                New Discussion
              </button>
            )}
            <StatusIndicator
              status={currentStatus}
              currentAgent={orchestratorState.current_agent}
              progressEvent={progressEvent}
            />
          </div>
        </div>
      </div>

      {/* Discussion tabs */}
      <div className="flex-1 overflow-hidden">
        <Tabs defaultTab={`segment-${sortedSegments[0] || 0}`} className="h-full flex flex-col">
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

      {/* Input area - only show when running */}
      {discussionStatus === 'running' && (
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
          if (!isInsightsOpen) {
            setNewInsightsCount(0);
          }
        }}
      />
    </div>
  );
}

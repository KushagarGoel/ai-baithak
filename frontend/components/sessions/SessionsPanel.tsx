'use client';

import { useEffect, useState } from 'react';
import { useCouncilStore } from '@/stores/councilStore';
import { Session, DiscussionTurn, CouncilConfig } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { formatDate, formatTokens, truncate, API_BASE_URL } from '@/lib/utils';

export function SessionsPanel() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const { setViewMode, setCurrentSessionId, resetDiscussion, updateConfig, setComprehensiveReport } = useCouncilStore();

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const response = await fetch('/api/sessions', { credentials: 'include' });
      if (response.status === 401) {
        window.location.href = '/login';
        return;
      }
      const data = await response.json();
      setSessions(data.sessions || []);
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSession = async (sessionId: string) => {
    try {
      const response = await fetch(`/api/sessions/${sessionId}`, { credentials: 'include' });
      if (response.status === 401) {
        window.location.href = '/login';
        return;
      }
      const data = await response.json();

      if (data.config) {
        updateConfig(data.config);
        setCurrentSessionId(sessionId);

        // Restore turns if available
        if (data.turns) {
          resetDiscussion();
          // Turns would be restored via the store
        }

        setViewMode('discussion');
      }
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  };

  const deleteSession = async (sessionId: string) => {
    if (!confirm('Are you sure you want to delete this session?')) return;

    try {
      const response = await fetch(`/api/sessions/${sessionId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (response.status === 401) {
        window.location.href = '/login';
        return;
      }
      setSessions(sessions.filter(s => s.id !== sessionId));
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const viewReport = async (sessionId: string) => {
    try {
      // First try to get existing report
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/report`, { credentials: 'include' });
      if (response.ok) {
        const report = await response.json();
        setComprehensiveReport(report);
        setCurrentSessionId(sessionId);
        setViewMode('report');
        return;
      }

      // If no report exists, generate one on-demand
      if (response.status === 404) {
        if (confirm('No report exists for this session. Generate one now?')) {
          await generateReport(sessionId);
        }
        return;
      }

      throw new Error('Failed to load report');
    } catch (error) {
      console.error('Failed to load report:', error);
      alert('Failed to load report');
    }
  };

  const generateReport = async (sessionId: string, customInstructions?: string) => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/generate-report`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ custom_instructions: customInstructions }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate report');
      }

      const data = await response.json();
      if (data.success && data.report) {
        setComprehensiveReport(data.report);
        setCurrentSessionId(sessionId);
        setViewMode('report');
      }
    } catch (error) {
      console.error('Failed to generate report:', error);
      alert('Failed to generate report');
    } finally {
      setLoading(false);
    }
  };

  const downloadReportMD = async (sessionId: string, topic: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/report-pdf`, { credentials: 'include' });
      if (!response.ok) {
        if (response.status === 404) {
          if (confirm('No report exists. Generate one first?')) {
            await generateReport(sessionId);
          }
          return;
        }
        throw new Error('Failed to download report');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${sessionId}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download report:', error);
      alert('Failed to download report');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="mb-8">
        <h1 className="text-display-md font-bold gradient-text mb-2">Active Sessions</h1>
        <p className="text-body-lg text-on-surface-variant">
          Continue or manage your ongoing discussions
        </p>
      </div>

      {sessions.length === 0 ? (
        <Card variant="elevated" className="text-center py-16">
          <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">💭</span>
          </div>
          <h3 className="text-headline-sm text-on-surface mb-2">No Active Sessions</h3>
          <p className="text-body-md text-on-surface-variant mb-6">
            Start a new discussion from the MCP Config tab
          </p>
          <Button variant="primary" onClick={() => setViewMode('config')}>
            Configure New Council
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4">
          {sessions.map((session) => (
            <Card key={session.id} variant="elevated" className="group">
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-headline-sm text-on-surface">
                        {truncate(session.topic, 60)}
                      </h3>
                      {session.total_tokens && session.total_tokens > 0 && (
                        <span className="px-2 py-0.5 bg-primary/20 text-primary rounded-full text-label-sm">
                          {formatTokens(session.total_tokens)} tokens
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-body-md text-on-surface-variant">
                      <span>{session.turns} turns</span>
                      <span>•</span>
                      <span>Segment {session.current_segment || 1}</span>
                      <span>•</span>
                      <span>{formatDate(session.date)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => loadSession(session.id)}
                    >
                      Continue
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => viewReport(session.id)}
                    >
                      View Report
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => generateReport(session.id)}
                    >
                      Generate Report
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => downloadReportMD(session.id, session.topic)}
                    >
                      Download MD
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteSession(session.id)}
                      className="text-error hover:bg-error/10"
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

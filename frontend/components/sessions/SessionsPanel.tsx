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
      const response = await fetch('/api/sessions');
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
      const response = await fetch(`/api/sessions/${sessionId}`);
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
      await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
      setSessions(sessions.filter(s => s.id !== sessionId));
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const viewReport = async (sessionId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/report`);
      if (!response.ok) {
        alert('Report not available yet. Wait for discussion to complete.');
        return;
      }
      const report = await response.json();
      setComprehensiveReport(report);
      setCurrentSessionId(sessionId);
      setViewMode('report');
    } catch (error) {
      console.error('Failed to load report:', error);
      alert('Failed to load report');
    }
  };

  const downloadReportPDF = async (sessionId: string, topic: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/report`);
      if (!response.ok) {
        alert('Report not available yet. Wait for discussion to complete.');
        return;
      }
      const report = await response.json();

      // Generate PDF content
      const pdfContent = generatePDFContent(report);
      const blob = new Blob([pdfContent], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${sessionId}.html`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download report:', error);
      alert('Failed to download report');
    }
  };

  const generatePDFContent = (report: any) => {
    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Solutioning Report - ${report.topic}</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
    h1 { color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }
    h2 { color: #555; margin-top: 30px; }
    h3 { color: #666; }
    .section { margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 8px; }
    .highlight { background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin: 15px 0; }
    ul { line-height: 1.8; }
    .meta { color: #888; font-size: 0.9em; }
  </style>
</head>
<body>
  <h1>Solutioning Report</h1>
  <p class="meta">Topic: ${report.topic}</p>
  <p class="meta">Date: ${new Date(report.end_time).toLocaleString()}</p>
  <p class="meta">Turns: ${report.total_turns}</p>

  <div class="section">
    <h2>Problem Statement</h2>
    <p>${report.problem_statement || 'N/A'}</p>
  </div>

  <div class="highlight">
    <h2>Final Answer</h2>
    <p>${report.final_answer || 'N/A'}</p>
  </div>

  <div class="section">
    <h2>Justification</h2>
    <p>${report.justification || 'N/A'}</p>
  </div>

  ${report.solution_options?.length ? `
  <div class="section">
    <h2>Solution Options</h2>
    ${report.solution_options.map((opt: any) => `
      <h3>${opt.option_name} ${opt.option_name === report.selected_solution ? '(Selected)' : ''}</h3>
      <p>${opt.description}</p>
      <p><strong>Pros:</strong> ${opt.pros.join(', ')}</p>
      <p><strong>Cons:</strong> ${opt.cons.join(', ')}</p>
    `).join('')}
  </div>
  ` : ''}

  ${report.implementation_steps?.length ? `
  <div class="section">
    <h2>Implementation Steps</h2>
    <ol>
      ${report.implementation_steps.map((step: string) => `<li>${step}</li>`).join('')}
    </ol>
  </div>
  ` : ''}

  ${report.action_items?.length ? `
  <div class="section">
    <h2>Action Items</h2>
    <ul>
      ${report.action_items.map((item: string) => `<li>${item}</li>`).join('')}
    </ul>
  </div>
  ` : ''}
</body>
</html>`;
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
                      Report
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => downloadReportPDF(session.id, session.topic)}
                    >
                      Download
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

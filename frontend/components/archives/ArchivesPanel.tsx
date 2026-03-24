'use client';

import { useEffect, useState } from 'react';
import { DiscussionSummary } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { formatDate, formatDuration, truncate } from '@/lib/utils';
import { Badge } from '@/components/ui/Badge';

interface ArchiveItem {
  id: string;
  summary: DiscussionSummary;
  transcript_path: string;
  agent_count: number;
  model_names: string[];
}

export function ArchivesPanel() {
  const [archives, setArchives] = useState<ArchiveItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedArchive, setSelectedArchive] = useState<ArchiveItem | null>(null);

  useEffect(() => {
    fetchArchives();
  }, []);

  const fetchArchives = async () => {
    try {
      const response = await fetch('/api/archives');
      const data = await response.json();
      setArchives(data.archives || []);
    } catch (error) {
      console.error('Failed to fetch archives:', error);
    } finally {
      setLoading(false);
    }
  };

  const downloadTranscript = async (transcriptPath: string) => {
    try {
      const response = await fetch(`/api/transcripts/${encodeURIComponent(transcriptPath)}`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = transcriptPath.split('/').pop() || 'transcript.json';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to download transcript:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (selectedArchive) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <Button
          variant="ghost"
          onClick={() => setSelectedArchive(null)}
          className="mb-6"
        >
          ← Back to Archives
        </Button>

        <Card variant="elevated">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="text-headline-lg mb-2">
                  {selectedArchive.summary.topic}
                </CardTitle>
                <p className="text-body-md text-on-surface-variant">
                  Completed on {formatDate(selectedArchive.summary.end_time)}
                </p>
              </div>
              <Badge
                variant={selectedArchive.summary.consensus_reached ? 'success' : 'warning'}
                size="md"
              >
                {selectedArchive.summary.consensus_reached ? 'Consensus' : 'No Consensus'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Stats */}
            <div className="grid grid-cols-4 gap-4">
              <div className="p-4 bg-surface-container-low rounded-lg text-center">
                <p className="text-headline-md text-primary">{selectedArchive.summary.total_turns}</p>
                <p className="text-label-sm text-on-surface-variant">Total Turns</p>
              </div>
              <div className="p-4 bg-surface-container-low rounded-lg text-center">
                <p className="text-headline-md text-secondary">
                  {formatDuration(selectedArchive.summary.start_time, selectedArchive.summary.end_time)}
                </p>
                <p className="text-label-sm text-on-surface-variant">Duration</p>
              </div>
              <div className="p-4 bg-surface-container-low rounded-lg text-center">
                <p className="text-headline-md text-tertiary">{selectedArchive.agent_count}</p>
                <p className="text-label-sm text-on-surface-variant">Agents</p>
              </div>
              <div className="p-4 bg-surface-container-low rounded-lg text-center">
                <p className="text-headline-md text-on-surface">{selectedArchive.summary.action_items.length}</p>
                <p className="text-label-sm text-on-surface-variant">Action Items</p>
              </div>
            </div>

            {/* Key Points */}
            {selectedArchive.summary.key_points.length > 0 && (
              <div>
                <h3 className="text-headline-sm text-on-surface mb-3">Key Points</h3>
                <ul className="space-y-2">
                  {selectedArchive.summary.key_points.map((point, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-body-md text-on-surface">
                      <span className="text-primary mt-1">•</span>
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Disagreements */}
            {selectedArchive.summary.disagreements.length > 0 && (
              <div>
                <h3 className="text-headline-sm text-on-surface mb-3">Disagreements</h3>
                <ul className="space-y-2">
                  {selectedArchive.summary.disagreements.map((d, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-body-md text-on-surface">
                      <span className="text-error mt-1">⚠</span>
                      {d}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Action Items */}
            {selectedArchive.summary.action_items.length > 0 && (
              <div>
                <h3 className="text-headline-sm text-on-surface mb-3">Action Items</h3>
                <ul className="space-y-2">
                  {selectedArchive.summary.action_items.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-body-md text-on-surface">
                      <span className="text-secondary mt-1">☐</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Final Recommendation */}
            {selectedArchive.summary.final_recommendation && (
              <div className="p-4 bg-surface-container-low rounded-lg">
                <h3 className="text-headline-sm text-on-surface mb-2">Final Recommendation</h3>
                <p className="text-body-md text-on-surface-variant">
                  {selectedArchive.summary.final_recommendation}
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end pt-4 border-t border-outline-variant/10">
              <Button
                variant="primary"
                onClick={() => downloadTranscript(selectedArchive.transcript_path)}
              >
                Download Transcript
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="mb-8">
        <h1 className="text-display-md font-bold gradient-text mb-2">Archives</h1>
        <p className="text-body-lg text-on-surface-variant">
          Browse past council discussions and their outcomes
        </p>
      </div>

      {archives.length === 0 ? (
        <Card variant="elevated" className="text-center py-16">
          <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">📚</span>
          </div>
          <h3 className="text-headline-sm text-on-surface mb-2">No Archives Yet</h3>
          <p className="text-body-md text-on-surface-variant">
            Completed discussions will appear here
          </p>
        </Card>
      ) : (
        <div className="grid gap-4">
          {archives.map((archive) => (
            <Card
              key={archive.id}
              variant="elevated"
              className="cursor-pointer hover:bg-surface-container/50 transition-colors"
              onClick={() => setSelectedArchive(archive)}
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-headline-sm text-on-surface">
                        {truncate(archive.summary.topic, 60)}
                      </h3>
                      <Badge
                        variant={archive.summary.consensus_reached ? 'success' : 'warning'}
                      >
                        {archive.summary.consensus_reached ? 'Consensus' : 'No Consensus'}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-body-md text-on-surface-variant">
                      <span>{archive.summary.total_turns} turns</span>
                      <span>•</span>
                      <span>{archive.agent_count} agents</span>
                      <span>•</span>
                      <span>{formatDate(archive.summary.end_time)}</span>
                      <span>•</span>
                      <span>{formatDuration(archive.summary.start_time, archive.summary.end_time)}</span>
                    </div>
                    {archive.summary.final_recommendation && (
                      <p className="mt-2 text-body-md text-on-surface-variant line-clamp-2">
                        {archive.summary.final_recommendation}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        downloadTranscript(archive.transcript_path);
                      }}
                    >
                      Download
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

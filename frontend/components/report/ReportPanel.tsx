'use client';

import { useState, useEffect } from 'react';
import { useCouncilStore } from '@/stores/councilStore';
import { ComprehensiveReport, SolutionOption, SegmentReport, AgentAnalysis } from '@/types';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { API_BASE_URL } from '@/lib/utils';
import { cn } from '@/lib/utils';

export function ReportPanel() {
  const { currentSessionId, setViewMode, comprehensiveReport, setComprehensiveReport } = useCouncilStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'solutions' | 'segments' | 'agents' | 'implementation'>('overview');

  useEffect(() => {
    if (currentSessionId && !comprehensiveReport) {
      fetchReport();
    }
  }, [currentSessionId]);

  const fetchReport = async () => {
    if (!currentSessionId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${currentSessionId}/report`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Report not yet generated. Wait for the discussion to complete.');
        }
        throw new Error('Failed to fetch report');
      }
      const data = await response.json();
      setComprehensiveReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-on-surface-variant">Loading comprehensive report...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
        <div className="text-error text-lg">Error loading report</div>
        <p className="text-on-surface-variant text-center max-w-md">{error}</p>
        <div className="flex gap-2">
          <Button onClick={fetchReport} variant="primary">Retry</Button>
          <Button onClick={() => setViewMode('discussion')} variant="secondary">Back to Discussion</Button>
        </div>
      </div>
    );
  }

  if (!comprehensiveReport) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
        <p className="text-on-surface-variant">No report available</p>
        <Button onClick={() => setViewMode('discussion')} variant="primary">Back to Discussion</Button>
      </div>
    );
  }

  const report = comprehensiveReport;

  return (
    <div className="h-full overflow-auto bg-background">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-surface/95 backdrop-blur border-b border-outline-variant/10 px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-headline-md font-bold text-on-surface">Solutioning Report</h1>
            <p className="text-body-sm text-on-surface-variant mt-1">{report.topic}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={report.consensus_reached ? 'success' : 'warning'}>
              {report.consensus_reached ? 'Consensus Reached' : 'No Consensus'}
            </Badge>
            <Button onClick={() => setViewMode('discussion')} variant="secondary" size="sm">
              Back to Discussion
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-outline-variant/10">
          {[
            { id: 'overview', label: 'Overview' },
            { id: 'solutions', label: 'Solutions' },
            { id: 'segments', label: 'Segments' },
            { id: 'agents', label: 'Agents' },
            { id: 'implementation', label: 'Implementation' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={cn(
                'px-4 py-2 text-label-md font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-on-surface-variant hover:text-on-surface'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-6 max-w-6xl mx-auto">
        {activeTab === 'overview' && <OverviewTab report={report} />}
        {activeTab === 'solutions' && <SolutionsTab report={report} />}
        {activeTab === 'segments' && <SegmentsTab report={report} />}
        {activeTab === 'agents' && <AgentsTab report={report} />}
        {activeTab === 'implementation' && <ImplementationTab report={report} />}
      </div>
    </div>
  );
}

function OverviewTab({ report }: { report: ComprehensiveReport }) {
  return (
    <div className="space-y-6">
      {/* Problem Statement */}
      <Card className="p-6" variant="elevated">
        <h2 className="text-title-md font-semibold text-on-surface mb-3">Problem Statement</h2>
        <p className="text-body-md text-on-surface leading-relaxed">{report.problem_statement || 'No problem statement available.'}</p>
      </Card>

      {/* Final Answer */}
      <Card className="p-6 border-2 border-secondary/30 bg-secondary/5" variant="elevated">
        <h2 className="text-title-md font-semibold text-on-surface mb-3">Final Answer</h2>
        <p className="text-body-md text-on-surface leading-relaxed whitespace-pre-wrap">{report.final_answer || 'No final answer available.'}</p>
      </Card>

      {/* Justification */}
      <Card className="p-6" variant="elevated">
        <h2 className="text-title-md font-semibold text-on-surface mb-3">Justification</h2>
        <p className="text-body-md text-on-surface leading-relaxed whitespace-pre-wrap">{report.justification || 'No justification available.'}</p>
      </Card>

      {/* Key Points */}
      {report.key_points && report.key_points.length > 0 && (
        <Card className="p-6" variant="elevated">
          <h2 className="text-title-md font-semibold text-on-surface mb-3">Key Points</h2>
          <ul className="space-y-2">
            {report.key_points.map((point, i) => (
              <li key={i} className="flex gap-3 text-body-md text-on-surface">
                <span className="text-primary font-bold">{i + 1}.</span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Disagreements */}
      {report.disagreements && report.disagreements.length > 0 && (
        <Card className="p-6 border-2 border-tertiary/30 bg-tertiary/5" variant="elevated">
          <h2 className="text-title-md font-semibold text-on-surface mb-3">Areas of Disagreement</h2>
          <ul className="space-y-2">
            {report.disagreements.map((disagreement, i) => (
              <li key={i} className="flex gap-2 text-body-md text-on-surface">
                <span className="text-tertiary">⚠</span>
                <span>{disagreement}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Final Recommendation */}
      {report.final_recommendation && (
        <Card className="p-6 border-2 border-secondary/30 bg-secondary/10" variant="elevated">
          <h2 className="text-title-md font-semibold text-on-surface mb-3">Executive Recommendation</h2>
          <p className="text-body-md text-on-surface leading-relaxed">{report.final_recommendation}</p>
        </Card>
      )}
    </div>
  );
}

function SolutionsTab({ report }: { report: ComprehensiveReport }) {
  return (
    <div className="space-y-6">
      {report.selected_solution && (
        <Card className="p-6 border-2 border-secondary/30 bg-secondary/10" variant="elevated">
          <h2 className="text-title-md font-semibold text-on-surface mb-2">Selected Solution</h2>
          <p className="text-headline-sm font-medium text-on-surface mb-3">{report.selected_solution}</p>
          <h3 className="text-label-md font-semibold text-on-surface-variant mb-1">Selection Reasoning</h3>
          <p className="text-body-md text-on-surface leading-relaxed">{report.selection_reasoning || 'No reasoning provided.'}</p>
        </Card>
      )}

      <div className="grid gap-4">
        {report.solution_options?.map((option: SolutionOption, i: number) => (
          <Card
            key={i}
            className={cn(
              "p-6",
              option.option_name === report.selected_solution ? "border-2 border-secondary" : ""
            )}
            variant="elevated"
          >
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-title-md font-semibold text-on-surface">{option.option_name}</h3>
              {option.option_name === report.selected_solution && (
                <Badge variant="success">Selected</Badge>
              )}
            </div>
            <p className="text-body-md text-on-surface mb-4">{option.description}</p>

            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-label-md font-semibold text-secondary mb-2">Pros</h4>
                <ul className="space-y-1">
                  {option.pros.map((pro, j) => (
                    <li key={j} className="text-body-sm text-on-surface flex gap-2">
                      <span className="text-secondary">+</span>
                      {pro}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-label-md font-semibold text-error mb-2">Cons</h4>
                <ul className="space-y-1">
                  {option.cons.map((con, j) => (
                    <li key={j} className="text-body-sm text-on-surface flex gap-2">
                      <span className="text-error">-</span>
                      {con}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="flex gap-4 mt-4 pt-4 border-t border-outline-variant/10">
              <div>
                <span className="text-label-sm text-on-surface-variant">Supporters:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {option.supporters.map((s, j) => (
                    <Badge key={j} variant="secondary" size="sm">{s}</Badge>
                  ))}
                </div>
              </div>
              {option.opposers.length > 0 && (
                <div>
                  <span className="text-label-sm text-on-surface-variant">Opposers:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {option.opposers.map((s, j) => (
                      <Badge key={j} variant="error" size="sm">{s}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function SegmentsTab({ report }: { report: ComprehensiveReport }) {
  return (
    <div className="space-y-4">
      {report.segment_reports?.map((segment: SegmentReport, i: number) => (
        <Card key={i} className="p-6" variant="elevated">
          <div className="flex items-center gap-2 mb-3">
            <Badge variant="primary">Segment {segment.segment_number}</Badge>
          </div>

          <h3 className="text-title-md font-medium text-on-surface mb-3">{segment.summary}</h3>

          {segment.key_developments && segment.key_developments.length > 0 && (
            <div className="mb-4">
              <h4 className="text-label-md font-semibold text-on-surface-variant mb-2">Key Developments</h4>
              <ul className="space-y-1">
                {segment.key_developments.map((dev, j) => (
                  <li key={j} className="text-body-sm text-on-surface flex gap-2">
                    <span className="text-primary">→</span>
                    {dev}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {segment.decisions_made && segment.decisions_made.length > 0 && (
            <div className="mb-4">
              <h4 className="text-label-md font-semibold text-on-surface-variant mb-2">Decisions Made</h4>
              <ul className="space-y-1">
                {segment.decisions_made.map((decision, j) => (
                  <li key={j} className="text-body-sm text-on-surface flex gap-2">
                    <span className="text-secondary">✓</span>
                    {decision}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {segment.open_questions && segment.open_questions.length > 0 && (
            <div className="mb-4">
              <h4 className="text-label-md font-semibold text-on-surface-variant mb-2">Open Questions</h4>
              <ul className="space-y-1">
                {segment.open_questions.map((q, j) => (
                  <li key={j} className="text-body-sm text-on-surface flex gap-2">
                    <span className="text-tertiary">?</span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {segment.agent_contributions && Object.keys(segment.agent_contributions).length > 0 && (
            <div className="mt-4 pt-4 border-t border-outline-variant/10">
              <h4 className="text-label-md font-semibold text-on-surface-variant mb-2">Agent Contributions</h4>
              <div className="space-y-2">
                {Object.entries(segment.agent_contributions).map(([agent, contribution], j) => (
                  <div key={j} className="text-body-sm">
                    <span className="font-medium text-on-surface">{agent}:</span>
                    <span className="text-on-surface-variant ml-2">{contribution}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function AgentsTab({ report }: { report: ComprehensiveReport }) {
  const stanceColors: Record<string, 'success' | 'error' | 'secondary' | 'warning'> = {
    supportive: 'success',
    opposed: 'error',
    neutral: 'secondary',
    skeptical: 'warning',
  };

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {report.agent_analyses?.map((agent: AgentAnalysis, i: number) => (
        <Card key={i} className="p-6" variant="elevated">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-title-md font-semibold text-on-surface">{agent.agent_name}</h3>
              <p className="text-body-sm text-on-surface-variant">{agent.persona}</p>
            </div>
            {agent.stance && (
              <Badge variant={stanceColors[agent.stance.toLowerCase()] || 'secondary'}>
                {agent.stance}
              </Badge>
            )}
          </div>

          {agent.critical_points && agent.critical_points.length > 0 && (
            <div className="mb-4">
              <h4 className="text-label-md font-semibold text-on-surface-variant mb-2">Critical Points</h4>
              <ul className="space-y-1">
                {agent.critical_points.map((point, j) => (
                  <li key={j} className="text-body-sm text-on-surface flex gap-2">
                    <span className="text-primary">•</span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {agent.key_arguments && agent.key_arguments.length > 0 && (
            <div className="mb-4">
              <h4 className="text-label-md font-semibold text-on-surface-variant mb-2">Key Arguments</h4>
              <ul className="space-y-1">
                {agent.key_arguments.map((arg, j) => (
                  <li key={j} className="text-body-sm text-on-surface flex gap-2">
                    <span className="text-secondary">→</span>
                    {arg}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {agent.tools_used && agent.tools_used.length > 0 && (
            <div className="mt-4 pt-4 border-t border-outline-variant/10">
              <h4 className="text-label-md font-semibold text-on-surface-variant mb-2">Tools Used</h4>
              <div className="flex flex-wrap gap-1">
                {agent.tools_used.map((tool, j) => (
                  <Badge key={j} variant="secondary" size="sm">{tool}</Badge>
                ))}
              </div>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function ImplementationTab({ report }: { report: ComprehensiveReport }) {
  return (
    <div className="space-y-6">
      {/* Implementation Steps */}
      <Card className="p-6" variant="elevated">
        <h2 className="text-title-md font-semibold text-on-surface mb-4">Implementation Steps</h2>
        {report.implementation_steps && report.implementation_steps.length > 0 ? (
          <div className="space-y-3">
            {report.implementation_steps.map((step, i) => (
              <div key={i} className="flex gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium text-label-md">
                  {i + 1}
                </div>
                <div className="flex-1 pt-1">
                  <p className="text-body-md text-on-surface">{step}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-on-surface-variant">No implementation steps available.</p>
        )}
      </Card>

      {/* Risks and Mitigations */}
      <Card className="p-6" variant="elevated">
        <h2 className="text-title-md font-semibold text-on-surface mb-4">Risks & Mitigations</h2>
        {report.risks_and_mitigations && report.risks_and_mitigations.length > 0 ? (
          <ul className="space-y-3">
            {report.risks_and_mitigations.map((risk, i) => (
              <li key={i} className="text-body-md text-on-surface flex gap-2 p-3 bg-surface-container rounded-lg">
                <span className="text-tertiary">⚠</span>
                <span>{risk}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-on-surface-variant">No risk analysis available.</p>
        )}
      </Card>

      {/* Action Items */}
      <Card className="p-6" variant="elevated">
        <h2 className="text-title-md font-semibold text-on-surface mb-4">Action Items</h2>
        {report.action_items && report.action_items.length > 0 ? (
          <ul className="space-y-2">
            {report.action_items.map((item, i) => (
              <li key={i} className="text-body-md text-on-surface flex gap-2">
                <span className="text-primary">☐</span>
                {item}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-on-surface-variant">No action items available.</p>
        )}
      </Card>
    </div>
  );
}

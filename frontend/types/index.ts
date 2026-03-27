export interface Persona {
  name: string;
  system_prompt: string;
  temperature: number;
  max_tokens?: number;
  speak_probability: number;
}

export interface AgentConfig {
  name: string;
  model: string;
  persona: string;
  temperature?: number;
  max_tokens?: number;
  tools_enabled: boolean;
}

export interface LiteLLMProxyConfig {
  api_base: string;
  api_key: string;
}

export interface CouncilConfig {
  topic: string;
  max_duration_minutes: number;
  max_turns: number;
  min_turns: number;
  agents: AgentConfig[];
  litellm_proxy?: LiteLLMProxyConfig;
  orchestrator_model: string;
  orchestrator_frequency: number;
  context_compression_threshold: number;
  session_id?: string;
  save_transcript?: boolean;
  workspace_path?: string;
}

export interface DiscussionTurn {
  turn_number: number;
  agent_name: string;
  persona: string;
  content: string;
  timestamp: number;
  tool_calls: ToolCall[];
  tool_results: ToolResult[];
  thinking?: string;  // Agent's reasoning/thinking process
  segment: number;
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResult {
  tool: string;
  arguments: Record<string, unknown>;
  success: boolean;
  data?: unknown;
  error?: string;
}

export interface DiscussionSegment {
  segment_number: number;
  start_turn: number;
  end_turn?: number;
  summary: string;
  orchestrator_message: string;
}

export interface DiscussionSummary {
  topic: string;
  start_time: string;
  end_time: string;
  total_turns: number;
  key_points: string[];
  consensus_reached: boolean;
  disagreements: string[];
  action_items: string[];
  final_recommendation?: string;
  // Extended comprehensive report fields
  problem_statement?: string;
  solution_options?: SolutionOption[];
  selected_solution?: string;
  selection_reasoning?: string;
  segment_reports?: SegmentReport[];
  agent_analyses?: AgentAnalysis[];
  final_answer?: string;
  justification?: string;
  implementation_steps?: string[];
  risks_and_mitigations?: string[];
}

export interface SolutionOption {
  option_name: string;
  description: string;
  pros: string[];
  cons: string[];
  supporters: string[];
  opposers: string[];
}

export interface SegmentReport {
  segment_number: number;
  summary: string;
  key_developments: string[];
  agent_contributions: Record<string, string>;
  decisions_made: string[];
  open_questions: string[];
}

export interface AgentAnalysis {
  agent_name: string;
  persona: string;
  critical_points: string[];
  key_arguments: string[];
  tools_used: string[];
  stance: string;
}

export interface ComprehensiveReport {
  session_id: string;
  topic: string;
  status: string;
  start_time: string;
  end_time: string;
  total_turns: number;
  problem_statement: string;
  final_answer: string;
  justification: string;
  final_recommendation: string;
  solution_options: SolutionOption[];
  selected_solution?: string;
  selection_reasoning: string;
  implementation_steps: string[];
  risks_and_mitigations: string[];
  action_items: string[];
  consensus_reached: boolean;
  key_points: string[];
  disagreements: string[];
  segment_reports: SegmentReport[];
  agent_analyses: AgentAnalysis[];
  turns: DiscussionTurn[];
  segments: DiscussionSegment[];
}

export interface Session {
  id: string;
  topic: string;
  turns: number;
  date: string;
  config?: CouncilConfig;
  total_tokens?: number;
  segments?: DiscussionSegment[];
  current_segment?: number;
}

export interface OrchestratorState {
  current_turn: number;
  max_turns: number;
  current_segment: number;
  total_segments: number;
  segment_tokens: number;
  total_tokens: number;
  is_running: boolean;
  status: 'idle' | 'thinking' | 'speaking' | 'orchestrating' | 'completed' | 'error';
  current_agent?: string;
}

export interface KeyInsight {
  id?: number;
  insight_number: number;
  content: string;
  source: 'orchestrator' | 'agent';
  source_agent?: string;
  turn_number?: number;
  segment: number;
  created_at?: string;
}

export interface ProgressUpdate {
  type: 'turn' | 'segment' | 'orchestrator' | 'insights' | 'complete' | 'error';
  turn?: DiscussionTurn;
  segment?: DiscussionSegment;
  orchestrator_message?: string;
  insights?: KeyInsight[];
  total_count?: number;
  summary?: DiscussionSummary;
  error?: string;
  state: OrchestratorState;
}

export type ViewMode = 'config' | 'discussion' | 'archives' | 'sessions' | 'report' | 'admin';

// Re-export admin types
export * from './admin';

export interface InsightsUpdate {
  type: 'insights';
  insights: KeyInsight[];
  total_count: number;
  state: OrchestratorState;
}

export const PERSONA_COLORS: Record<string, { bg: string; border: string; glow: string }> = {
  the_lazy_one: { bg: 'rgba(34, 197, 94, 0.15)', border: '#22c55e', glow: 'rgba(34, 197, 94, 0.3)' },
  the_egomaniac: { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', glow: 'rgba(245, 158, 11, 0.3)' },
  the_devils_advocate: { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', glow: 'rgba(239, 68, 68, 0.3)' },
  the_creative: { bg: 'rgba(168, 85, 247, 0.15)', border: '#a855f7', glow: 'rgba(168, 85, 247, 0.3)' },
  the_pragmatist: { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6', glow: 'rgba(59, 130, 246, 0.3)' },
  the_empath: { bg: 'rgba(236, 72, 153, 0.15)', border: '#ec4899', glow: 'rgba(236, 72, 153, 0.3)' },
  the_researcher: { bg: 'rgba(99, 102, 241, 0.15)', border: '#6366f1', glow: 'rgba(99, 102, 241, 0.3)' },
  the_orchestrator: { bg: 'rgba(234, 179, 8, 0.15)', border: '#eab308', glow: 'rgba(234, 179, 8, 0.3)' },
};

export const AVAILABLE_MODELS = [
  'kimi-latest',
  'open-fast',
  'open-large',
  'glm-latest',
  'minimaxai/minimax-m2',
  'anthropic/claude-3-haiku-20240307',
  'anthropic/claude-3-sonnet-20240229',
  'openai/gpt-4o',
  'openai/gpt-4o-mini',
];

export const DEFAULT_AGENT_CONFIGS: [string, string][] = [
  ['kimi-latest', 'the_lazy_one'],
  ['open-fast', 'the_egomaniac'],
  ['glm-latest', 'the_devils_advocate'],
  ['open-large', 'the_creative'],
  ['glm-latest', 'the_researcher'],
  ['kimi-latest', 'the_pragmatist'],
];

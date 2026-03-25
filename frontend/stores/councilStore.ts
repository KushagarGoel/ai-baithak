import { create } from 'zustand';
import {
  CouncilConfig,
  DiscussionTurn,
  DiscussionSegment,
  DiscussionSummary,
  ComprehensiveReport,
  Session,
  OrchestratorState,
  ViewMode,
  DEFAULT_AGENT_CONFIGS,
  KeyInsight,
} from '@/types';

interface CouncilState {
  // View state
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;

  // Configuration
  config: CouncilConfig;
  updateConfig: (updates: Partial<CouncilConfig>) => void;
  updateAgentConfig: (index: number, updates: Partial<CouncilConfig['agents'][0]>) => void;
  addAgent: () => void;
  removeAgent: (index: number) => void;
  resetConfig: () => void;

  // Discussion state
  turns: DiscussionTurn[];
  segments: DiscussionSegment[];
  summary: DiscussionSummary | null;
  orchestratorState: OrchestratorState;
  addTurn: (turn: DiscussionTurn) => void;
  updateSegment: (segment: DiscussionSegment) => void;
  setSummary: (summary: DiscussionSummary | null) => void;
  updateOrchestratorState: (updates: Partial<OrchestratorState>) => void;
  resetDiscussion: () => void;

  // Key Insights
  insights: KeyInsight[];
  addInsights: (insights: KeyInsight[]) => void;
  setInsights: (insights: KeyInsight[]) => void;

  // Sessions
  currentSessionId: string | null;
  setCurrentSessionId: (id: string | null) => void;

  // Comprehensive Report
  comprehensiveReport: ComprehensiveReport | null;
  setComprehensiveReport: (report: ComprehensiveReport | null) => void;

  // WebSocket
  wsConnection: WebSocket | null;
  setWsConnection: (ws: WebSocket | null) => void;
  wsStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  setWsStatus: (status: 'disconnected' | 'connecting' | 'connected' | 'error') => void;

  // Discussion state
  discussionStatus: 'idle' | 'running' | 'completed' | 'error';
  setDiscussionStatus: (status: 'idle' | 'running' | 'completed' | 'error') => void;
}

const defaultConfig: CouncilConfig = {
  topic: '',
  max_duration_minutes: 5,
  max_turns: 15,
  min_turns: 5,
  agents: DEFAULT_AGENT_CONFIGS.map(([model, persona], i) => ({
    name: `${persona.replace('the_', '').replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} (${model})`,
    model,
    persona,
    tools_enabled: true,
  })),
  litellm_proxy: {
    api_base: 'https://grid.ai.juspay.net',
    api_key: '',
  },
  orchestrator_model: 'kimi-latest',
  orchestrator_frequency: 3,
  context_compression_threshold: 20,
  save_transcript: true,
  workspace_path: '.',
};

const defaultOrchestratorState: OrchestratorState = {
  current_turn: 0,
  max_turns: 15,
  current_segment: 0,
  total_segments: 1,
  segment_tokens: 0,
  total_tokens: 0,
  is_running: false,
  status: 'idle',
};

export const useCouncilStore = create<CouncilState>((set, get) => ({
  // View state
  viewMode: 'config',
  setViewMode: (mode) => set({ viewMode: mode }),

  // Configuration
  config: { ...defaultConfig },
  updateConfig: (updates) => set((state) => ({
    config: { ...state.config, ...updates },
  })),
  updateAgentConfig: (index, updates) => set((state) => {
    const agents = [...state.config.agents];
    agents[index] = { ...agents[index], ...updates };
    return { config: { ...state.config, agents } };
  }),
  addAgent: () => set((state) => {
    if (state.config.agents.length >= 10) return state;
    const defaultPair = DEFAULT_AGENT_CONFIGS[state.config.agents.length % DEFAULT_AGENT_CONFIGS.length];
    const newAgent = {
      name: `Agent ${state.config.agents.length + 1}`,
      model: defaultPair[0],
      persona: defaultPair[1],
      tools_enabled: true,
    };
    return {
      config: {
        ...state.config,
        agents: [...state.config.agents, newAgent],
      },
    };
  }),
  removeAgent: (index) => set((state) => ({
    config: {
      ...state.config,
      agents: state.config.agents.filter((_, i) => i !== index),
    },
  })),
  resetConfig: () => set({ config: { ...defaultConfig } }),

  // Discussion state
  turns: [],
  segments: [],
  summary: null,
  orchestratorState: { ...defaultOrchestratorState },
  addTurn: (turn) => set((state) => ({
    turns: [...state.turns, turn],
  })),
  updateSegment: (segment) => set((state) => {
    const segments = [...state.segments];
    const index = segments.findIndex(s => s.segment_number === segment.segment_number);
    if (index >= 0) {
      segments[index] = segment;
    } else {
      segments.push(segment);
    }
    return { segments };
  }),
  setSummary: (summary) => set({ summary }),
  updateOrchestratorState: (updates) => set((state) => ({
    orchestratorState: { ...state.orchestratorState, ...updates },
  })),
  resetDiscussion: () => set({
    turns: [],
    segments: [],
    summary: null,
    orchestratorState: { ...defaultOrchestratorState },
    insights: [],
  }),

  // Key Insights
  insights: [],
  addInsights: (newInsights) => set((state) => ({
    insights: [...state.insights, ...newInsights],
  })),
  setInsights: (insights) => set({ insights }),

  // Sessions
  currentSessionId: null,
  setCurrentSessionId: (id) => set({ currentSessionId: id }),

  // Comprehensive Report
  comprehensiveReport: null,
  setComprehensiveReport: (report) => set({ comprehensiveReport: report }),

  // WebSocket
  wsConnection: null,
  setWsConnection: (ws) => set({ wsConnection: ws }),
  wsStatus: 'disconnected',
  setWsStatus: (status) => set({ wsStatus: status }),

  // Discussion state
  discussionStatus: 'idle',
  setDiscussionStatus: (status) => set({ discussionStatus: status }),
}));

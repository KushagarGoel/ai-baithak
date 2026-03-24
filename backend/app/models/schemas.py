"""Pydantic models for the Agent Council API."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class LiteLLMProxyConfig(BaseModel):
    """Configuration for LiteLLM proxy."""
    api_base: str = "http://localhost:4000"
    api_key: str = ""


class AgentConfig(BaseModel):
    """Configuration for a single agent."""
    name: str
    model: str
    persona: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools_enabled: bool = True


class CouncilConfig(BaseModel):
    """Configuration for the council discussion."""
    topic: str
    max_duration_minutes: int = 10
    max_turns: int = 20
    min_turns: int = 5
    agents: list[AgentConfig] = Field(default_factory=list)
    litellm_proxy: Optional[LiteLLMProxyConfig] = None
    orchestrator_model: str = "anthropic/claude-3-haiku-20240307"
    orchestrator_frequency: int = 3
    context_compression_threshold: int = 40
    save_transcript: bool = True
    workspace_path: str = "."
    session_id: Optional[str] = None


class ToolCall(BaseModel):
    """A tool call from an agent."""
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result of a tool execution."""
    tool: str
    arguments: dict[str, Any]
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class DiscussionTurn(BaseModel):
    """A single turn in the discussion."""
    turn_number: float  # Can be fractional (e.g., 5.5 for orchestrator interjections)
    agent_name: str
    persona: str
    content: str
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    segment: int = 0


class DiscussionSegment(BaseModel):
    """A segment of the discussion."""
    segment_number: int
    start_turn: int
    end_turn: Optional[int] = None
    summary: str = ""
    orchestrator_message: str = ""


class DiscussionSummary(BaseModel):
    """Summary of a completed discussion."""
    topic: str
    start_time: str
    end_time: str
    total_turns: int
    key_points: list[str]
    consensus_reached: bool
    disagreements: list[str]
    action_items: list[str]
    final_recommendation: Optional[str] = None


class OrchestratorState(BaseModel):
    """Current state of the orchestrator."""
    current_turn: int = 0
    max_turns: int = 20
    current_segment: int = 0
    total_segments: int = 1
    segment_tokens: int = 0  # Tokens used in current segment only
    total_tokens: int = 0    # Total tokens across all segments
    is_running: bool = False
    status: str = "idle"  # idle, thinking, speaking, orchestrating, completed, error
    current_agent: Optional[str] = None


class Session(BaseModel):
    """A saved session."""
    id: str
    topic: str
    turns: int
    date: str
    config: Optional[CouncilConfig] = None
    total_tokens: int = 0
    segments: list[DiscussionSegment] = Field(default_factory=list)
    current_segment: int = 0


class ArchiveItem(BaseModel):
    """An archived discussion."""
    id: str
    summary: DiscussionSummary
    transcript_path: str
    agent_count: int
    model_names: list[str]


class WebSocketMessage(BaseModel):
    """Base WebSocket message."""
    type: str


class StartDiscussionMessage(WebSocketMessage):
    """Message to start a discussion."""
    type: str = "start"
    config: CouncilConfig


class UserMessage(WebSocketMessage):
    """User message during discussion."""
    type: str = "user_message"
    content: str


class TurnUpdate(WebSocketMessage):
    """Turn update message."""
    type: str = "turn"
    turn: DiscussionTurn
    state: OrchestratorState


class SegmentUpdate(WebSocketMessage):
    """Segment update message."""
    type: str = "segment"
    segment: DiscussionSegment
    state: OrchestratorState


class OrchestratorMessage(WebSocketMessage):
    """Orchestrator message."""
    type: str = "orchestrator"
    message: str
    state: OrchestratorState


class StateUpdate(WebSocketMessage):
    """State update message."""
    type: str = "state"
    state: OrchestratorState


class CompleteMessage(WebSocketMessage):
    """Discussion complete message."""
    type: str = "complete"
    summary: DiscussionSummary
    state: OrchestratorState


class ErrorMessage(WebSocketMessage):
    """Error message."""
    type: str = "error"
    error: str


class KeyInsight(BaseModel):
    """A key insight extracted from the discussion."""
    id: Optional[int] = None
    insight_number: int
    content: str
    source: str = "orchestrator"  # 'orchestrator' or 'agent'
    source_agent: Optional[str] = None
    turn_number: Optional[float] = None
    segment: int = 0
    created_at: Optional[str] = None


class InsightsUpdate(WebSocketMessage):
    """Update when new insights are available."""
    type: str = "insights"
    insights: list[KeyInsight]
    total_count: int
    state: OrchestratorState

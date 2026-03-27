"""Pydantic models for the Agent Council API."""

from datetime import datetime
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field


# MCP Framework: Agent Configuration Models
class Agent(BaseModel):
    """An agent stored in the database."""
    id: str
    name: str
    description: Optional[str] = None
    system_prompt: str
    model: str = "openai/gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2000
    speak_probability: float = 1.0
    avatar_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_active: bool = True


class AgentCreate(BaseModel):
    """Request to create an agent."""
    name: str
    description: Optional[str] = None
    system_prompt: str
    model: str = "openai/gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2000
    speak_probability: float = 1.0
    avatar_url: Optional[str] = None


class AgentUpdate(BaseModel):
    """Request to update an agent."""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    speak_probability: Optional[float] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None


# MCP Framework: MCP Server Models
class MCPServerBase(BaseModel):
    """Base MCP server configuration."""
    name: str
    description: Optional[str] = None


class MCPServerCreate(MCPServerBase):
    """Request to create an MCP server."""
    transport: Literal["stdio", "sse", "websocket"]
    config: dict[str, Any]


class MCPServerUpdate(BaseModel):
    """Request to update an MCP server."""
    name: Optional[str] = None
    description: Optional[str] = None
    transport: Optional[Literal["stdio", "sse", "websocket"]] = None
    config: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class MCPServer(MCPServerBase):
    """An MCP server stored in the database."""
    id: str
    transport: Literal["stdio", "sse", "websocket"]
    config: dict[str, Any]
    is_active: bool = True
    created_at: Optional[str] = None


class MCPServerWithStatus(MCPServer):
    """MCP server with connection status."""
    status: str = "unknown"  # active, offline, error
    tool_count: int = 0
    last_error: Optional[str] = None


# MCP Framework: Permission Models
class AgentMCPPermission(BaseModel):
    """Permission grant for agent to access MCP."""
    agent_id: str
    mcp_id: str
    allowed_tools: Optional[list[str]] = None  # None = all tools allowed
    created_at: Optional[str] = None


class MCPAccessGrant(BaseModel):
    """Request to grant MCP access to an agent."""
    mcp_id: str
    allowed_tools: Optional[list[str]] = None


class MCPAccessUpdate(BaseModel):
    """Request to update MCP access permissions."""
    allowed_tools: Optional[list[str]] = None


class AgentWithMCPS(Agent):
    """Agent with its MCP permissions."""
    mcps: list[MCPServer] = Field(default_factory=list)


# MCP Framework: Agent Group Models
class AgentGroup(BaseModel):
    """A group of agents."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None


class AgentGroupCreate(BaseModel):
    """Request to create an agent group."""
    name: str
    description: Optional[str] = None


class AgentGroupWithMembers(AgentGroup):
    """Agent group with its member agents."""
    agents: list[Agent] = Field(default_factory=list)


# MCP Framework: Permission Matrix
class PermissionMatrixCell(BaseModel):
    """A cell in the permission matrix."""
    agent_id: str
    mcp_id: str
    has_access: bool
    allowed_tools: Optional[list[str]] = None
    all_tools: list[str] = Field(default_factory=list)


class PermissionMatrix(BaseModel):
    """The full permission matrix."""
    agents: list[Agent]
    mcps: list[MCPServer]
    permissions: list[PermissionMatrixCell]


# MCP Framework: Tool Models
class MCPTool(BaseModel):
    """A tool provided by an MCP server."""
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    mcp_server_id: str
    mcp_server_name: str


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
    agent_id: Optional[str] = None  # Database agent ID for MCP access


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


class AgentAnalysis(BaseModel):
    """Analysis of a single agent's contribution."""
    agent_name: str
    persona: str
    critical_points: list[str]
    key_arguments: list[str]
    tools_used: list[str] = Field(default_factory=list)
    stance: str = ""  # e.g., "supportive", "opposed", "neutral", "skeptical"


class SolutionOption(BaseModel):
    """A potential solution option discussed."""
    option_name: str
    description: str
    pros: list[str]
    cons: list[str]
    supporters: list[str]  # Agent names who supported this
    opposers: list[str]   # Agent names who opposed this


class SegmentReport(BaseModel):
    """Detailed report for a discussion segment."""
    segment_number: int
    summary: str
    key_developments: list[str]
    agent_contributions: dict[str, str]  # agent_name -> summary of contribution
    decisions_made: list[str]
    open_questions: list[str]


class DiscussionSummary(BaseModel):
    """Comprehensive solutioning document for a completed discussion."""
    topic: str
    start_time: str
    end_time: str
    total_turns: int

    # Overall analysis
    key_points: list[str]
    consensus_reached: bool
    disagreements: list[str]
    action_items: list[str]

    # Detailed solution breakdown
    problem_statement: str = ""
    solution_options: list[SolutionOption] = Field(default_factory=list)
    selected_solution: Optional[str] = None
    selection_reasoning: str = ""

    # Per-segment analysis
    segment_reports: list[SegmentReport] = Field(default_factory=list)

    # Agent analysis
    agent_analyses: list[AgentAnalysis] = Field(default_factory=list)

    # Final conclusion
    final_recommendation: Optional[str] = None
    final_answer: str = ""
    justification: str = ""
    implementation_steps: list[str] = Field(default_factory=list)
    risks_and_mitigations: list[str] = Field(default_factory=list)


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

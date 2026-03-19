"""Agent Council - A multi-agent deliberation system for complex problem solving."""

from .orchestrator import CouncilOrchestrator
from .config import CouncilConfig, AgentConfig
from .agent import CouncilAgent
from .tools import ToolRegistry

__version__ = "0.1.0"
__all__ = ["CouncilOrchestrator", "CouncilConfig", "AgentConfig", "CouncilAgent", "ToolRegistry"]

"""Configuration for Agent Council."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration for a single agent."""

    name: str
    model: str  # LiteLLM model name, e.g., "openai/gpt-4o", "anthropic/claude-3-sonnet-20240229"
    persona: str  # Key from personas.PERSONAS
    temperature: Optional[float] = None  # Override persona default
    max_tokens: Optional[int] = None  # Override persona default
    tools_enabled: bool = True


@dataclass
class LiteLLMProxyConfig:
    """Configuration for personal LiteLLM proxy deployment."""

    api_base: str  # e.g., "http://localhost:4000" or "https://your-litellm.com"
    api_key: str  # Your LiteLLM proxy API key


@dataclass
class CouncilConfig:
    """Configuration for the agent council."""

    topic: str
    max_duration_minutes: int = 10
    max_turns: int = 20
    min_turns: int = 5

    # Agents configuration
    agents: list[AgentConfig] = field(default_factory=list)

    # LiteLLM Proxy settings (optional - for personal deployments)
    litellm_proxy: Optional[LiteLLMProxyConfig] = None

    # Orchestrator settings
    orchestrator_model: str = "anthropic/claude-3-haiku-20240307"
    orchestrator_frequency: int = 3  # Interject every N turns

    # Output settings
    save_transcript: bool = True
    transcript_path: Optional[str] = None

    # Tool settings
    workspace_path: str = "."

    # Session ID for organizing files
    session_id: Optional[str] = None

    @classmethod
    def create_default(
        cls, topic: str, max_duration_minutes: int = 10
    ) -> "CouncilConfig":
        """Create a default configuration with diverse agents."""
        return cls(
            topic=topic,
            max_duration_minutes=max_duration_minutes,
            agents=[
                AgentConfig(
                    name="Lazy Larry",
                    model="openai/gpt-4o-mini",
                    persona="the_lazy_one",
                ),
                AgentConfig(
                    name="Smart Sally",
                    model="anthropic/claude-3-haiku-20240307",
                    persona="the_egomaniac",
                ),
                AgentConfig(
                    name="Skeptical Sam",
                    model="openai/gpt-4o-mini",
                    persona="the_devils_advocate",
                ),
                AgentConfig(
                    name="Creative Casey",
                    model="anthropic/claude-3-haiku-20240307",
                    persona="the_creative",
                ),
                AgentConfig(
                    name="Practical Pat",
                    model="openai/gpt-4o-mini",
                    persona="the_pragmatist",
                ),
            ],
        )

    @classmethod
    def create_with_models(
        cls,
        topic: str,
        models: list[str],
        max_duration_minutes: int = 10,
    ) -> "CouncilConfig":
        """
        Create a configuration with specific models.

        Args:
            topic: Discussion topic
            models: List of LiteLLM model identifiers (3-6 models recommended)
            max_duration_minutes: Maximum discussion time
        """
        personas = [
            "the_lazy_one",
            "the_egomaniac",
            "the_devils_advocate",
            "the_creative",
            "the_pragmatist",
            "the_empath",
        ]

        agents = []
        for i, model in enumerate(models):
            persona = personas[i % len(personas)]
            agents.append(
                AgentConfig(
                    name=f"Agent_{i + 1}_{persona.replace('the_', '').title()}",
                    model=model,
                    persona=persona,
                )
            )

        return cls(
            topic=topic,
            max_duration_minutes=max_duration_minutes,
            agents=agents,
        )

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.topic.strip():
            errors.append("Topic cannot be empty")

        if self.max_duration_minutes < 1:
            errors.append("Max duration must be at least 1 minute")

        if len(self.agents) < 2:
            errors.append("At least 2 agents are required")

        if len(self.agents) > 10:
            errors.append("Maximum 10 agents allowed")

        from .personas import list_personas

        valid_personas = set(list_personas())

        for agent in self.agents:
            if agent.persona not in valid_personas:
                errors.append(
                    f"Unknown persona '{agent.persona}' for agent '{agent.name}'"
                )

        return errors

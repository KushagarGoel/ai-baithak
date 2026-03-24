"""Streamlit dashboard for Agent Council."""

import asyncio
import os
import time
from datetime import datetime

import streamlit as st

from agent_council import CouncilConfig, CouncilOrchestrator
from agent_council.personas import list_personas

# Page configuration
st.set_page_config(
    page_title="Agent Council",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
.agent-message {
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
}
.the-lazy-one {
    background-color: #e8f5e9;
    border-left: 4px solid #4caf50;
}
.the-egomaniac {
    background-color: #fff3e0;
    border-left: 4px solid #ff9800;
}
.the-devils-advocate {
    background-color: #ffebee;
    border-left: 4px solid #f44336;
}
.the-creative {
    background-color: #f3e5f5;
    border-left: 4px solid #9c27b0;
}
.the-pragmatist {
    background-color: #e3f2fd;
    border-left: 4px solid #2196f3;
}
.the-empath {
    background-color: #fce4ec;
    border-left: 4px solid #e91e63;
}
.the-researcher {
    background-color: #e0f2f1;
    border-left: 4px solid #009688;
}
.orchestrator {
    background-color: #fff8e1;
    border-left: 4px solid #ffc107;
    font-style: italic;
}
.agent-name {
    font-weight: bold;
    font-size: 0.9rem;
    color: #666;
    margin-bottom: 0.25rem;
}
.persona-tag {
    font-size: 0.75rem;
    padding: 0.1rem 0.5rem;
    border-radius: 1rem;
    background-color: rgba(0,0,0,0.1);
    margin-left: 0.5rem;
}
</style>
""", unsafe_allow_html=True)


def get_persona_class(persona: str) -> str:
    """Get CSS class for a persona."""
    persona_map = {
        "The Lazy One": "the-lazy-one",
        "The Know-It-All": "the-egomaniac",
        "Devil's Advocate": "the-devils-advocate",
        "The Creative": "the-creative",
        "The Pragmatist": "the-pragmatist",
        "The Empath": "the-empath",
        "The Researcher": "the-researcher",
        "Manager": "orchestrator",
    }
    return persona_map.get(persona, "agent-message")


def render_message(turn):
    """Render a single message turn."""
    css_class = get_persona_class(turn.persona)

    st.markdown(f"""
    <div class="agent-message {css_class}">
        <div class="agent-name">
            {turn.agent_name}
            <span class="persona-tag">{turn.persona}</span>
        </div>
        <div>{turn.content}</div>
    </div>
    """, unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "discussion_running" not in st.session_state:
        st.session_state.discussion_running = False
    if "turns" not in st.session_state:
        st.session_state.turns = []
    if "summary" not in st.session_state:
        st.session_state.summary = None
    if "config" not in st.session_state:
        st.session_state.config = None


def sidebar_config():
    """Render sidebar configuration."""
    st.sidebar.title("🏛️ Agent Council")
    st.sidebar.markdown("---")

    st.sidebar.header("Discussion Setup")

    # Topic input
    topic = st.sidebar.text_area(
        "Discussion Topic",
        placeholder="Enter the topic for the council to discuss...",
        height=100,
    )

    # Duration
    duration = st.sidebar.slider(
        "Max Duration (minutes)",
        min_value=1,
        max_value=30,
        value=5,
        help="Maximum time the discussion will run",
    )

    # Max turns
    max_turns = st.sidebar.slider(
        "Max Turns",
        min_value=5,
        max_value=50,
        value=20,
        help="Maximum number of discussion turns",
    )

    st.sidebar.markdown("---")
    st.sidebar.header("Agent Configuration")

    # Agent setup
    personas = list_personas()

    # Default agents
    default_agents = [
        ("Lazy Larry", "the_lazy_one", "openai/gpt-4o-mini"),
        ("Smart Sally", "the_egomaniac", "anthropic/claude-3-haiku-20240307"),
        ("Skeptical Sam", "the_devils_advocate", "openai/gpt-4o-mini"),
        ("Creative Casey", "the_creative", "anthropic/claude-3-haiku-20240307"),
        ("Practical Pat", "the_pragmatist", "openai/gpt-4o-mini"),
    ]

    agents = []
    num_agents = st.sidebar.number_input(
        "Number of Agents",
        min_value=2,
        max_value=8,
        value=5,
    )

    for i in range(num_agents):
        default = default_agents[i] if i < len(default_agents) else (f"Agent {i+1}", personas[i % len(personas)], "openai/gpt-4o-mini")

        with st.sidebar.expander(f"Agent {i+1}", expanded=i == 0):
            name = st.text_input(f"Name", value=default[0], key=f"agent_name_{i}")
            persona = st.selectbox(
                f"Persona",
                options=personas,
                index=personas.index(default[1]) if default[1] in personas else 0,
                key=f"agent_persona_{i}",
            )
            model = st.text_input(
                f"Model (LiteLLM format)",
                value=default[2],
                key=f"agent_model_{i}",
                help="e.g., openai/gpt-4o, anthropic/claude-3-opus-20240229",
            )
            agents.append((name, persona, model))

    st.sidebar.markdown("---")

    # LiteLLM Proxy Configuration
    st.sidebar.header("LiteLLM Proxy (Optional)")
    st.sidebar.markdown("Configure your personal LiteLLM deployment:")

    use_proxy = st.sidebar.checkbox(
        "Use LiteLLM Proxy",
        value=False,
        help="Use a custom LiteLLM proxy instead of direct API providers"
    )

    proxy_base = ""
    proxy_key = ""
    if use_proxy:
        proxy_base = st.sidebar.text_input(
            "LiteLLM Proxy URL",
            value=os.getenv("LITELLM_PROXY_URL", "http://localhost:4000"),
            key="proxy_base",
            help="Your LiteLLM proxy base URL",
        )
        proxy_key = st.sidebar.text_input(
            "LiteLLM Proxy API Key",
            type="password",
            value=os.getenv("LITELLM_PROXY_KEY", ""),
            key="proxy_key",
            help="Your LiteLLM proxy API key",
        )

    st.sidebar.markdown("---")

    # API Keys section (only needed if not using proxy)
    st.sidebar.header("API Keys (Direct)")
    st.sidebar.markdown("Set your API keys if not using a proxy:")

    openai_key = st.sidebar.text_input(
        "OpenAI API Key",
        type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        key="openai_key",
    )
    anthropic_key = st.sidebar.text_input(
        "Anthropic API Key",
        type="password",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        key="anthropic_key",
    )

    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key
    if anthropic_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key

    return {
        "topic": topic,
        "duration": duration,
        "max_turns": max_turns,
        "agents": agents,
        "use_proxy": use_proxy,
        "proxy_base": proxy_base,
        "proxy_key": proxy_key,
    }


def create_config(setup: dict) -> CouncilConfig:
    """Create CouncilConfig from setup dict."""
    from agent_council.config import AgentConfig, LiteLLMProxyConfig

    agent_configs = []
    for name, persona, model in setup["agents"]:
        agent_configs.append(AgentConfig(
            name=name,
            model=model,
            persona=persona,
        ))

    # Configure LiteLLM proxy if enabled
    litellm_proxy = None
    if setup.get("use_proxy") and setup.get("proxy_base"):
        litellm_proxy = LiteLLMProxyConfig(
            api_base=setup["proxy_base"],
            api_key=setup.get("proxy_key", ""),
        )

    return CouncilConfig(
        topic=setup["topic"],
        max_duration_minutes=setup["duration"],
        max_turns=setup["max_turns"],
        agents=agent_configs,
        litellm_proxy=litellm_proxy,
    )


def run_discussion(config: CouncilConfig):
    """Run the discussion and update UI."""
    st.session_state.discussion_running = True
    st.session_state.turns = []
    st.session_state.summary = None

    orchestrator = CouncilOrchestrator(config)

    # Create a placeholder for live updates
    chat_container = st.container()

    async def progress_callback(turn_num, total_turns, turn):
        st.session_state.turns.append(turn)

        # Update the display
        with chat_container:
            render_message(turn)

    # Run the discussion
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        summary = loop.run_until_complete(
            orchestrator.run_discussion(progress_callback=progress_callback)
        )
        st.session_state.summary = summary
        st.session_state.orchestrator = orchestrator
    finally:
        loop.close()

    st.session_state.discussion_running = False
    st.rerun()


def render_summary():
    """Render the discussion summary."""
    summary = st.session_state.summary
    if not summary:
        return

    st.markdown("---")
    st.header("📋 Discussion Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Key Points")
        for point in summary.key_points:
            st.markdown(f"- {point}")

        st.subheader("Action Items")
        for item in summary.action_items:
            st.markdown(f"- [ ] {item}")

    with col2:
        st.subheader("Consensus")
        if summary.consensus_reached:
            st.success("✅ Consensus reached")
        else:
            st.warning("❌ No consensus reached")

        st.subheader("Disagreements")
        for disagreement in summary.disagreements:
            st.markdown(f"- ⚠️ {disagreement}")

    with col3:
        st.subheader("Usage Stats")
        # Get token count
        tokens = 0
        if "orchestrator" in st.session_state and hasattr(st.session_state.orchestrator, 'total_tokens_used'):
            tokens = st.session_state.orchestrator.total_tokens_used
        if tokens >= 1000:
            tokens_str = f"{tokens / 1000:.1f}k"
        else:
            tokens_str = str(tokens)
        st.metric("Total Tokens", tokens_str)
        st.caption("Approximate token usage for this discussion")

    st.subheader("Final Recommendation")
    st.info(summary.final_recommendation or "No recommendation provided")

    # Download transcript
    if "orchestrator" in st.session_state:
        transcript_file = st.session_state.orchestrator._save_transcript()
        with open(transcript_file, 'r') as f:
            transcript_data = f.read()

        st.download_button(
            label="📥 Download Transcript",
            data=transcript_data,
            file_name=transcript_file,
            mime="application/json",
        )


def main():
    """Main dashboard function."""
    init_session_state()

    # Title
    st.title("🏛️ Agent Council")
    st.markdown("*A deliberative multi-agent system for complex problem solving*")

    # Sidebar configuration
    setup = sidebar_config()

    # Main content area
    if not setup["topic"]:
        st.info("👈 Please enter a discussion topic in the sidebar to begin")
        return

    # Start button
    if not st.session_state.discussion_running and not st.session_state.summary:
        if st.button("🚀 Start Discussion", type="primary", use_container_width=True):
            config = create_config(setup)
            errors = config.validate()
            if errors:
                for error in errors:
                    st.error(error)
                return
            st.session_state.config = config
            run_discussion(config)

    # Show discussion status
    if st.session_state.discussion_running:
        st.spinner("Discussion in progress...")

    # Render past turns if any
    if st.session_state.turns:
        st.header("💬 Discussion")

        # Show token usage in a metric
        tokens = 0
        if "orchestrator" in st.session_state and hasattr(st.session_state.orchestrator, 'total_tokens_used'):
            tokens = st.session_state.orchestrator.total_tokens_used
        if tokens > 0:
            if tokens >= 1000:
                tokens_str = f"{tokens / 1000:.1f}k"
            else:
                tokens_str = str(tokens)
            st.caption(f"💰 Tokens used: ~{tokens_str}")

        for turn in st.session_state.turns:
            render_message(turn)

    # Render summary if complete
    if st.session_state.summary:
        render_summary()

        # New discussion button
        if st.button("🔄 Start New Discussion", use_container_width=True):
            st.session_state.discussion_running = False
            st.session_state.turns = []
            st.session_state.summary = None
            st.session_state.config = None
            st.session_state.orchestrator = None
            st.rerun()


if __name__ == "__main__":
    main()
